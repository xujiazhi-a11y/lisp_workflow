"""
多 Provider AI 服务：文本 / 图像 / 视频生成，以及视频拼接。
供 workflow_lisp 内置函数调用。
"""

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

# 与 workflow_lisp.BASE_DIR 一致（py/ 目录）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_IMAGES_DIR = os.path.join(_BASE_DIR, ".ark", "tmp", "ai_images")
AI_VIDEOS_DIR = os.path.join(_BASE_DIR, ".ark", "tmp", "ai_videos")

PROVIDER_CHAT = {
    "deepseek": "https://api.deepseek.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
}

KLING_API_BASE = "https://api-beijing.klingai.com"
KLING_DEFAULT_MODEL = "kling-v2-1"
ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_VIDEO_MODEL = "cogvideox-3"

_api_keys_provider: Optional[Callable[[], Dict[str, str]]] = None


def set_api_keys_provider(fn: Callable[[], Dict[str, str]]) -> None:
    global _api_keys_provider
    _api_keys_provider = fn


def _keys() -> Dict[str, str]:
    if _api_keys_provider:
        return _api_keys_provider() or {}
    return {}


def _require_key(provider: str) -> str:
    key = (_keys().get(provider) or "").strip()
    if not key and provider == "deepseek":
        key = (
            os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
    if not key and provider == "siliconflow":
        key = (os.environ.get("SILICONFLOW_API_KEY") or "").strip()
    if not key and provider == "kling":
        # 旧版单 key 兼容：env `KLING_API_KEY=ak:sk`
        key = (os.environ.get("KLING_API_KEY") or "").strip()
    if not key and provider == "zhipu":
        key = (os.environ.get("ZHIPU_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            f"未配置 {provider} 的 API 密钥，请在设置中配置 api_keys.{provider}"
        )
    return key


def _require_kling_pair() -> Tuple[str, str]:
    """获取可灵 Access Key + Secret Key（每次调用现场组合，JWT 不缓存）。

    支持以下来源（按优先级）：
      1. Provider 回调返回 `kling_ak` + `kling_sk` 字段
      2. Provider 回调返回 `kling="ak:sk"` 单字段（向后兼容）
      3. 环境变量 `KLING_AK` + `KLING_SK`
      4. 环境变量 `KLING_API_KEY="ak:sk"`（向后兼容）
    """
    keys = _keys() or {}
    ak = (keys.get("kling_ak") or keys.get("kling_ak".upper()) or "").strip()
    sk = (keys.get("kling_sk") or keys.get("kling_sk".upper()) or "").strip()
    if not (ak and sk):
        legacy = (keys.get("kling") or "").strip()
        if ":" in legacy:
            ak, sk = (s.strip() for s in legacy.split(":", 1))
    if not (ak and sk):
        ak = (os.environ.get("KLING_AK") or "").strip()
        sk = (os.environ.get("KLING_SK") or os.environ.get("KLING_SECRET_KEY") or "").strip()
    if not (ak and sk):
        legacy = (os.environ.get("KLING_API_KEY") or "").strip()
        if ":" in legacy:
            ak, sk = (s.strip() for s in legacy.split(":", 1))
    if not (ak and sk):
        raise ValueError(
            "未配置可灵 API 密钥对，请设置 api_keys.kling_ak 与 api_keys.kling_sk "
            "（或环境变量 KLING_AK / KLING_SK，或 api_keys.kling=ak:sk 兼容写法）"
        )
    return ak, sk


def _resolve_path(path: str) -> str:
    if not path:
        raise ValueError("路径不能为空")
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(_BASE_DIR, path))


def _rel_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    base = os.path.abspath(_BASE_DIR)
    if abs_path.startswith(base + os.sep):
        return abs_path[len(base) + 1 :]
    return abs_path


def _image_to_data_url(path: str) -> str:
    abs_path = _resolve_path(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"图片不存在: {path}")
    mime, _ = mimetypes.guess_type(abs_path)
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    with open(abs_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _image_to_base64(path: str) -> str:
    abs_path = _resolve_path(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"图片不存在: {path}")
    with open(abs_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _parse_lisp_kw_args(args: tuple) -> Tuple[List[Any], Dict[str, Any]]:
    """解析 Lisp 关键字参数，如 :image path"""
    positional: List[Any] = []
    kwargs: Dict[str, Any] = {}
    i = 0
    while i < len(args):
        a = args[i]
        key = None
        if hasattr(a, "__str__") and not isinstance(a, (int, float, bool, list, dict)):
            s = str(a)
            if s.startswith(":"):
                key = s[1:]
        if key is not None:
            if i + 1 >= len(args):
                raise ValueError(f"缺少 {key} 的参数值")
            kwargs[key] = args[i + 1]
            i += 2
        else:
            positional.append(a)
            i += 1
    return positional, kwargs


def _chat_request(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    image: Optional[str] = None,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if image:
        content = [
            {"type": "text", "text": str(prompt)},
            {"type": "image_url", "image_url": {"url": _image_to_data_url(image)}},
        ]
    else:
        content = str(prompt)

    payload = {
        "model": str(model),
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=(10, 120),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"AI 文本请求失败 ({resp.status_code}): {resp.text}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def ai_text(
    provider: str,
    model: str,
    prompt: str,
    image: Optional[str] = None,
) -> str:
    provider = str(provider).strip().lower()
    if provider not in PROVIDER_CHAT:
        raise ValueError(
            f"不支持的文本服务提供商：{provider}，可用：deepseek、siliconflow"
        )
    api_key = _require_key(provider)
    base_url = PROVIDER_CHAT[provider]
    return _chat_request(base_url, api_key, model, prompt, image=image)


def ai_image(
    provider: str,
    model: str,
    prompt: str,
    ref_image: Optional[str] = None,
) -> str:
    provider = str(provider).strip().lower()
    if provider != "siliconflow":
        raise ValueError(f"不支持的图像服务提供商：{provider}，可用：siliconflow")

    api_key = _require_key("siliconflow")
    payload: Dict[str, Any] = {
        "model": str(model),
        "prompt": str(prompt),
        "image_size": "1024x1024",
        "batch_size": 1,
    }
    if ref_image:
        payload["image"] = _image_to_data_url(ref_image)

    resp = requests.post(
        "https://api.siliconflow.cn/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=(10, 180),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"AI 图像请求失败 ({resp.status_code}): {resp.text}")

    data = resp.json()
    images = data.get("images") or []
    if not images:
        raise RuntimeError(f"AI 图像未返回结果: {data}")

    url = images[0].get("url") or images[0].get("b64_json")
    os.makedirs(AI_IMAGES_DIR, exist_ok=True)
    ext = ".png"
    out_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
    out_path = os.path.join(AI_IMAGES_DIR, out_name)

    if url and str(url).startswith("http"):
        img_resp = requests.get(url, timeout=(10, 120))
        img_resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(img_resp.content)
    elif url:
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(url))
    else:
        raise RuntimeError(f"无法解析图像响应: {images[0]}")

    return _rel_path(out_path)


def _kling_jwt(access_key: str, secret_key: str) -> str:
    try:
        import jwt as pyjwt

        now = int(time.time())
        return pyjwt.encode(
            {"iss": access_key, "exp": now + 1800, "nbf": now - 5},
            secret_key,
            algorithm="HS256",
            headers={"alg": "HS256", "typ": "JWT"},
        )
    except ImportError:
        pass

    def _b64url(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = _b64url(
        json.dumps(
            {"iss": access_key, "exp": now + 1800, "nbf": now - 5},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


def _kling_headers(access_key: str, secret_key: str) -> Dict[str, str]:
    token = _kling_jwt(access_key, secret_key)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _parse_kling_key(key: str) -> Tuple[str, str]:
    if ":" not in key:
        raise ValueError(
            "Kling API 密钥格式应为 access_key:secret_key，请在设置中配置 api_keys.kling"
        )
    access_key, secret_key = key.split(":", 1)
    access_key = access_key.strip()
    secret_key = secret_key.strip()
    if not access_key or not secret_key:
        raise ValueError(
            "Kling API 密钥格式应为 access_key:secret_key，请在设置中配置 api_keys.kling"
        )
    return access_key, secret_key


def _zhipu_video_create(api_key: str, image_path: str, prompt: str, duration: int = 5) -> str:
    """智谱清影图生视频：提交任务，返回任务 ID。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # 图片转 base64
    image_data = _image_to_base64(image_path)
    image_url = f"data:image/jpeg;base64,{image_data}"
    
    payload = {
        "model": ZHIPU_VIDEO_MODEL,
        "prompt": str(prompt)[:512],  # 不超过 512 字符
        "image_url": image_url,
        "quality": "speed",  # 速度优先
        "duration": str(duration),
    }
    
    resp = requests.post(
        f"{ZHIPU_API_BASE}/videos/generations",
        headers=headers,
        json=payload,
        timeout=(10, 60),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"智谱清影视频任务创建失败 ({resp.status_code}): {resp.text}")
    
    data = resp.json()
    task_id = data.get("id")
    if not task_id:
        raise RuntimeError(f"智谱清影未返回任务 ID: {data}")
    
    return task_id


def _zhipu_video_poll(api_key: str, task_id: str, timeout_sec: int = 300) -> str:
    """轮询智谱清影任务状态，返回视频本地路径。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    query_url = f"{ZHIPU_API_BASE}/async-result/{task_id}"
    poll_interval = 10
    start = time.time()
    
    while True:
        elapsed = int(time.time() - start)
        if elapsed > timeout_sec:
            raise TimeoutError(f"智谱清影视频生成超时（{timeout_sec} 秒），任务 ID: {task_id}")
        
        resp = requests.get(query_url, headers=headers, timeout=(10, 30))
        if resp.status_code != 200:
            raise RuntimeError(f"智谱清影任务查询失败 ({resp.status_code}): {resp.text}")
        
        data = resp.json()
        task_status = data.get("task_status", "")
        print(f"[zhipu-video] [{elapsed}s] 状态: {task_status}")
        
        if task_status == "SUCCESS":
            video_result = data.get("video_result") or []
            if not video_result:
                raise RuntimeError("智谱清影任务完成但未返回视频")
            video_url = video_result[0].get("url")
            if not video_url:
                raise RuntimeError("智谱清影返回的视频 URL 为空")
            
            os.makedirs(AI_VIDEOS_DIR, exist_ok=True)
            out_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.mp4"
            out_path = os.path.join(AI_VIDEOS_DIR, out_name)
            
            print(f"[zhipu-video] 下载视频...")
            vresp = requests.get(video_url, stream=True, timeout=(10, 300))
            vresp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in vresp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[zhipu-video] 已保存: {_rel_path(out_path)}")
            return _rel_path(out_path)
        
        if task_status == "FAIL":
            raise RuntimeError(f"智谱清影视频生成失败: {data}")
        
        if task_status not in ("PROCESSING", "PENDING"):
            print(f"[zhipu-video] 未知状态: {task_status}, 继续等待...")
        
        time.sleep(poll_interval)


def ai_video(
    provider: str,
    first_frame: str,
    last_frame: str,
    prompt: str,
    duration,
    model: str = KLING_DEFAULT_MODEL,
) -> str:
    provider = str(provider).strip().lower()
    
    # 智谱清影：仅首帧，忽略尾帧
    if provider == "zhipu":
        api_key = _require_key("zhipu")
        dur = int(duration) if duration is not None else 5
        if dur not in (5, 10):
            dur = 5
        task_id = _zhipu_video_create(api_key, first_frame, prompt, duration=dur)
        print(f"[zhipu-video] 任务已提交: {task_id}")
        return _zhipu_video_poll(api_key, task_id)
    
    # 可灵：支持首尾帧
    if provider != "kling":
        raise ValueError(f"不支持的视频服务提供商：{provider}，可用：kling, zhipu")

    key = _require_key("kling")
    # 新写法：直接从 kling_ak + kling_sk 取；旧写法：拆 ak:sk
    try:
        access_key, secret_key = _require_kling_pair()
    except ValueError:
        access_key, secret_key = _parse_kling_key(key)
    headers = _kling_headers(access_key, secret_key)

    dur = str(int(duration)) if duration is not None else "5"
    if dur not in ("5", "10"):
        dur = "5"

    body = {
        "model_name": str(model),
        "image": _image_to_base64(first_frame),
        "image_tail": _image_to_base64(last_frame),
        "prompt": str(prompt),
        "duration": dur,
        "mode": "std",
    }

    create_url = f"{KLING_API_BASE}/v1/videos/image2video"
    resp = requests.post(create_url, headers=headers, json=body, timeout=(10, 60))
    if resp.status_code != 200:
        raise RuntimeError(f"Kling 视频任务创建失败 ({resp.status_code}): {resp.text}")

    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Kling 视频任务创建失败: {result.get('message', result)}")

    task_id = result["data"]["task_id"]
    print(f"[ai-video] 任务已提交: {task_id}")

    query_url = f"{KLING_API_BASE}/v1/videos/image2video/{task_id}"
    timeout_sec = 300
    poll_interval = 10
    start = time.time()

    while True:
        elapsed = int(time.time() - start)
        if elapsed > timeout_sec:
            raise TimeoutError(f"Kling 视频生成超时（{timeout_sec} 秒），任务 ID: {task_id}")

        qresp = requests.get(query_url, headers=headers, timeout=(10, 30))
        if qresp.status_code != 200:
            raise RuntimeError(f"Kling 任务查询失败 ({qresp.status_code}): {qresp.text}")

        qdata = qresp.json()
        if qdata.get("code") != 0:
            raise RuntimeError(f"Kling 任务查询失败: {qdata.get('message', qdata)}")

        task = qdata["data"]
        status = task.get("task_status", "")
        print(f"[ai-video] [{elapsed}s] 状态: {status}")

        if status == "succeed":
            videos = (task.get("task_result") or {}).get("videos") or []
            if not videos:
                raise RuntimeError("Kling 任务完成但未返回视频")
            video_url = videos[0].get("url")
            if not video_url:
                raise RuntimeError("Kling 返回的视频 URL 为空")

            os.makedirs(AI_VIDEOS_DIR, exist_ok=True)
            out_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.mp4"
            out_path = os.path.join(AI_VIDEOS_DIR, out_name)

            print(f"[ai-video] 下载视频...")
            vresp = requests.get(video_url, stream=True, timeout=(10, 300))
            vresp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in vresp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"[ai-video] 已保存: {_rel_path(out_path)}")
            return _rel_path(out_path)

        if status == "failed":
            msg = task.get("task_status_msg") or "未知错误"
            raise RuntimeError(f"Kling 视频生成失败: {msg}")

        if status not in ("submitted", "processing", "pending"):
            raise RuntimeError(f"Kling 未知任务状态: {status}")

        time.sleep(poll_interval)


def video_concat(video_paths, output_path: str) -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg，请先安装 ffmpeg 并确保已加入系统 PATH")

    if isinstance(video_paths, (str, bytes)):
        paths = [video_paths]
    else:
        paths = list(video_paths)

    if len(paths) < 2:
        raise ValueError("视频拼接至少需要 2 个视频路径")

    resolved = []
    for p in paths:
        abs_p = _resolve_path(str(p))
        if not os.path.isfile(abs_p):
            raise FileNotFoundError(f"视频文件不存在: {p}")
        resolved.append(abs_p)

    out_abs = _resolve_path(output_path)
    os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)

    list_fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="concat_")
    try:
        with os.fdopen(list_fd, "w", encoding="utf-8") as f:
            for abs_p in resolved:
                escaped = abs_p.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            out_abs,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"ffmpeg 拼接失败: {err or proc.returncode}")
    finally:
        try:
            os.remove(list_path)
        except OSError:
            pass

    return _rel_path(out_abs)


# ── Lisp 内置函数包装（支持 :image / :ref-image 关键字参数）──


def lisp_ai_text(*args):
    positional, kwargs = _parse_lisp_kw_args(args)
    if len(positional) < 3:
        raise ValueError("(ai-text 提供商 模型 提示词 [:image 图片路径])")
    return ai_text(
        positional[0],
        positional[1],
        positional[2],
        image=kwargs.get("image"),
    )


def lisp_ai_image(*args):
    positional, kwargs = _parse_lisp_kw_args(args)
    if len(positional) < 3:
        raise ValueError("(ai-image 提供商 模型 提示词 [:ref-image 参考图路径])")
    import time as _t
    _t.sleep(2)  # 限流保护：Z-Image-Turbo 实测单次 4-8s，2s 间隔 ≈ 6-10 IPM 稳过
    return ai_image(
        positional[0],
        positional[1],
        positional[2],
        ref_image=kwargs.get("ref-image") or kwargs.get("ref_image"),
    )


def lisp_ai_video(*args):
    positional, _kwargs = _parse_lisp_kw_args(args)
    if len(positional) < 5:
        raise ValueError(
            "(ai-video 提供商 首帧路径 尾帧路径 提示词 时长)"
        )
    return ai_video(
        positional[0],
        positional[1],
        positional[2],
        positional[3],
        positional[4],
    )


def lisp_video_concat(video_paths, output_path):
    return video_concat(video_paths, output_path)


def slideshow_video(image_paths, output_path, total_duration, title=""):
    """ffmpeg 静帧拼视频（降级路径）：每张图按比例分配时长，加 Ken Burns 缩放 + 字幕。"""
    import subprocess
    if not image_paths:
        raise ValueError("slideshow_video: 至少需要 1 张图片")
    os.makedirs(os.path.dirname(_resolve_path(output_path)) or ".", exist_ok=True)
    n = len(image_paths)
    per = max(0.5, total_duration / n)
    # 用 scale + zoompan 让每张图有缓慢推近效果；用 drawtext 加字幕
    # 我们用 concat demuxer + xfade 让过渡更丝滑
    inputs = []
    for p in image_paths:
        abs_p = _resolve_path(p)
        inputs.extend(["-loop", "1", "-t", f"{per:.3f}", "-i", abs_p])

    # 滤镜：每张图缩放到 1024x1024，加 zoompan（缓慢推近），最后一张加字幕
    parts = []
    last = ""
    for i in range(n):
        scale = f"[{i}:v]scale=1024:1024:force_original_aspect_ratio=decrease,pad=1024:1024:(ow-iw)/2:(oh-ih)/2:black,setsar=1,zoompan=z='min(zoom+0.0008,1.15)':d={int(per*25)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1024x1024[v{i}]"
        parts.append(scale)
        last = f"[v{i}]"
    # 全部拼接
    if n == 1:
        out = last
    else:
        # 用 xfade 串联
        seg_dur = per
        # 构建 xfade 链
        cur = "[v0]"
        offset = seg_dur
        for i in range(1, n):
            nxt = f"[v{i}]"
            out_label = f"[x{i}]" if i < n - 1 else "[vout]"
            parts.append(f"{cur}{nxt}xfade=transition=fade:duration=0.4:offset={max(0, offset-0.4):.3f}{out_label}")
            cur = out_label
            offset += seg_dur
        out = cur

    if title:
        safe = title.replace(":", r"\:").replace("'", r"\'")
        parts.append(f"{out}drawtext=text='{safe}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.5:boxborderw=10:x=(w-text_w)/2:y=h-100[vfinal]")
        out = "[vfinal]"

    # 音频轨：静音
    filter_complex = ";\n".join(parts)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           *inputs,
           "-f", "lavfi", "-t", f"{total_duration:.3f}", "-i", "anullsrc=r=44100:cl=stereo",
           "-filter_complex", filter_complex,
           "-map", out, "-map", f"[{n}:a]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k",
           "-t", f"{total_duration:.3f}",
           _resolve_path(output_path)]
    print(f"[slideshow] running ffmpeg, n={n} per={per:.2f}s")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败 ({proc.returncode}): {proc.stderr[:500]}")
    return _rel_path(_resolve_path(output_path))


def lisp_slideshow_video(*args):
    """(slideshow-video 图列表 输出路径 总时长 [:title 标题])"""
    positional, kwargs = _parse_lisp_kw_args(args)
    if len(positional) < 3:
        raise ValueError("(slideshow-video 图列表 输出路径 总时长 [:title 标题])")
    image_paths = positional[0]
    output_path = positional[1]
    total_duration = float(positional[2])
    title = kwargs.get("title", "")
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    return slideshow_video(image_paths, output_path, total_duration, title=title)
