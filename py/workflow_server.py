#!/usr/bin/env python3
"""
工作流 Lisp Web 服务器 - 简化版
"""

import os
import sys
import re
import time
import json
import base64
import shutil
import subprocess
import threading
import queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_lisp import run as run_lisp, GLOBAL_ENV, to_lisp_str, to_symbol, _CN_ALIASES
import workflow_lisp

# 全局状态
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_CONFIG_PATH = os.path.join(_BASE_DIR, '.user_config.json')
_server_api_key = ""
_api_keys = {}
_KNOWN_PROVIDERS = ("deepseek", "siliconflow", "kling", "zhipu")
import uuid

# ── 执行会话：每客户端绑定独立队列，全局仅允许一个活跃执行 ──
_exec_lock = threading.Lock()
_exec_tls = threading.local()
_active_session = None


class ExecutionSession:
    """单次脚本执行上下文，绑定发起客户端。"""

    def __init__(self, client_id: str, markdown: bool = False):
        self.id = uuid.uuid4().hex
        self.client_id = client_id or ""
        self.markdown = markdown
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None

    def stopped(self):
        return self.stop_event.is_set()

    def request_stop(self):
        self.stop_event.set()
        cancel_search_activity()
        try:
            self.output_queue.put_nowait("__STOPPED__")
        except queue.Full:
            pass
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.input_queue.put_nowait("")
        except queue.Full:
            pass

    def drain_output(self):
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break


def _get_active_session():
    with _exec_lock:
        return _active_session


def _terminate_session(session, join_timeout=3.0):
    """停止指定会话及其关联异步搜索活动。"""
    if not session:
        return
    session.request_stop()
    set_cancel_check(lambda: True)
    t = session.thread
    if t and t.is_alive() and t is not threading.current_thread():
        t.join(timeout=join_timeout)
    session.drain_output()


def _terminate_active_execution(join_timeout=3.0):
    """强制终止当前活跃执行（新执行启动前 / 全局 stop 时调用）。"""
    global _active_session
    with _exec_lock:
        session = _active_session
        _active_session = None
    if session:
        _terminate_session(session, join_timeout=join_timeout)
    set_cancel_check(lambda: (_get_active_session() is None) or _get_active_session().stopped())


def _start_execution(client_id: str, code: str, markdown: bool = False, inputs: Optional[dict] = None):
    """终止旧执行并启动新会话。返回新 ExecutionSession。"""
    global _active_session
    _terminate_active_execution()
    session = ExecutionSession(client_id, markdown)
    with _exec_lock:
        _active_session = session
    set_cancel_check(lambda: session.stopped())

    def _run():
        global _active_session
        _exec_tls.session = session
        try:
            # 注入运行时用户输入（角色图路径等），让 Lisp 端用 (取值 用户输入数据 "key") 读取
            if inputs:
                GLOBAL_ENV[to_symbol('client-input')] = inputs
                GLOBAL_ENV[to_symbol('用户输入数据')] = inputs
            _execute_code(session, code)
        finally:
            if getattr(_exec_tls, "session", None) is session:
                _exec_tls.session = None
            with _exec_lock:
                if _active_session is session:
                    _active_session = None
            set_cancel_check(lambda: (_get_active_session() is None) or _get_active_session().stopped())

    session.thread = threading.Thread(target=_run, daemon=True)
    session.thread.start()
    return session


def _session_for_output():
    """执行线程内或 torrent 回调中获取当前会话。"""
    s = getattr(_exec_tls, "session", None)
    if s:
        return s
    return _get_active_session()


markdown_mode = False  # 保留变量供旧逻辑兼容（实际用 session.markdown）


def _get_merged_api_keys():
    """合并本地配置与环境变量中的 API Key。

    Kling 现在拆成 kling_ak / kling_sk 两个独立字段，便于前端两输入框。
    兼容旧的 kling="ak:sk" 写法。
    """
    keys = dict(_api_keys)
    if not keys.get("deepseek"):
        env_key = (
            os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        if env_key:
            keys["deepseek"] = env_key
    if not keys.get("siliconflow") and os.environ.get("SILICONFLOW_API_KEY"):
        keys["siliconflow"] = os.environ["SILICONFLOW_API_KEY"].strip()
    # Zhipu: 智谱清影 API Key
    if not keys.get("zhipu") and os.environ.get("ZHIPU_API_KEY"):
        keys["zhipu"] = os.environ["ZHIPU_API_KEY"].strip()
    # Kling: 优先使用拆分字段，缺失时回退到合并字段/环境变量
    if not (keys.get("kling_ak") and keys.get("kling_sk")):
        # 回退路径 1: 旧 kling="ak:sk" 字段
        legacy = (keys.get("kling") or "").strip()
        if ":" in legacy and not (keys.get("kling_ak") and keys.get("kling_sk")):
            ak, sk = (s.strip() for s in legacy.split(":", 1))
            keys["kling_ak"] = ak
            keys["kling_sk"] = sk
        # 回退路径 2: 旧 KLING_API_KEY="ak:sk" 环境变量
        if not (keys.get("kling_ak") and keys.get("kling_sk")):
            env_legacy = os.environ.get("KLING_API_KEY", "").strip()
            if ":" in env_legacy:
                ak, sk = (s.strip() for s in env_legacy.split(":", 1))
                keys["kling_ak"] = ak
                keys["kling_sk"] = sk
    # 回退路径 3: 新的 KLING_AK / KLING_SK 拆分环境变量
    if not keys.get("kling_ak") and os.environ.get("KLING_AK"):
        keys["kling_ak"] = os.environ["KLING_AK"].strip()
    if not keys.get("kling_sk") and os.environ.get("KLING_SK"):
        keys["kling_sk"] = os.environ["KLING_SK"].strip()
    return keys


def _mask_api_key(key):
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _make_llm_fn():
    """创建使用服务端 API Key 的 call-llm 函数"""
    from workflow.llm import call_llm
    keys = _get_merged_api_keys()
    key = keys.get("deepseek") or _server_api_key
    if key:
        return lambda prompt: call_llm(prompt, config={"api_key": key})
    return lambda prompt: call_llm(prompt)  # 无 key 时走 mock 模式


def update_llm_env():
    """更新 Lisp 全局环境中的 call-llm，注入当前 API Key"""
    fn = _make_llm_fn()
    GLOBAL_ENV['call-llm'] = fn
    GLOBAL_ENV['llm'] = fn
    GLOBAL_ENV[to_symbol('调用模型')] = fn


def _read_user_config_file():
    if not os.path.isfile(_USER_CONFIG_PATH):
        return {}
    try:
        with open(_USER_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"[Config] 读取 .user_config.json 失败: {e}")
        return {}


def _write_user_config_file(data):
    with open(_USER_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def _sync_legacy_api_key_field(data):
    """保持 api_key 与 deepseek 同步，兼容旧前端"""
    deepseek = (data.get('api_keys') or {}).get('deepseek', '').strip()
    if deepseek:
        data['api_key'] = deepseek
    else:
        data.pop('api_key', None)


def _load_user_config():
    """启动时从本地文件加载多 Provider API Key"""
    global _server_api_key, _api_keys
    data = _read_user_config_file()
    if not data:
        return

    api_keys = data.get('api_keys') or {}
    if not isinstance(api_keys, dict):
        api_keys = {}

    legacy = (data.get('api_key') or '').strip()
    if legacy and not (api_keys.get('deepseek') or '').strip():
        api_keys['deepseek'] = legacy

    _api_keys = {
        k: str(v).strip()
        for k, v in api_keys.items()
        if v and str(v).strip()
    }
    _server_api_key = _api_keys.get('deepseek', legacy)

    if _api_keys:
        providers = ', '.join(sorted(_api_keys.keys()))
        print(f"[Config] 已加载 API 密钥：{providers}")


def _save_provider_api_key(provider, api_key):
    """按 provider 写入 API Key"""
    global _server_api_key, _api_keys
    provider = (provider or 'deepseek').strip().lower()
    data = _read_user_config_file()
    api_keys = data.get('api_keys') or {}
    if not isinstance(api_keys, dict):
        api_keys = {}
    api_keys[provider] = api_key
    data['api_keys'] = api_keys
    _sync_legacy_api_key_field(data)
    _write_user_config_file(data)

    _api_keys = {
        k: str(v).strip()
        for k, v in api_keys.items()
        if v and str(v).strip()
    }
    if provider == 'deepseek':
        _server_api_key = api_key


def _clear_provider_api_key(provider=None):
    """清除指定 provider 的 API Key；无 provider 时清除 deepseek（兼容旧接口）"""
    global _server_api_key, _api_keys
    provider = (provider or 'deepseek').strip().lower()
    data = _read_user_config_file()
    api_keys = data.get('api_keys') or {}
    if not isinstance(api_keys, dict):
        api_keys = {}
    api_keys.pop(provider, None)
    if api_keys:
        data['api_keys'] = api_keys
    else:
        data.pop('api_keys', None)
    if provider == 'deepseek':
        data.pop('api_key', None)
    _sync_legacy_api_key_field(data)

    if data:
        _write_user_config_file(data)
    elif os.path.isfile(_USER_CONFIG_PATH):
        os.remove(_USER_CONFIG_PATH)

    _api_keys = {
        k: str(v).strip()
        for k, v in api_keys.items()
        if v and str(v).strip()
    }
    if provider == 'deepseek':
        _server_api_key = _api_keys.get('deepseek', '')


def _config_api_keys_response():
    merged = _get_merged_api_keys()
    result = {}
    for name in _KNOWN_PROVIDERS:
        if name == 'kling':
            # Kling 现在拆成 ak + sk，单独返回
            ak = merged.get('kling_ak', '')
            sk = merged.get('kling_sk', '')
            result[name] = {
                "set": bool(ak and sk),
                "kling_ak": _mask_api_key(ak),
                "kling_sk": _mask_api_key(sk),
                "masked": f"{_mask_api_key(ak)} / {_mask_api_key(sk)}",
            }
        else:
            key = merged.get(name, '')
            result[name] = {
                "set": bool(key),
                "masked": _mask_api_key(key),
            }
    deepseek = merged.get('deepseek', '')
    return {
        "api_keys": result,
        "api_key_set": bool(deepseek),
        "masked_key": _mask_api_key(deepseek),
    }


def _save_user_config_api_key(api_key):
    """兼容旧接口：写入 deepseek key"""
    _save_provider_api_key('deepseek', api_key)


def _clear_user_config_api_key():
    """兼容旧接口：清除 deepseek key"""
    _clear_provider_api_key('deepseek')


# 飞书 Webhook 配置
import os
FEISHU_WEBHOOK = os.environ.get('FEISHU_WEBHOOK', '[请配置飞书Webhook地址]')

def feishu_send(title, content):
    """发送消息到飞书群"""
    try:
        import urllib.request
        import json

        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "red" if "负向" in title else "green"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "plain_text", "content": content}}
                ]
            }
        }

        data = json.dumps(card).encode('utf-8')
        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('code') == 0 or result.get('StatusCode') == 0:
                return "飞书消息发送成功"
            else:
                return f"飞书发送失败: {result}"
    except Exception as e:
        return f"飞书发送失败: {str(e)}"


# 注册飞书函数
GLOBAL_ENV['send-to-feishu'] = feishu_send
GLOBAL_ENV[to_symbol('发送飞书')] = feishu_send

# 注册种子搜索函数（仅保留搜索原语，筛选/格式化由 Lisp 库实现）
from workflow.torrent import (
    torrent_search, torrent_guess_en, build_search_term,
    set_api_key_provider, set_progress_callback, set_cancel_check, cancel_search_activity,
)
from workflow.ai_services import (
    set_api_keys_provider as set_ai_api_keys_provider,
    lisp_ai_text, lisp_ai_image, lisp_ai_video, lisp_video_concat,
    lisp_slideshow_video,
)
from workflow.user_errors import format_user_error
GLOBAL_ENV['torrent-search'] = torrent_search
GLOBAL_ENV[to_symbol('搜索种子')] = torrent_search
GLOBAL_ENV['torrent-guess-en'] = torrent_guess_en
GLOBAL_ENV[to_symbol('猜测英文片名')] = torrent_guess_en
GLOBAL_ENV['build-search-term'] = build_search_term
GLOBAL_ENV[to_symbol('构建搜索词')] = build_search_term

# 注册种子结果/推荐的 SSE 发送原语
import json as _json

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples', '搜索历史.json')

def stream_torrent_results(results):
    """发送结构化种子结果到前端"""
    session = _session_for_output()
    if not session or session.stopped():
        return
    payload = _json.dumps(results, ensure_ascii=False).replace('\n', '')
    session.output_queue.put(f"__TORRENT__:{payload}")


def stream_search_progress(data):
    """搜索过程中向前端推送进度"""
    session = _session_for_output()
    if not session or session.stopped():
        return
    payload = _json.dumps(data, ensure_ascii=False).replace('\n', '')
    session.output_queue.put(f"__PROGRESS__:{payload}")


def emit_search_progress(message, percent=0, eta=None):
    """Lisp 可调用的搜索进度原语"""
    data = {"message": str(message), "percent": int(percent), "elapsed": 0}
    if eta is not None:
        data["eta"] = int(eta)
    stream_search_progress(data)


set_progress_callback(stream_search_progress)
GLOBAL_ENV['search-progress'] = emit_search_progress
GLOBAL_ENV[to_symbol('发送搜索进度')] = emit_search_progress


def stream_recommendations(items):
    """发送推荐列表到前端"""
    session = _session_for_output()
    if not session or session.stopped():
        return
    payload = _json.dumps(items, ensure_ascii=False).replace('\n', '')
    session.output_queue.put(f"__RECOMMEND__:{payload}")

def load_search_history():
    """读取搜索历史"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return _json.load(f)
    return []

def save_search_history(history):
    """保存搜索历史"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        _json.dump(history, f, ensure_ascii=False, indent=2)
    return "ok"

GLOBAL_ENV['emit-torrent-results'] = stream_torrent_results
GLOBAL_ENV[to_symbol('发送种子结果')] = stream_torrent_results
GLOBAL_ENV['emit-recommendations'] = stream_recommendations
GLOBAL_ENV[to_symbol('发送推荐')] = stream_recommendations
GLOBAL_ENV['load-history'] = load_search_history
GLOBAL_ENV[to_symbol('读取历史')] = load_search_history
GLOBAL_ENV['save-history'] = save_search_history
GLOBAL_ENV[to_symbol('保存历史')] = save_search_history

GLOBAL_ENV['ai-text'] = lisp_ai_text
GLOBAL_ENV[to_symbol('AI文本')] = lisp_ai_text
GLOBAL_ENV['ai-image'] = lisp_ai_image
GLOBAL_ENV[to_symbol('AI图像')] = lisp_ai_image
GLOBAL_ENV['ai-video'] = lisp_ai_video
GLOBAL_ENV[to_symbol('AI视频')] = lisp_ai_video
GLOBAL_ENV['video-concat'] = lisp_video_concat
GLOBAL_ENV[to_symbol('视频拼接')] = lisp_video_concat
GLOBAL_ENV['slideshow-video'] = lisp_slideshow_video
GLOBAL_ENV[to_symbol('幻灯片视频')] = lisp_slideshow_video


# 初始化时加载本地配置并注入 LLM / AI 服务
_load_user_config()
set_api_key_provider(lambda: _get_merged_api_keys().get("deepseek", ""))
set_ai_api_keys_provider(_get_merged_api_keys)
update_llm_env()


def stream_print(*args):
    """流式打印 - 支持多个参数"""
    session = _session_for_output()
    if not session or session.stopped():
        return
    text = ' '.join(str(a) for a in args)
    prefix = "__MD__:" if session.markdown else "__TEXT__:"
    escaped = text.replace('\n', '↎')
    session.output_queue.put(f"{prefix}{escaped}")


def stream_input(prompt=""):
    """阻塞等待用户输入（仅接受绑定客户端的 /api/input）"""
    session = _session_for_output()
    if not session or session.stopped():
        return ""
    text = str(prompt).replace('\n', '↎') if prompt else ""
    session.output_queue.put(f"__INPUT__:{text}")
    while not session.stopped():
        try:
            val = session.input_queue.get(timeout=1.0)
            if session.stopped():
                return ""
            return val
        except queue.Empty:
            continue
    return ""


def stream_interact(prompt, options):
    """
    结构化交互：弹出一个选项列表（含可选 image/video 缩略图）给用户点选。

    options: list of {label, value, image?, video?}
      - label:  显示文本（如 "[1] 使用这组帧"）
      - value:  用户选择后回传给 Lisp 的字符串
      - image:  可选，图片 URL/路径（前端会渲染为缩略图）
      - video:  可选，视频 URL/路径
    """
    session = _session_for_output()
    if not session or session.stopped():
        return ""
    payload = {
        "prompt": str(prompt).replace('\n', '↎'),
        "options": list(options or []),
    }
    session.output_queue.put(f"__INTERACT__:{json.dumps(payload, ensure_ascii=False)}")
    while not session.stopped():
        try:
            val = session.input_queue.get(timeout=1.0)
            if session.stopped():
                return ""
            return val
        except queue.Empty:
            continue
    return ""


def _execute_code(session: ExecutionSession, code: str):
    """在独立线程中执行代码"""
    global markdown_mode
    markdown_mode = session.markdown

    use_zhiyu = os.environ.get("ZHIYU_RUNTIME", "zhiyu").lower() != "legacy"

    try:
        if use_zhiyu:
            from workflow.zhiyu_runner import run_zhiyu_session
            run_zhiyu_session(session, code)
            return

        update_llm_env()

        GLOBAL_ENV['print'] = stream_print
        GLOBAL_ENV[to_symbol('打印')] = stream_print
        GLOBAL_ENV[to_symbol('输出')] = stream_print
        GLOBAL_ENV['input'] = stream_input
        GLOBAL_ENV[to_symbol('输入')] = stream_input
        GLOBAL_ENV['interact'] = stream_interact
        GLOBAL_ENV[to_symbol('选择')] = stream_interact
        GLOBAL_ENV[to_symbol('交互')] = stream_interact

        workflow_lisp.BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples')
        workflow_lisp._loaded_files = set()

        result = run_lisp(code)

        if session.stopped():
            session.output_queue.put("__STOPPED__")
            return

        if result is not None:
            result_str = str(result).replace('\n', '↎')
            session.output_queue.put(f"__RESULT__:{result_str}")

        session.output_queue.put("__DONE__")

    except Exception as e:
        if not session.stopped():
            session.output_queue.put(f"__ERROR__:{format_user_error(e)}")
        else:
            session.output_queue.put("__STOPPED__")


_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

_STATIC_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
}


def _serve_static_file(handler, rel_path):
    """Serve a file from the static directory."""
    from urllib.parse import unquote
    rel_path = unquote(rel_path).lstrip('/')
    fpath = os.path.normpath(os.path.join(_STATIC_DIR, rel_path))
    if not fpath.startswith(_STATIC_DIR) or not os.path.isfile(fpath):
        handler.send_error(404)
        return
    ext = os.path.splitext(fpath)[1].lower()
    content_type = _STATIC_TYPES.get(ext, 'application/octet-stream')
    with open(fpath, 'rb') as f:
        data = f.read()
    handler.send_response(200)
    handler.send_header('Content-type', content_type)
    if ext in ('.html', '.js', '.css'):
        handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    handler.end_headers()
    handler.wfile.write(data)


# --- aria2 视频预览 ---
_PREVIEW_DATA_DIR = os.path.join(_BASE_DIR, '.preview_cache')
_PREVIEW_CACHE = {}
_PREVIEW_LOCK = threading.Lock()
_ARIA2_AVAILABLE = shutil.which('aria2c') is not None

_VIDEO_EXTS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.webm'}
_VIDEO_CONTENT_TYPES = {
    '.mkv': 'video/x-matroska',
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.wmv': 'video/x-ms-msvideo',
    '.webm': 'video/webm',
}

_ARIA2_HINT = (
    '视频预览增强功能需要 aria2，安装方法：brew install aria2（macOS）'
    ' / apt install aria2（Linux）/ 下载：https://aria2.github.io'
)


def _magnet_info_hash(magnet):
    m = re.search(r'btih:([A-Fa-f0-9]{40})', magnet, re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r'btih:([A-Za-z0-9]{32})', magnet, re.I)
    if m:
        try:
            return base64.b32decode(m.group(1).upper()).hex().upper()
        except Exception:
            pass
    return ''


def _bdecode_at(data, idx):
    if idx >= len(data):
        raise ValueError('bencode eof')
    c = data[idx]
    if c == ord('i'):
        end = data.index(ord('e'), idx + 1)
        return int(data[idx + 1:end].decode('ascii')), end + 1
    if c == ord('l'):
        idx += 1
        items = []
        while data[idx] != ord('e'):
            val, idx = _bdecode_at(data, idx)
            items.append(val)
        return items, idx + 1
    if c == ord('d'):
        idx += 1
        obj = {}
        while data[idx] != ord('e'):
            key, idx = _bdecode_at(data, idx)
            val, idx = _bdecode_at(data, idx)
            obj[key] = val
        return obj, idx + 1
    if 48 <= c <= 57:
        colon = data.index(ord(':'), idx)
        n = int(data[idx:colon].decode('ascii'))
        start = colon + 1
        return data[start:start + n], start + n
    raise ValueError(f'bencode bad byte {c}')


def _torrent_largest_video(torrent_path):
    with open(torrent_path, 'rb') as f:
        raw = f.read()
    root, _ = _bdecode_at(raw, 0)
    info = root.get(b'info', {})
    candidates = []
    if b'files' in info:
        for ent in info[b'files']:
            parts = ent.get(b'path', [])
            path = '/'.join(
                p.decode('utf-8', errors='replace') if isinstance(p, bytes) else str(p)
                for p in parts
            )
            candidates.append((path, int(ent.get(b'length', 0))))
    elif b'name' in info:
        name = info[b'name']
        if isinstance(name, bytes):
            name = name.decode('utf-8', errors='replace')
        candidates.append((name, int(info.get(b'length', 0))))
    if not candidates:
        return '', 0
    video = [c for c in candidates if os.path.splitext(c[0])[1].lower() in _VIDEO_EXTS]
    pool = video or candidates
    return max(pool, key=lambda x: x[1])


def _find_torrent_file(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if name.endswith('.torrent'):
                return os.path.join(dirpath, name)
    return ''


def _find_video_on_disk(root_dir, prefer_name=''):
    best_path = ''
    best_size = 0
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if name.endswith(('.torrent', '.aria2')):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in _VIDEO_EXTS:
                continue
            path = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if prefer_name:
                rel = os.path.relpath(path, root_dir).replace('\\', '/')
                if rel != prefer_name and os.path.basename(prefer_name) != name:
                    continue
            if size > best_size:
                best_size = size
                best_path = path
    if best_path or not prefer_name:
        return best_path, best_size
    return _find_video_on_disk(root_dir, '')


class Aria2PreviewEntry:
    METADATA_TIMEOUT = 30
    MIN_READY_BYTES = 2 * 1024 * 1024

    def __init__(self, info_hash, magnet):
        self.info_hash = info_hash
        self.magnet = magnet
        self.save_path = os.path.join(_PREVIEW_DATA_DIR, info_hash)
        self.lock = threading.Lock()
        self.process = None
        self.ready = False
        self.error = None
        self.filename = ''
        self.file_path = ''
        self.file_size = 0
        self.content_type = 'application/octet-stream'
        self._init_started = False

    def _ensure_download(self):
        with self.lock:
            if self._init_started:
                return
            self._init_started = True
        os.makedirs(self.save_path, exist_ok=True)
        cmd = [
            'aria2c',
            f'--dir={self.save_path}',
            '--seed-time=0',
            '--bt-save-metadata=true',
            '--enable-dht=true',
            '--enable-peer-exchange=true',
            '--stream-piece-selector=inorder',
            '--bt-prioritize-piece=head=2048,tail=2048',
            '--file-allocation=none',
            '--summary-interval=0',
            '--console-log-level=error',
            '--quiet=true',
            '--download-result=hide',
            self.magnet,
        ]
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            with self.lock:
                self.error = str(e)

    def _refresh_file_info(self):
        torrent_path = _find_torrent_file(self.save_path)
        prefer = ''
        total = 0
        if torrent_path:
            rel, total = _torrent_largest_video(torrent_path)
            if rel:
                prefer = rel
                self.filename = os.path.basename(rel)
                self.file_size = total

        path, current = _find_video_on_disk(self.save_path, prefer)
        if path:
            self.file_path = path
            if not self.filename:
                self.filename = os.path.basename(path)
            if not self.file_size:
                self.file_size = current
            ext = os.path.splitext(path)[1].lower()
            self.content_type = _VIDEO_CONTENT_TYPES.get(ext, 'application/octet-stream')
            if current >= self.MIN_READY_BYTES or (
                self.file_size and current / self.file_size >= 0.02
            ):
                self.ready = True
            return current
        return 0

    def get_status(self):
        if not _ARIA2_AVAILABLE:
            return {'ready': False, 'progress': 0, 'filename': '', 'aria2': False}
        self._ensure_download()
        with self.lock:
            if self.error:
                return {'ready': False, 'progress': 0, 'filename': '', 'aria2': True}
        if self.process and self.process.poll() is not None and self.process.returncode not in (0, None):
            with self.lock:
                if not self.ready:
                    self.error = f'aria2 exited {self.process.returncode}'

        current = self._refresh_file_info()
        progress = 0
        if self.file_size > 0 and current > 0:
            progress = int(min(99, max(0, current * 100 // self.file_size)))
        elif current > 0:
            progress = min(30, int(current // (512 * 1024)))

        return {
            'ready': self.ready,
            'progress': progress,
            'filename': self.filename,
            'aria2': True,
        }

    def wait_ready(self, timeout=30):
        if not _ARIA2_AVAILABLE:
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_status()
            if status.get('ready'):
                return True
            with self.lock:
                if self.error:
                    return False
            time.sleep(0.5)
        return self.ready

    def read_range(self, start, end, timeout=120):
        if not self.file_path:
            self._refresh_file_info()
        if not self.file_path:
            return None
        want = end - start + 1
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                available = os.path.getsize(self.file_path)
            except OSError:
                available = 0
            if available > end:
                with open(self.file_path, 'rb') as f:
                    f.seek(start)
                    data = f.read(want)
                if len(data) == want:
                    return data
            time.sleep(0.3)
        return None


def _get_preview_entry(magnet):
    if not magnet or not magnet.startswith('magnet:'):
        return None
    info_hash = _magnet_info_hash(magnet)
    if not info_hash:
        return None
    with _PREVIEW_LOCK:
        if info_hash not in _PREVIEW_CACHE:
            _PREVIEW_CACHE[info_hash] = Aria2PreviewEntry(info_hash, magnet)
        return _PREVIEW_CACHE[info_hash]


def preview_status(magnet):
    entry = _get_preview_entry(magnet)
    if not entry:
        return {'ready': False, 'progress': 0, 'filename': '', 'aria2': _ARIA2_AVAILABLE}
    return entry.get_status()


def _send_preview_unavailable(handler):
    handler.send_response(503)
    handler.send_header('Content-Type', 'text/plain; charset=utf-8')
    handler.end_headers()
    handler.wfile.write('资源暂不可用'.encode('utf-8'))


def _parse_range_header(range_header, file_size):
    if not range_header:
        return None
    m = re.match(r'bytes=(\d+)-(\d*)', range_header.strip())
    if not m:
        return None
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else file_size - 1
    if file_size > 0:
        end = min(end, file_size - 1)
    if start > end:
        return None
    return start, end


def handle_preview_stream(handler, magnet):
    if not _ARIA2_AVAILABLE:
        _send_preview_unavailable(handler)
        return
    entry = _get_preview_entry(magnet)
    if not entry or not entry.wait_ready(timeout=30):
        _send_preview_unavailable(handler)
        return

    file_size = entry.file_size or 0
    try:
        disk_size = os.path.getsize(entry.file_path) if entry.file_path else 0
    except OSError:
        disk_size = 0
    if file_size <= 0:
        file_size = disk_size
    if file_size <= 0:
        _send_preview_unavailable(handler)
        return

    range_header = handler.headers.get('Range')
    parsed = _parse_range_header(range_header, file_size)
    if parsed:
        start, end = parsed
        data = entry.read_range(start, end)
        if data is None:
            _send_preview_unavailable(handler)
            return
        handler.send_response(206)
        handler.send_header('Content-Type', entry.content_type)
        handler.send_header('Accept-Ranges', 'bytes')
        handler.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    else:
        data = entry.read_range(0, min(file_size - 1, max(disk_size - 1, 0)), timeout=300)
        if data is None:
            _send_preview_unavailable(handler)
            return
        handler.send_response(200)
        handler.send_header('Content-Type', entry.content_type)
        handler.send_header('Accept-Ranges', 'bytes')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            _serve_static_file(self, 'index.html')
        elif self.path.startswith('/?'):
            _serve_static_file(self, 'index.html')
        elif self.path.startswith('/static/'):
            _serve_static_file(self, self.path[len('/static/'):])
        elif self.path == '/api/status':
            merged = _get_merged_api_keys()
            self.send_json({
                "status": "ok",
                "api_key_set": bool(merged.get("deepseek")),
                "aria2": _ARIA2_AVAILABLE,
            })
        elif self.path == '/api/config':
            self.send_json(_config_api_keys_response())
        elif self.path == '/api/files':
            examples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples')
            def build_tree(dir_path):
                items = []
                all_entries = [e for e in os.listdir(dir_path) if not e.startswith('.')]
                dirs = sorted([e for e in all_entries if os.path.isdir(os.path.join(dir_path, e))], key=lambda e: os.stat(os.path.join(dir_path, e)).st_birthtime, reverse=True)
                files = sorted([e for e in all_entries if not os.path.isdir(os.path.join(dir_path, e))], key=lambda e: os.stat(os.path.join(dir_path, e)).st_birthtime, reverse=True)
                for entry in dirs:
                    items.append({"name": entry, "type": "dir", "children": build_tree(os.path.join(dir_path, entry))})
                for entry in files:
                    items.append({"name": entry, "type": "file"})
                return items
            self.send_json({"tree": build_tree(examples_dir)})
        elif self.path.startswith('/api/file/'):
            from urllib.parse import unquote
            name = unquote(self.path[len('/api/file/'):])
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples', name)
            fpath = os.path.normpath(fpath)
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            if os.path.exists(fpath) and fpath.startswith(examples_dir) and os.path.isfile(fpath):
                with open(fpath, 'r', encoding='utf-8') as f:
                    self.send_json({"name": name, "content": f.read()})
            else:
                self.send_error(404)
        elif self.path == '/api/ai/uploads':
            upload_root = os.path.normpath(os.path.join(_BASE_DIR, '.ark', 'uploads'))
            items = []
            if os.path.isdir(upload_root):
                for name in sorted(os.listdir(upload_root), reverse=True):
                    full = os.path.join(upload_root, name)
                    if not os.path.isfile(full):
                        continue
                    rel = os.path.relpath(full, _BASE_DIR)
                    items.append({
                        "name": name,
                        "path": rel,
                        "size": os.path.getsize(full),
                        "mtime": int(os.path.getmtime(full)),
                    })
            self.send_json({"status": "ok", "uploads": items})
            return
        elif self.path == '/api/ai/uploads/serve':
            qs = parse_qs(urlparse(self.path).query)
            rel = (qs.get('path', [''])[0] or '').strip()
            full = os.path.normpath(os.path.join(_BASE_DIR, rel)) if rel else ''
            upload_root = os.path.normpath(os.path.join(_BASE_DIR, '.ark', 'uploads'))
            if full and full.startswith(upload_root) and os.path.isfile(full):
                ext = os.path.splitext(full)[1].lower()
                mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}.get(ext, 'application/octet-stream')
                with open(full, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)
            return
        elif self.path == '/api/ai/serve':
            qs = parse_qs(urlparse(self.path).query)
            rel = (qs.get('path', [''])[0] or '').strip()
            full = os.path.normpath(os.path.join(_BASE_DIR, rel)) if rel else ''
            ark_root = os.path.normpath(os.path.join(_BASE_DIR, '.ark'))
            if full and full.startswith(ark_root) and os.path.isfile(full):
                ext = os.path.splitext(full)[1].lower()
                mime = 'video/mp4' if ext == '.mp4' else 'image/jpeg'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(os.path.getsize(full)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                with open(full, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
            return
        elif urlparse(self.path).path == '/api/preview/status':
            qs = parse_qs(urlparse(self.path).query)
            magnet = unquote(qs.get('magnet', [''])[0])
            self.send_json(preview_status(magnet))
        elif urlparse(self.path).path == '/api/preview':
            qs = parse_qs(urlparse(self.path).query)
            magnet = unquote(qs.get('magnet', [''])[0])
            handle_preview_stream(self, magnet)
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))

        if self.path == '/api/file/upload':
            import cgi
            content_type = self.headers.get('Content-Type', '')
            env = {'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type, 'CONTENT_LENGTH': str(content_length)}
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=env)
            purpose = (form.getvalue('purpose') or '').strip()
            target_dir = form.getvalue('dir', '') or ''
            uploaded = []
            file_items = form['files'] if 'files' in form else []
            if not isinstance(file_items, list):
                file_items = [file_items]

            # AI 视频角色图：保存到 .ark/uploads/，Lisp 端通过返回的 path 直接引用
            if purpose == 'ai_video':
                upload_root = os.path.normpath(os.path.join(_BASE_DIR, '.ark', 'uploads'))
                os.makedirs(upload_root, exist_ok=True)
                for item in file_items:
                    if not item.filename:
                        continue
                    ext = os.path.splitext(item.filename)[1].lower() or '.jpg'
                    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                        ext = '.jpg'
                    safe_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
                    fpath = os.path.join(upload_root, safe_name)
                    with open(fpath, 'wb') as f:
                        f.write(item.file.read())
                    rel = os.path.relpath(fpath, _BASE_DIR)
                    uploaded.append(rel)
                self.send_json({"status": "ok", "files": uploaded, "purpose": purpose})
                return

            # 默认：保存到 examples/（兼容旧行为）
            examples_dir = os.path.normpath(os.path.join(_BASE_DIR, 'examples'))
            for item in file_items:
                if item.filename:
                    fname = os.path.basename(item.filename)
                    fpath = os.path.normpath(os.path.join(examples_dir, target_dir, fname))
                    if fpath.startswith(examples_dir):
                        os.makedirs(os.path.dirname(fpath), exist_ok=True)
                        with open(fpath, 'wb') as f:
                            f.write(item.file.read())
                        uploaded.append(os.path.join(target_dir, fname) if target_dir else fname)
            self.send_json({"status": "ok", "files": uploaded, "purpose": purpose or "examples"})
            return

        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path == '/api/chat':
            prompt = (data.get('prompt') or data.get('message') or '').strip()
            if not prompt:
                self.send_json({"status": "error", "message": "请提供提示词"})
                return
            from workflow.llm import call_llm
            merged = _get_merged_api_keys()
            key = merged.get("deepseek", "")
            try:
                reply = call_llm(
                    prompt,
                    config={"api_key": key, "temperature": 0.1, "max_tokens": 256} if key else {},
                )
                self.send_json({"status": "ok", "reply": reply})
            except Exception as e:
                self.send_json({"status": "error", "message": format_user_error(e)})

        elif self.path == '/api/config':
            provider = (data.get('provider') or 'deepseek').strip().lower()

            # 可灵特殊：支持拆分 Access Key / Secret Key 两字段
            if provider == 'kling':
                self._handle_kling_config(data)
                return

            new_key = (data.get('api_key') or '').strip()

            if data.get('clear'):
                _clear_provider_api_key(provider)
                set_api_key_provider(lambda: _get_merged_api_keys().get("deepseek", ""))
                set_ai_api_keys_provider(_get_merged_api_keys)
                update_llm_env()
                print(f"[HTTP] 已清除 {provider} API 密钥")
                self.send_json({"status": "ok", "message": f"{provider} API 密钥已清除"})
            elif new_key:
                _save_provider_api_key(provider, new_key)
                set_api_key_provider(lambda: _get_merged_api_keys().get("deepseek", ""))
                set_ai_api_keys_provider(_get_merged_api_keys)
                update_llm_env()
                masked = _mask_api_key(new_key)
                print(f"[HTTP] {provider} API 密钥已更新 ({masked})")
                self.send_json({"status": "ok", "message": f"{provider} API 密钥已设置"})
            else:
                self.send_json({"status": "error", "message": "请提供有效的 API 密钥"})

        elif self.path == '/api/execute':
            self._handle_execute(data)

        elif self.path == '/api/stop':
            client_id = str(data.get('client_id') or '').strip()
            active = _get_active_session()
            if active and client_id and active.client_id != client_id:
                self.send_json({"status": "error", "message": "当前执行由其他客户端发起，无法从此处终止"})
                return
            _terminate_active_execution()
            self.send_json({"status": "stopped"})

        elif self.path == '/api/input':
            client_id = str(data.get('client_id') or '').strip()
            active = _get_active_session()
            if not active:
                self.send_json({"status": "error", "message": "当前没有等待输入的执行"})
                return
            if client_id and active.client_id != client_id:
                self.send_json({"status": "error", "message": "输入与当前执行客户端不匹配"})
                return
            value = data.get('input')
            if value is None:
                value = data.get('value', '')
            active.input_queue.put(str(value))
            self.send_json({"status": "ok"})

        elif self.path == '/api/file/save':
            name = data.get('name', '')
            content = data.get('content', '')
            if name:
                examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
                fpath = os.path.normpath(os.path.join(examples_dir, name))
                if fpath.startswith(examples_dir):
                    os.makedirs(os.path.dirname(fpath), exist_ok=True)
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    active = _get_active_session()
                    if active and os.environ.get("ZHIYU_RUNTIME", "zhiyu").lower() != "legacy":
                        try:
                            from workflow.zhiyu_runner import reload_zhiyu_file
                            rel = os.path.relpath(fpath, examples_dir)
                            reload_zhiyu_file(active, rel)
                        except Exception:
                            pass
                    self.send_json({"status": "ok"})
                else:
                    self.send_json({"status": "error", "message": "路径无效"})
            else:
                self.send_json({"status": "error", "message": "文件名无效"})

        elif self.path == '/api/file/create':
            name = data.get('name', '')
            if not name:
                self.send_json({"status": "error", "message": "名称不能为空"})
                return
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            fpath = os.path.normpath(os.path.join(examples_dir, name))
            if not fpath.startswith(examples_dir):
                self.send_json({"status": "error", "message": "路径无效"})
            elif not os.path.exists(fpath):
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write('')
                self.send_json({"status": "ok", "name": name})
            else:
                self.send_json({"status": "error", "message": "文件已存在"})

        elif self.path == '/api/dir/create':
            name = data.get('name', '')
            if not name:
                self.send_json({"status": "error", "message": "名称不能为空"})
                return
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            dpath = os.path.normpath(os.path.join(examples_dir, name))
            if not dpath.startswith(examples_dir):
                self.send_json({"status": "error", "message": "路径无效"})
            elif not os.path.exists(dpath):
                os.makedirs(dpath)
                self.send_json({"status": "ok"})
            else:
                self.send_json({"status": "error", "message": "文件夹已存在"})

        elif self.path == '/api/file/delete':
            name = data.get('name', '')
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            fpath = os.path.normpath(os.path.join(examples_dir, name))
            if os.path.exists(fpath) and fpath.startswith(examples_dir) and fpath != examples_dir:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                elif os.path.isdir(fpath):
                    import shutil
                    shutil.rmtree(fpath)
                self.send_json({"status": "ok"})
            else:
                self.send_json({"status": "error", "message": "文件未找到"})

        elif self.path == '/api/file/rename':
            old_name = data.get('old', '')
            new_name = data.get('new', '')
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            old_path = os.path.normpath(os.path.join(examples_dir, old_name))
            new_path = os.path.normpath(os.path.join(examples_dir, new_name))
            if not old_path.startswith(examples_dir) or not new_path.startswith(examples_dir):
                self.send_json({"status": "error", "message": "路径无效"})
            elif not os.path.exists(old_path):
                self.send_json({"status": "error", "message": "源文件未找到"})
            elif os.path.exists(new_path):
                self.send_json({"status": "error", "message": "目标已存在"})
            else:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.rename(old_path, new_path)
                self.send_json({"status": "ok", "name": new_name})

        elif self.path == '/api/file/duplicate':
            import shutil
            name = data.get('name', '')
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            src_path = os.path.normpath(os.path.join(examples_dir, name))
            if not src_path.startswith(examples_dir) or not os.path.exists(src_path):
                self.send_json({"status": "error", "message": "文件未找到"})
            else:
                base, ext = os.path.splitext(src_path)
                copy_path = base + "_副本" + ext
                i = 2
                while os.path.exists(copy_path):
                    copy_path = base + f"_副本{i}" + ext
                    i += 1
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, copy_path)
                else:
                    shutil.copy2(src_path, copy_path)
                rel = os.path.relpath(copy_path, examples_dir)
                self.send_json({"status": "ok", "name": rel})

    def _handle_execute(self, data):
        """处理 /api/execute 请求"""
        client_id = str(data.get('client_id') or '').strip()
        code = data.get('code', '')
        is_markdown = data.get('markdown', False)
        inputs = data.get('inputs') if isinstance(data.get('inputs'), dict) else None

        session = _start_execution(client_id, code, is_markdown, inputs=inputs)

        self.send_response(200)
        self.send_header('Content-type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache, no-transform')
        self.send_header('Connection', 'keep-alive')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

        try:
            self.wfile.write(f"data: __SESSION__:{session.id}\n\n".encode())
            self.wfile.flush()

            while True:
                if session.stopped() and session.output_queue.empty():
                    try:
                        self.wfile.write(b"data: __STOPPED__\n\n")
                        self.wfile.flush()
                    except Exception:
                        pass
                    break
                try:
                    msg = session.output_queue.get(timeout=1.0)

                    if msg in ("__DONE__", "__STOPPED__"):
                        self.wfile.write(f"data: {msg}\n\n".encode())
                        self.wfile.flush()
                        break
                    if msg.startswith("__ERROR__:"):
                        self.wfile.write(f"data: {msg}\n\n".encode())
                        self.wfile.flush()
                        break
                    self.wfile.write(f"data: {msg}\n\n".encode())
                    self.wfile.flush()

                except queue.Empty:
                    active = _get_active_session()
                    if active is not session:
                        try:
                            self.wfile.write(b"data: __STOPPED__\n\n")
                            self.wfile.flush()
                        except Exception:
                            pass
                        break
                    if session.thread and not session.thread.is_alive():
                        if session.output_queue.empty():
                            try:
                                self.wfile.write(b"data: __DONE__\n\n")
                                self.wfile.flush()
                            except Exception:
                                pass
                            break
                    try:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                    except Exception:
                        break

        except Exception as e:
            try:
                self.wfile.write(f"data: __ERROR__:{format_user_error(e)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")




def main():
    port = 8080
    print("=" * 50)
    print("Lisp 工作流 Web 界面")
    print("=" * 50)
    if not _ARIA2_AVAILABLE:
        print(_ARIA2_HINT)
    print(f"\\n服务器: http://localhost:{port}")
    print("按 Ctrl+C 停止\\n")

    class ThreadedServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
    server = ThreadedServer(('localhost', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\n服务器已停止")


if __name__ == "__main__":
    main()
