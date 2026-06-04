#!/usr/bin/env python3
"""
工作流 Lisp Web 服务器 - 简化版
"""

import os
import sys
import json
import threading
import queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_lisp import run as run_lisp, GLOBAL_ENV, to_lisp_str, to_symbol, _CN_ALIASES
import workflow_lisp

# 全局状态
_server_api_key = ""
execution_lock = threading.Lock()
output_queue = queue.Queue()
current_thread = None
should_stop = False
markdown_mode = False  # Markdown 渲染模式


def _make_llm_fn():
    """创建使用服务端 API Key 的 call-llm 函数"""
    from workflow.llm import call_llm
    key = _server_api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    if key:
        return lambda prompt: call_llm(prompt, config={"api_key": key})
    return lambda prompt: call_llm(prompt)  # 无 key 时走 mock 模式


def update_llm_env():
    """更新 Lisp 全局环境中的 call-llm，注入当前 API Key"""
    fn = _make_llm_fn()
    GLOBAL_ENV['call-llm'] = fn
    GLOBAL_ENV['llm'] = fn
    GLOBAL_ENV[to_symbol('调用模型')] = fn


# 飞书 Webhook 配置
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/422435e3-a5eb-489d-b410-35e5293d3df6"

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


# 初始化时注入
update_llm_env()


def stream_print(*args):
    """流式打印 - 支持多个参数"""
    global should_stop, markdown_mode
    if not should_stop:
        text = ' '.join(str(a) for a in args)
        prefix = "__MD__:" if markdown_mode else "__TEXT__:"
        escaped = text.replace('\n', '↎')
        output_queue.put(f"{prefix}{escaped}")


def execute_code(code: str, is_markdown=False):
    """在独立线程中执行代码"""
    global should_stop, markdown_mode
    markdown_mode = is_markdown
    
    try:
        # 每次执行前更新 LLM 环境（确保使用最新的 API Key）
        update_llm_env()
        
        # 替换 print 函数
        GLOBAL_ENV['print'] = stream_print
        GLOBAL_ENV[to_symbol('打印')] = stream_print
        GLOBAL_ENV[to_symbol('输出')] = stream_print
        
        # 设置 BASE_DIR 为 examples 目录
        workflow_lisp.BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples')
        workflow_lisp._loaded_files = set()

        # 执行代码
        result = run_lisp(code)
        
        if not should_stop and result is not None:
            result_str = str(result).replace('\n', '↎')
            output_queue.put(f"__RESULT__:{result_str}")
        
        output_queue.put("__DONE__")
        
    except Exception as e:
        if not should_stop:
            output_queue.put(f"__ERROR__:{type(e).__name__}: {str(e)}")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path.startswith('/?'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path == '/api/status':
            self.send_json({
                "status": "ok",
                "api_key_set": bool(_server_api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
            })
        elif self.path == '/api/config':
            # 只返回 key 是否已设置，不返回 key 本身
            self.send_json({
                "api_key_set": bool(_server_api_key),
                "masked_key": (_server_api_key[:4] + "****" + _server_api_key[-4:]) if len(_server_api_key) > 8 else ("****" if _server_api_key else "")
            })
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
        else:
            self.send_error(404)

    def do_POST(self):
        global current_thread, should_stop, _server_api_key

        content_length = int(self.headers.get('Content-Length', 0))

        if self.path == '/api/file/upload':
            import cgi
            content_type = self.headers.get('Content-Type', '')
            env = {'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type, 'CONTENT_LENGTH': str(content_length)}
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=env)
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            target_dir = form.getvalue('dir', '') or ''
            uploaded = []
            file_items = form['files'] if 'files' in form else []
            if not isinstance(file_items, list):
                file_items = [file_items]
            for item in file_items:
                if item.filename:
                    fname = os.path.basename(item.filename)
                    fpath = os.path.normpath(os.path.join(examples_dir, target_dir, fname))
                    if fpath.startswith(examples_dir):
                        os.makedirs(os.path.dirname(fpath), exist_ok=True)
                        with open(fpath, 'wb') as f:
                            f.write(item.file.read())
                        uploaded.append(os.path.join(target_dir, fname) if target_dir else fname)
            self.send_json({"status": "ok", "files": uploaded})
            return

        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path == '/api/config':
            # 设置 API Key
            new_key = (data.get('api_key') or '').strip()
            if new_key:
                _server_api_key = new_key
                update_llm_env()
                print(f"[HTTP] API Key 已更新 ({new_key[:4]}****{new_key[-4:] if len(new_key)>8 else ''})")
                self.send_json({"status": "ok", "message": "API Key 已设置"})
            elif data.get('clear'):
                _server_api_key = ""
                update_llm_env()
                print("[HTTP] API Key 已清除")
                self.send_json({"status": "ok", "message": "API Key 已清除"})
            else:
                self.send_json({"status": "error", "message": "请提供有效的 API Key"})
        
        elif self.path == '/api/execute':
            # 重置状态
            should_stop = False
            while not output_queue.empty():
                output_queue.get()
            
            # 设置流式响应
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            code = data.get('code', '')
            is_markdown = data.get('markdown', False)
            print(f"[DEBUG] is_markdown = {is_markdown}")
            
            # 启动执行线程
            current_thread = threading.Thread(target=execute_code, args=(code, is_markdown))
            current_thread.start()
            
            # 读取输出并发送
            try:
                while True:
                    try:
                        msg = output_queue.get(timeout=1.0)
                        
                        if msg == "__DONE__":
                            self.wfile.write(b"data: __DONE__\n\n")
                            self.wfile.flush()
                            break
                        elif msg.startswith("__ERROR__:"):
                            self.wfile.write(f"data: {msg}\n\n".encode())
                            self.wfile.flush()
                            break
                        elif msg.startswith("__RESULT__:"):
                            self.wfile.write(f"data: {msg}\n\n".encode())
                            self.wfile.flush()
                        else:
                            self.wfile.write(f"data: {msg}\n\n".encode())
                            self.wfile.flush()
                    
                    except queue.Empty:
                        if not current_thread.is_alive():
                            break
                        continue
            
            except Exception as e:
                self.wfile.write(f"data: __ERROR__:{str(e)}\n\n".encode())
                self.wfile.flush()
        
        elif self.path == '/api/stop':
            should_stop = True
            if current_thread and current_thread.is_alive():
                # 无法真正中断 Python 线程，只能设置标志
                pass
            # 清空队列
            while not output_queue.empty():
                output_queue.get()
            self.send_json({"status": "stopped"})

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
                    self.send_json({"status": "ok"})
                else:
                    self.send_json({"status": "error", "message": "Invalid path"})
            else:
                self.send_json({"status": "error", "message": "Invalid filename"})

        elif self.path == '/api/file/create':
            name = data.get('name', '')
            if not name:
                self.send_json({"status": "error", "message": "Empty name"})
                return
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            fpath = os.path.normpath(os.path.join(examples_dir, name))
            if not fpath.startswith(examples_dir):
                self.send_json({"status": "error", "message": "Invalid path"})
            elif not os.path.exists(fpath):
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write('')
                self.send_json({"status": "ok", "name": name})
            else:
                self.send_json({"status": "error", "message": "File already exists"})

        elif self.path == '/api/dir/create':
            name = data.get('name', '')
            if not name:
                self.send_json({"status": "error", "message": "Empty name"})
                return
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            dpath = os.path.normpath(os.path.join(examples_dir, name))
            if not dpath.startswith(examples_dir):
                self.send_json({"status": "error", "message": "Invalid path"})
            elif not os.path.exists(dpath):
                os.makedirs(dpath)
                self.send_json({"status": "ok"})
            else:
                self.send_json({"status": "error", "message": "Directory already exists"})

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
                self.send_json({"status": "error", "message": "File not found"})

        elif self.path == '/api/file/rename':
            old_name = data.get('old', '')
            new_name = data.get('new', '')
            examples_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples'))
            old_path = os.path.normpath(os.path.join(examples_dir, old_name))
            new_path = os.path.normpath(os.path.join(examples_dir, new_name))
            if not old_path.startswith(examples_dir) or not new_path.startswith(examples_dir):
                self.send_json({"status": "error", "message": "Invalid path"})
            elif not os.path.exists(old_path):
                self.send_json({"status": "error", "message": "Source not found"})
            elif os.path.exists(new_path):
                self.send_json({"status": "error", "message": "Target already exists"})
            else:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.rename(old_path, new_path)
                self.send_json({"status": "ok", "name": new_name})

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")



HTML_PAGE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">
    <title>Lisp Workflow</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/lib/codemirror.min.css">
    <script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/lib/codemirror.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/addon/edit/matchbrackets.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/addon/edit/closebrackets.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body, html { height: 100%; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        body {
            display: grid;
            grid-template-rows: 36px 1fr 22px;
            grid-template-columns: 220px 1fr 1fr;
            background: #1e1e1e; color: #ccc;
        }

        /* Title Bar */
        .titlebar {
            grid-row: 1; grid-column: 1 / -1;
            background: #323233; display: flex; align-items: center; padding: 0 12px; gap: 10px;
            border-bottom: 1px solid #191919; font-size: 12px;
        }
        .titlebar h1 { font-size: 13px; color: #ccc; font-weight: 400; }
        .titlebar-icon { background: transparent; border: none; color: #888; cursor: pointer; font-size: 14px; padding: 4px 8px; border-radius: 3px; }
        .titlebar-icon:hover { color: #fff; background: rgba(255,255,255,0.08); }
        .titlebar .spacer { flex: 1; }
        .titlebar .key-group { display: flex; align-items: center; gap: 4px; }
        .titlebar .key-group input { padding: 3px 8px; background: #3c3c3c; color: #ccc; border: 1px solid #555; border-radius: 3px; font-size: 11px; width: 150px; outline: none; }
        .titlebar .key-group input:focus { border-color: #007acc; }
        .titlebar .key-group button { padding: 3px 8px; background: #3c3c3c; color: #ccc; border: 1px solid #555; border-radius: 3px; cursor: pointer; font-size: 11px; }
        .titlebar .key-group button:hover { background: #505050; }
        .titlebar .key-group button.set { background: #0e639c; color: #fff; border-color: #0e639c; }
        .titlebar .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; background: #3c3c3c; color: #888; }
        .titlebar .status-badge.ok { color: #89d185; }

        /* Sidebar */
        .sidebar {
            grid-row: 2; grid-column: 1;
            background: #252526; display: flex; flex-direction: column;
            border-right: 1px solid #191919; overflow: hidden;
        }
        .sidebar-header { padding: 10px 12px; font-size: 11px; color: #bbb; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase; display: flex; justify-content: space-between; align-items: center; }
        .sidebar .file-list { flex: 1; overflow-y: auto; padding: 2px 0; }
        .sidebar .file-item { padding: 4px 12px; font-size: 12px; color: #ccc; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 5px; }
        .sidebar .file-item:hover { background: #2a2d2e; }
        .sidebar .file-item.active { background: #37373d; color: #fff; }
        .sidebar .file-item .icon { flex-shrink: 0; font-size: 12px; }
        .sidebar .dir-children { display: none; }
        .sidebar .dir-children.open { display: block; }
        .sidebar .new-btn { background: none; border: none; color: #888; cursor: pointer; font-size: 11px; padding: 2px 4px; border-radius: 3px; }
        .sidebar .new-btn:hover { color: #ccc; background: #3c3c3c; }
        .sidebar .inline-input { width: calc(100% - 24px); margin: 4px 12px; padding: 3px 6px; font-size: 12px; border: 1px solid #007acc; border-radius: 3px; background: #1e1e1e; color: #fff; outline: none; box-sizing: border-box; }
        .ctx-menu { position: fixed; z-index: 9999; background: #252526; border: 1px solid #454545; border-radius: 4px; padding: 4px 0; min-width: 120px; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
        .ctx-item { padding: 5px 16px; font-size: 12px; color: #ccc; cursor: pointer; }
        .ctx-item:hover { background: #094771; color: #fff; }
        .sidebar .drag-over { background: rgba(0,122,204,0.15); outline: 2px dashed #007acc; outline-offset: -2px; }

        /* Editor Area */
        .editor-area {
            grid-row: 2; grid-column: 2;
            overflow: hidden; border-right: 1px solid #191919; position: relative;
        }
        .editor-actions {
            position: absolute; top: 8px; right: 14px; z-index: 10;
            display: flex; gap: 4px;
        }
        .editor-actions .btn-run { padding: 4px 12px; border: none; border-radius: 3px; cursor: pointer; font-size: 11px; background: #0e639c; color: #fff; transition: 0.15s; }
        .editor-actions .btn-run:hover { background: #1177bb; }
        .editor-actions .btn-stop { padding: 4px 12px; border: 1px solid #f48771; border-radius: 3px; cursor: pointer; font-size: 11px; background: transparent; color: #f48771; display: none; transition: 0.15s; }
        .editor-actions .btn-stop:hover { background: #f48771; color: #1e1e1e; }
        .CodeMirror { height: 100%; background: #1e1e1e; color: #d4d4d4; font-family: "JetBrains Mono", Monaco, Consolas, monospace; font-size: 13px; line-height: 1.5; }
        .CodeMirror-gutters { background: #1e1e1e; border-right: 1px solid #333; }
        .CodeMirror-linenumber { color: #555; padding: 0 12px 0 8px; }
        .CodeMirror-cursor { border-left: 2px solid #aeafad; }
        .CodeMirror-selected { background: rgba(38, 79, 120, 0.5) !important; }
        .CodeMirror-activeline-background { background: #282828; }
        .CodeMirror-matchingbracket { color: inherit !important; font-weight: bold; background: rgba(255, 215, 0, 0.3); outline: 1px solid rgba(255, 215, 0, 0.7); }
        .cm-matchingbracket-custom { font-weight: bold; background: rgba(255, 215, 0, 0.3); outline: 1px solid rgba(255, 215, 0, 0.7); }
        .cm-file-link { text-decoration: underline; cursor: pointer; }
        .CodeMirror-focused .CodeMirror-selected { background: rgba(38, 79, 120, 0.6) !important; }
        .cm-s-lisp-dark .cm-keyword { color: #c586c0; font-weight: bold; }
        .cm-s-lisp-dark .cm-builtin { color: #dcdcaa; }
        .cm-s-lisp-dark .cm-stdlib { color: #4ec9b0; }
        .cm-s-lisp-dark .cm-string { color: #ce9178; }
        .cm-s-lisp-dark .cm-number { color: #b5cea8; }
        .cm-s-lisp-dark .cm-comment { color: #6a9955; font-style: italic; }
        .cm-s-lisp-dark .cm-atom { color: #569cd6; }
        .cm-s-lisp-dark .cm-variable { color: #9cdcfe; }
        .cm-s-lisp-dark span.cm-bracket-0 { color: #ffd700; }
        .cm-s-lisp-dark span.cm-bracket-1 { color: #da70d6; }
        .cm-s-lisp-dark span.cm-bracket-2 { color: #87cefa; }
        .cm-s-lisp-dark span.cm-bracket-3 { color: #98fb98; }
        .cm-s-lisp-dark span.cm-bracket-4 { color: #ff7f50; }
        .cm-s-lisp-dark span.cm-bracket-5 { color: #dda0dd; }

        /* Output Area */
        .output-area {
            grid-row: 2; grid-column: 3;
            display: flex; flex-direction: column; overflow: hidden; background: #1e1e1e;
        }
        .state-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
        .state-dot.idle { background: #555; }
        .state-dot.running { background: #007acc; animation: pulse 1.2s infinite; }
        .state-dot.done { background: #89d185; }
        .state-dot.error { background: #f48771; }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
        .console-output {
            flex: 1; overflow-y: auto; padding: 4px 0;
            font-family: Monaco, Consolas, monospace; font-size: 12px; line-height: 1.4; min-height: 0;
        }
        .console-output::-webkit-scrollbar { width: 6px; }
        .console-output::-webkit-scrollbar-track { background: transparent; }
        .console-output::-webkit-scrollbar-thumb { background: #424242; border-radius: 3px; }
        .output-line { padding: 1px 12px; border-left: 3px solid transparent; }
        .output-line.type-output { color: #ccc; border-left-color: #333; }
        .output-line.type-result { color: #89d185; border-left-color: #89d185; background: rgba(137,209,133,0.05); padding: 3px 12px; margin: 2px 0; }
        .output-line.type-error { color: #f48771; border-left-color: #f48771; background: rgba(244,135,113,0.05); padding: 3px 12px; margin: 2px 0; }
        .output-line.type-step { border-left-color: #007acc; padding: 2px 12px; margin-top: 3px; }
        .step-badge { font-size: 9px; padding: 1px 5px; border-radius: 3px; background: #264f78; color: #6cb6ff; font-weight: 700; margin-right: 6px; }
        .step-text { color: #aaa; }
        .output-line.type-md { border-left-color: #c586c0; }
        .output-line .md-content { font-family: -apple-system, sans-serif; font-size: 13px; line-height: 1.4; color: #ddd; }
        .output-line .md-content h1, .output-line .md-content h2, .output-line .md-content h3 { color: #569cd6; margin: 0.3em 0 0.2em; font-size: 13px; }
        .output-line .md-content p { margin: 0.2em 0; }
        .output-line .md-content code { background: #333; padding: 1px 4px; border-radius: 2px; font-size: 11px; }

        /* Status Bar */
        .statusbar {
            grid-row: 3; grid-column: 1 / -1;
            background: #007acc; display: flex; align-items: center; padding: 0 10px;
            font-size: 11px; color: #fff; gap: 16px;
        }
        .statusbar .sb-item { display: flex; align-items: center; gap: 4px; }
        .statusbar .sb-spacer { flex: 1; }
        .statusbar button { background: transparent; border: none; color: #fff; cursor: pointer; font-size: 11px; padding: 2px 6px; border-radius: 3px; }
        .statusbar button:hover { background: rgba(255,255,255,0.12); }

        /* Light theme */
        body.theme-light { background: #ffffff; color: #333; }
        body.theme-light .titlebar { background: #f3f3f3; border-bottom-color: #ddd; }
        body.theme-light .titlebar h1 { color: #333; }
        body.theme-light .titlebar .key-group input { background: #fff; color: #333; border-color: #ccc; }
        body.theme-light .titlebar .key-group button { background: #fff; color: #333; border-color: #ccc; }
        body.theme-light .titlebar-icon { color: #555; }
        body.theme-light .titlebar-icon:hover { color: #333; background: rgba(0,0,0,0.06); }
        body.theme-light .titlebar .status-badge { background: #e8e8e8; color: #666; }
        body.theme-light .titlebar .status-badge.ok { color: #16a34a; }
        body.theme-light .sidebar { background: #f3f3f3; border-right-color: #ddd; }
        body.theme-light .sidebar-header { color: #555; }
        body.theme-light .sidebar .file-item { color: #333; }
        body.theme-light .sidebar .file-item:hover { background: #e8e8e8; }
        body.theme-light .sidebar .file-item.active { background: #d4d4d4; color: #000; }
        body.theme-light .sidebar .inline-input { background: #fff; color: #333; border-color: #007acc; }
        body.theme-light .ctx-menu { background: #f3f3f3; border-color: #ccc; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
        body.theme-light .ctx-item { color: #333; }
        body.theme-light .ctx-item:hover { background: #0060c0; color: #fff; }
        body.theme-light .sidebar .drag-over { background: rgba(0,122,204,0.08); }
        body.theme-light .editor-area { border-right-color: #ddd; }
        body.theme-light .CodeMirror { background: #fff; color: #1e1e1e; }
        body.theme-light .CodeMirror-gutters { background: #fff; border-right-color: #eee; }
        body.theme-light .CodeMirror-linenumber { color: #999; }
        body.theme-light .CodeMirror-activeline-background { background: #f8f8f8; }
        body.theme-light .cm-s-lisp-dark .cm-keyword { color: #af00db; }
        body.theme-light .cm-s-lisp-dark .cm-builtin { color: #795e26; }
        body.theme-light .cm-s-lisp-dark .cm-stdlib { color: #267f99; }
        body.theme-light .cm-s-lisp-dark .cm-string { color: #a31515; }
        body.theme-light .cm-s-lisp-dark .cm-number { color: #098658; }
        body.theme-light .cm-s-lisp-dark .cm-comment { color: #008000; }
        body.theme-light .cm-s-lisp-dark .cm-variable { color: #001080; }
        body.theme-light .cm-s-lisp-dark span.cm-bracket-0 { color: #b8860b; }
        body.theme-light .cm-s-lisp-dark span.cm-bracket-1 { color: #7e22ce; }
        body.theme-light .cm-s-lisp-dark span.cm-bracket-2 { color: #1d4ed8; }
        body.theme-light .cm-s-lisp-dark span.cm-bracket-3 { color: #15803d; }
        body.theme-light .cm-s-lisp-dark span.cm-bracket-4 { color: #c2410c; }
        body.theme-light .cm-s-lisp-dark span.cm-bracket-5 { color: #a21caf; }
        body.theme-light .output-area { background: #fff; border-left: 1px solid #ddd; }
        body.theme-light .console-output { background: #fff; }
        body.theme-light .output-line.type-output { color: #333; border-left-color: #e0e0e0; }
        body.theme-light .output-line.type-result { color: #16a34a; border-left-color: #16a34a; background: rgba(22,163,74,0.05); }
        body.theme-light .output-line.type-error { color: #dc2626; border-left-color: #dc2626; background: rgba(220,38,38,0.05); }
        body.theme-light .output-line.type-step { border-left-color: #2563eb; }
        body.theme-light .step-badge { background: #eff6ff; color: #2563eb; }
        body.theme-light .step-text { color: #475569; }
        body.theme-light .output-line.type-md { border-left-color: #7c3aed; }
        body.theme-light .output-line .md-content { color: #1e293b; }
        body.theme-light .output-line .md-content h1, body.theme-light .output-line .md-content h2, body.theme-light .output-line .md-content h3 { color: #1e40af; }
        body.theme-light .output-line .md-content code { background: #f1f5f9; color: #334155; }
        body.theme-light .statusbar { background: #007acc; }
    </style>
</head>
<body>
    <!-- Title Bar -->
    <div class="titlebar">
        <h1>Lisp Workflow</h1>
        <span class="status-badge" id="status">...</span>
        <button class="titlebar-icon" id="themeBtn" onclick="toggleTheme()" title="切换主题">&#9788;</button>
        <div class="spacer"></div>
        <div class="key-group">
            <input type="password" id="apiKeyInput" placeholder="DeepSeek API Key">
            <button onclick="toggleKeyVisibility()" title="显示/隐藏">&#128065;</button>
            <button class="set" id="keySetBtn" onclick="setApiKey()">设置</button>
            <button id="keyClearBtn" onclick="clearApiKey()" style="display:none">清除</button>
        </div>
    </div>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-header">
            <span>Explorer</span>
            <span>
                <button class="new-btn" onclick="startCreateIn('','file')" title="新建文件">📄+</button>
                <button class="new-btn" onclick="startCreateIn('','dir')" title="新建文件夹">📁+</button>
            </span>
        </div>
        <div class="file-list" id="fileList"></div>
    </div>

    <!-- Editor -->
    <div class="editor-area">
        <div class="editor-actions">
            <button class="btn-run" id="runBtn" onclick="runCode()">&#9654; 运行</button>
            <button class="btn-stop" id="stopBtn" onclick="stopCode()">&#9724; 停止</button>
        </div>
        <textarea id="codeArea">;; 点击左侧文件打开</textarea>
    </div>

    <!-- Output -->
    <div class="output-area">
        <div class="console-output" id="consoleOutput"></div>
    </div>

    <!-- Status Bar -->
    <div class="statusbar">
        <span class="sb-item" id="sbFile">未打开文件</span>
        <span class="sb-item" id="sbCursor">行 1, 列 1</span>
        <span class="sb-spacer"></span>
        <span class="sb-item"><span class="state-dot idle" id="stateDot"></span></span>
        <span class="sb-item" id="execTime">0.0s</span>
        <button id="mdModeBtn" onclick="toggleMarkdownMode()">MD: ON</button>
    </div>

    <script>
        // --- Theme ---
        (function() {
            var saved = localStorage.getItem("lisp-theme");
            if (saved === "light") document.body.classList.add("theme-light");
        })();
        function toggleTheme() {
            var isLight = document.body.classList.toggle("theme-light");
            localStorage.setItem("lisp-theme", isLight ? "light" : "dark");
            document.getElementById("themeBtn").innerHTML = isLight ? "&#9790;" : "&#9788;";
        }

        // --- Custom Lisp mode ---
        (function() {
            var KEYWORDS = /^(define|lambda|if|let|begin|pipe|quote|set!|defmacro|map|reduce|filter|load|cond|when|unless|do|and|or|not)$/;
            var KEYWORDS_CN = /^(定义|道|如果|令|开始|引入|引|！赋|映射|归约|过滤|与|或|非)$/;
            var BUILTINS = /^(call-llm|llm|send-to-feishu|str-concat|str-join|str-split|str-replace|str-trim|str-upper|str-lower|str-starts\?|str-ends\?|str-contains\?|format|print|println|pr|parse-json|to-json|extract-json|remove-think|regex-match|regex-replace|read-file|write-file|each|dict|get|put|keys|values|http-post|http-get|pipe|->)$/;
            var BUILTINS_CN = /^(调用模型|发送飞书|打印|输出|格式化|文本拼接|文本连接|文本裁剪|文本包含|文本开头|文本结尾|文本替换|文本分割|转文本|解析JSON|转JSON|提取JSON|去除思考|读文件|写文件|字典|取值|赋值|序列|长度|追加|反转|前项|后项|序对|为空\?|是列表\?|是数字\?|是文本\?|取余)$/;
            var STDLIB = /^(list|cons|car|cdr|first|rest|length|append|reverse|nth|take|drop|null\?|list\?|number\?|string\?|symbol\?|boolean\?|procedure\?|empty\?|dict\?|eq\?|equal\?|mod|str|abs|max|min|floor|ceil|round)$/;
            CodeMirror.defineMode("lisp-workflow", function() {
                return {
                    startState: function() { return { inString: false, depth: 0 }; },
                    token: function(stream, state) {
                        if (state.inString) {
                            while (!stream.eol()) {
                                var ch = stream.next();
                                if (ch === '"') { state.inString = false; return "string"; }
                                if (ch === "\\\\") stream.next();
                            }
                            return "string";
                        }
                        if (stream.eatSpace()) return null;
                        var ch = stream.peek();
                        if (ch === ";") { stream.skipToEnd(); return "comment"; }
                        if (ch === '"') { stream.next(); state.inString = true; return "string"; }
                        if (ch === "(" || ch === "[" || ch === "{" || ch === "【" || ch === "（") {
                            stream.next();
                            var cls = "bracket bracket-" + (state.depth % 6);
                            state.depth++;
                            return cls;
                        }
                        if (ch === ")" || ch === "]" || ch === "}" || ch === "】" || ch === "）") {
                            stream.next();
                            state.depth = Math.max(0, state.depth - 1);
                            return "bracket bracket-" + (state.depth % 6);
                        }
                        if (stream.match(/^#[tf](rue|alse)?\\b/)) return "atom";
                        if (stream.match(/^-?\d+(\.\d+)?/)) return "number";
                        var word = "";
                        while (!stream.eol()) {
                            ch = stream.peek();
                            if (/[\\s()\\[\\]{}\\u3010\\u3011\\uff08\\uff09";'\\\\]/.test(ch)) break;
                            word += stream.next();
                        }
                        if (word) {
                            if (KEYWORDS.test(word) || KEYWORDS_CN.test(word)) return "keyword";
                            if (BUILTINS.test(word) || BUILTINS_CN.test(word)) return "builtin";
                            if (STDLIB.test(word)) return "stdlib";
                            return "variable";
                        }
                        stream.next();
                        return null;
                    }
                };
            });
        })();

        // --- Editor init ---
        var editor = CodeMirror.fromTextArea(document.getElementById("codeArea"), {
            mode: "lisp-workflow", theme: "lisp-dark",
            lineNumbers: true, matchBrackets: true, autoCloseBrackets: true,
            indentUnit: 2, tabSize: 2, indentWithTabs: false,
            lineWrapping: true, styleActiveLine: true,
            extraKeys: {
                "Ctrl-Enter": function() { runCode(); },
                "Cmd-Enter": function() { runCode(); },
                "Esc": function() { if (isRunning) stopCode(); }
            }
        });

        // --- Custom bracket matching for 【】 ---
        (function() {
            var marks = [];
            function clearMarks() { marks.forEach(function(m) { m.clear(); }); marks = []; }
            function findMatch(doc, pos, open, close, dir) {
                var depth = 0, line = pos.line, ch = pos.ch + (dir > 0 ? 1 : 0);
                var lineCount = doc.lineCount();
                while (line >= 0 && line < lineCount) {
                    var text = doc.getLine(line);
                    for (var i = (dir > 0 ? ch : Math.min(ch - 1, text.length - 1)); (dir > 0 ? i < text.length : i >= 0); i += dir) {
                        var c = text.charAt(i);
                        if (c === open) depth++;
                        else if (c === close) depth--;
                        if (depth === 0) return {line: line, ch: i};
                    }
                    line += dir;
                    ch = dir > 0 ? 0 : (line >= 0 && line < lineCount ? doc.getLine(line).length : 0);
                }
                return null;
            }
            editor.on("cursorActivity", function() {
                clearMarks();
                var cur = editor.getCursor(), line = editor.getLine(cur.line);
                var ch = line.charAt(cur.ch), chBefore = cur.ch > 0 ? line.charAt(cur.ch - 1) : "";
                var pos, match;
                if (ch === "【") { pos = {line: cur.line, ch: cur.ch}; match = findMatch(editor.getDoc(), pos, "【", "】", 1); }
                else if (ch === "】") { pos = {line: cur.line, ch: cur.ch}; match = findMatch(editor.getDoc(), {line: cur.line, ch: cur.ch + 1}, "】", "【", -1); }
                else if (chBefore === "】") { pos = {line: cur.line, ch: cur.ch - 1}; match = findMatch(editor.getDoc(), {line: cur.line, ch: cur.ch}, "】", "【", -1); }
                else if (chBefore === "【") { pos = {line: cur.line, ch: cur.ch - 1}; match = findMatch(editor.getDoc(), {line: cur.line, ch: cur.ch - 1}, "【", "】", 1); }
                else { return; }
                if (match) {
                    var cls = "cm-matchingbracket-custom";
                    marks.push(editor.markText(pos, {line: pos.line, ch: pos.ch + 1}, {className: cls}));
                    marks.push(editor.markText(match, {line: match.line, ch: match.ch + 1}, {className: cls}));
                }
            });
        })();

        // --- Cursor status bar ---
        editor.on("cursorActivity", function() {
            var cur = editor.getCursor();
            document.getElementById("sbCursor").textContent = "行 " + (cur.line + 1) + ", 列 " + (cur.ch + 1);
        });

        // --- State ---
        var consoleOutput = document.getElementById("consoleOutput");
        var runBtn = document.getElementById("runBtn");
        var stopBtn = document.getElementById("stopBtn");
        var statusEl = document.getElementById("status");
        var stateDot = document.getElementById("stateDot");
        var execTimeEl = document.getElementById("execTime");
        var sbFile = document.getElementById("sbFile");
        var mdModeBtn = document.getElementById("mdModeBtn");
        var isRunning = false, abortController = null, markdownMode = true;
        var executionTimer = null, startTime = 0, stepCount = 0, lineCount = 0;

        function setExecState(state) { stateDot.className = "state-dot " + state; }
        function startTimer() {
            startTime = performance.now(); stepCount = 0; lineCount = 0;
            execTimeEl.textContent = "0.0s";
            executionTimer = setInterval(function() { execTimeEl.textContent = ((performance.now() - startTime) / 1000).toFixed(1) + "s"; }, 100);
        }
        function stopTimer() { if (executionTimer) { clearInterval(executionTimer); executionTimer = null; } execTimeEl.textContent = ((performance.now() - startTime) / 1000).toFixed(2) + "s"; }

        // --- File tree ---
        var currentFile = "";
        var expandedDirs = {"prompts": true};
        var ctxMenu = null;

        function loadFileList() {
            fetch("/api/files").then(function(r) { return r.json(); }).then(function(d) {
                document.getElementById("fileList").innerHTML = "";
                renderTree(d.tree, document.getElementById("fileList"), "");
            });
        }
        function renderTree(items, container, prefix) {
            items.forEach(function(item) {
                var path = prefix ? prefix + "/" + item.name : item.name;
                var el = document.createElement("div");
                var depth = prefix ? prefix.split("/").length : 0;
                el.style.paddingLeft = (12 + depth * 14) + "px";
                el.setAttribute("data-path", path);
                el.setAttribute("data-type", item.type);
                el.draggable = true;
                el.addEventListener("dragstart", function(e) { e.dataTransfer.setData("text/x-path", path); e.dataTransfer.effectAllowed = "move"; });
                if (item.type === "dir") {
                    el.className = "file-item";
                    var arrow = expandedDirs[path] ? "▼" : "▶";
                    el.innerHTML = '<span class="icon">' + arrow + '</span><span class="icon">📁</span><span class="fname">' + item.name + '</span>';
                    el.onclick = function(e) { if (e.target.tagName === "INPUT") return; expandedDirs[path] = !expandedDirs[path]; loadFileList(); };
                    el.addEventListener("dragover", function(e) { if (e.dataTransfer.types.indexOf("text/x-path") > -1) { e.preventDefault(); el.classList.add("drag-over"); } });
                    el.addEventListener("dragleave", function() { el.classList.remove("drag-over"); });
                    el.addEventListener("drop", function(e) {
                        e.preventDefault(); e.stopPropagation(); el.classList.remove("drag-over");
                        var srcPath = e.dataTransfer.getData("text/x-path");
                        if (!srcPath || srcPath === path || path.indexOf(srcPath + "/") === 0) return;
                        var fileName = srcPath.split("/").pop();
                        var newPath = path + "/" + fileName;
                        fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: srcPath, new: newPath}) })
                        .then(function(r) { return r.json(); }).then(function(d) {
                            if (d.status === "ok") { expandedDirs[path] = true; if (srcPath === currentFile) { currentFile = newPath; sbFile.textContent = newPath; } loadFileList(); }
                            else alert(d.message);
                        });
                    });
                    container.appendChild(el);
                    if (expandedDirs[path] && item.children) {
                        var cc = document.createElement("div"); cc.className = "dir-children open";
                        cc.setAttribute("data-dir", path);
                        renderTree(item.children, cc, path); container.appendChild(cc);
                    }
                } else {
                    el.className = "file-item" + (path === currentFile ? " active" : "");
                    el.innerHTML = '<span class="icon">📄</span><span class="fname">' + item.name + '</span>';
                    el.onclick = function(e) { if (e.target.tagName === "INPUT") return; openFile(path); };
                    container.appendChild(el);
                }
                el.oncontextmenu = function(e) { e.preventDefault(); showCtxMenu(e, path, item.type); };
                el.ondblclick = function(e) { e.preventDefault(); e.stopPropagation(); startRename(el, path, item.type); };
            });
        }

        // --- Context Menu ---
        function showCtxMenu(e, path, type) {
            hideCtxMenu();
            ctxMenu = document.createElement("div");
            ctxMenu.className = "ctx-menu";
            var items = [
                {label: "重命名", fn: function() { var el = document.querySelector('[data-path=\"' + path + '\"]'); if (el) startRename(el, path, type); }},
                {label: "删除", fn: function() { if (confirm("确认删除 " + path + " ?")) deleteFile(path); }}
            ];
            if (type === "dir") {
                items.unshift({label: "新建文件", fn: function() { startCreateIn(path, "file"); }});
                items.unshift({label: "新建文件夹", fn: function() { startCreateIn(path, "dir"); }});
            }
            items.forEach(function(it) {
                var mi = document.createElement("div"); mi.className = "ctx-item"; mi.textContent = it.label;
                mi.onclick = function() { hideCtxMenu(); it.fn(); };
                ctxMenu.appendChild(mi);
            });
            document.body.appendChild(ctxMenu);
            var rect = ctxMenu.getBoundingClientRect();
            var x = e.clientX, y = e.clientY;
            if (y + rect.height > window.innerHeight) y = window.innerHeight - rect.height - 4;
            if (x + rect.width > window.innerWidth) x = window.innerWidth - rect.width - 4;
            ctxMenu.style.left = x + "px";
            ctxMenu.style.top = y + "px";
        }
        function hideCtxMenu() { if (ctxMenu) { ctxMenu.remove(); ctxMenu = null; } }
        document.addEventListener("click", hideCtxMenu);

        // --- Rename (double-click) ---
        function startRename(el, path, type) {
            var fnameEl = el.querySelector(".fname");
            if (!fnameEl) return;
            var oldName = fnameEl.textContent;
            var inp = document.createElement("input");
            inp.className = "inline-input";
            inp.value = oldName;
            inp.style.margin = "0"; inp.style.width = "calc(100% - 40px)";
            fnameEl.replaceWith(inp);
            inp.focus(); inp.select();
            function commit() {
                var newName = inp.value.trim();
                if (!newName || newName === oldName) { loadFileList(); return; }
                var dir = path.lastIndexOf("/") > -1 ? path.substring(0, path.lastIndexOf("/") + 1) : "";
                fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: path, new: dir + newName}) })
                .then(function(r) { return r.json(); }).then(function(d) {
                    if (d.status === "ok") { if (path === currentFile) { currentFile = d.name; sbFile.textContent = d.name; } }
                    else { alert(d.message); }
                    loadFileList();
                });
            }
            inp.addEventListener("keydown", function(e) { if (e.key === "Enter") { e.preventDefault(); commit(); } else if (e.key === "Escape") { loadFileList(); } });
            inp.addEventListener("blur", commit);
        }

        // --- Create in directory ---
        function startCreateIn(dir, type) {
            expandedDirs[dir] = true;
            loadFileList();
            setTimeout(function() {
                var container = document.querySelector('[data-dir=\"' + dir + '\"]') || document.getElementById("fileList");
                var inp = document.createElement("input");
                inp.className = "inline-input";
                inp.placeholder = type === "dir" ? "文件夹名" : "文件名.lisp";
                container.insertBefore(inp, container.firstChild);
                inp.focus();
                inp.addEventListener("keydown", function(e) {
                    if (e.key === "Enter") {
                        var name = inp.value.trim(); if (!name) { inp.remove(); return; }
                        var fullPath = dir ? dir + "/" + name : name;
                        if (type === "dir") {
                            fetch("/api/dir/create", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({name: fullPath}) })
                            .then(function(r) { return r.json(); }).then(function(d) { inp.remove(); if (d.status === "ok") loadFileList(); else alert(d.message); });
                        } else {
                            fetch("/api/file/create", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({name: fullPath}) })
                            .then(function(r) { return r.json(); }).then(function(d) { inp.remove(); if (d.status === "ok") openFile(d.name); else alert(d.message); });
                        }
                    } else if (e.key === "Escape") { inp.remove(); }
                });
                inp.addEventListener("blur", function() { setTimeout(function() { if (inp.parentNode) inp.remove(); }, 150); });
            }, 50);
        }
        function openFile(name) {
            fetch("/api/file/" + encodeURIComponent(name)).then(function(r) { return r.json(); }).then(function(d) {
                editor.setValue(d.content); currentFile = name; sbFile.textContent = name; loadFileList();
                updateRunBtnVisibility(); updateFileLinks();
            });
        }
        function saveFile() {
            if (!currentFile) { currentFile = prompt("文件名:", "untitled.lisp"); if (!currentFile) return; }
            fetch("/api/file/save", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({name: currentFile, content: editor.getValue()}) })
            .then(function(r) { return r.json(); }).then(function() { loadFileList(); });
        }
        // --- Drag and drop upload (external files only) ---
        (function() {
            var fl = document.getElementById("fileList");
            fl.addEventListener("dragover", function(e) {
                e.preventDefault();
                if (e.dataTransfer.types.indexOf("text/x-path") === -1) fl.classList.add("drag-over");
            });
            fl.addEventListener("dragleave", function(e) { fl.classList.remove("drag-over"); });
            fl.addEventListener("drop", function(e) {
                fl.classList.remove("drag-over");
                if (e.dataTransfer.types.indexOf("text/x-path") > -1) return;
                e.preventDefault();
                var files = e.dataTransfer.files; if (!files.length) return;
                var dir = "";
                var target = e.target.closest("[data-path]");
                if (target && target.getAttribute("data-type") === "dir") dir = target.getAttribute("data-path");
                var fd = new FormData();
                for (var i = 0; i < files.length; i++) fd.append("files", files[i]);
                if (dir) fd.append("dir", dir);
                fetch("/api/file/upload", { method: "POST", body: fd })
                .then(function(r) { return r.json(); }).then(function(d) { if (d.status === "ok") loadFileList(); else alert(d.message); });
            });
        })();
        // --- Internal drag to root (move file out of folder) ---
        (function() {
            var fl = document.getElementById("fileList");
            fl.addEventListener("drop", function(e) {
                var srcPath = e.dataTransfer.getData("text/x-path");
                if (!srcPath) return;
                if (e.target.closest("[data-type='dir']")) return;
                e.preventDefault();
                var fileName = srcPath.split("/").pop();
                if (srcPath === fileName) return;
                fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: srcPath, new: fileName}) })
                .then(function(r) { return r.json(); }).then(function(d) {
                    if (d.status === "ok") { if (srcPath === currentFile) { currentFile = fileName; sbFile.textContent = fileName; } loadFileList(); }
                    else alert(d.message);
                });
            });
        })();
        function deleteFile(name) {
            fetch("/api/file/delete", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({name: name}) })
            .then(function(r) { return r.json(); }).then(function() { if (name === currentFile) { currentFile = ""; editor.setValue(""); sbFile.textContent = "未打开文件"; } loadFileList(); });
        }
        loadFileList();
        if (document.body.classList.contains("theme-light")) document.getElementById("themeBtn").innerHTML = "&#9790;";

        // --- Console ---
        function escapeHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
        function log(msg, type) {
            type = type || "text";
            var el = document.createElement("div");
            el.className = "output-line";
            if (type === "system") {
                if (msg.indexOf(">>>") === 0) {
                    stepCount++;
                    el.innerHTML = '<span class="step-badge">STEP ' + stepCount + '</span><span class="step-text">' + escapeHtml(msg.replace(/^>>>\s*/, "")) + '</span>';
                    el.classList.add("type-step");
                } else { el.classList.add("type-step"); el.innerHTML = '<span class="step-text">' + escapeHtml(msg) + '</span>'; }
            } else if (type === "error") { el.classList.add("type-error"); el.textContent = msg; }
            else if (type === "result") { el.classList.add("type-result"); el.textContent = msg; }
            else if (type === "md" || (markdownMode && type === "text")) {
                el.classList.add("type-md");
                var md = document.createElement("div"); md.className = "md-content";
                md.innerHTML = DOMPurify.sanitize(marked.parse(msg)); el.appendChild(md);
            } else { el.classList.add("type-output"); el.textContent = msg; }
            lineCount++; consoleOutput.appendChild(el); consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        function clearConsole() { consoleOutput.innerHTML = ""; lineCount = 0; }
        function toggleMarkdownMode() { markdownMode = !markdownMode; mdModeBtn.textContent = "MD: " + (markdownMode ? "ON" : "OFF"); }

        // --- Run/Stop ---
        function setRunning(running) {
            isRunning = running;
            runBtn.style.display = running ? "none" : "inline-block";
            stopBtn.style.display = running ? "inline-block" : "none";
            if (running) { setExecState("running"); startTimer(); }
        }
        function runCode() {
            if (isRunning) return;
            setRunning(true); clearConsole(); log(">>> 开始执行...", "system");
            abortController = new AbortController();
            fetch("/api/execute", { method: "POST", headers: {"Content-Type":"application/json"},
                body: JSON.stringify({ code: editor.getValue(), markdown: markdownMode }),
                signal: abortController.signal
            }).then(function(response) {
                var reader = response.body.getReader(), decoder = new TextDecoder();
                function read() {
                    reader.read().then(function(result) {
                        if (result.done) { setRunning(false); return; }
                        var lines = decoder.decode(result.value).split("\\n");
                        for (var i = 0; i < lines.length; i++) {
                            var line = lines[i];
                            if (line.indexOf("data: ") === 0) {
                                var data = line.substring(6);
                                if (data === "__DONE__") { stopTimer(); setExecState("done"); log(">>> 执行完成", "system"); }
                                else if (data.indexOf("__ERROR__:") === 0) { stopTimer(); setExecState("error"); log(data.substring(10), "error"); }
                                else if (data.indexOf("__RESULT__:") === 0) { stepCount++; log("=> " + data.substring(11).replace(/↎/g, "\\n"), "result"); }
                                else if (data.indexOf("__MD__:") === 0) { stepCount++; log(data.substring(7).replace(/↎/g, "\\n"), "md"); }
                                else if (data.indexOf("__TEXT__:") === 0) { stepCount++; log(data.substring(8).replace(/↎/g, "\\n"), "text"); }
                                else if (data) { stepCount++; log(data.replace(/↎/g, "\\n"), "text"); }
                            }
                        }
                        read();
                    }).catch(function(e) { stopTimer(); if (e.name === "AbortError") { setExecState("idle"); log(">>> 已停止", "system"); } else { setExecState("error"); log("请求失败: " + e.message, "error"); } setRunning(false); });
                }
                read();
            }).catch(function(e) { stopTimer(); if (e.name === "AbortError") { setExecState("idle"); log(">>> 已停止", "system"); } else { setExecState("error"); log("请求失败: " + e.message, "error"); } setRunning(false); });
        }
        function stopCode() { log(">>> 正在停止...", "system"); if (abortController) abortController.abort(); fetch("/api/stop", { method: "POST" }).catch(function() {}); }

        // --- Keyboard shortcuts ---
        document.addEventListener("keydown", function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveFile(); }
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !isRunning) runCode();
            if (e.key === "Escape" && isRunning) stopCode();
        });

        // --- Ctrl+Click file path jump ---
        editor.getWrapperElement().addEventListener("mousedown", function(e) {
            if (!(e.ctrlKey || e.metaKey)) return;
            var pos = editor.coordsChar({left: e.clientX, top: e.clientY});
            var token = editor.getTokenAt(pos);
            if (token.type && token.type.indexOf("string") !== -1) {
                var str = token.string.replace(/^["']|["']$/g, "");
                if (str.indexOf("/") !== -1 || str.match(/\\.(lisp|txt)$/)) { e.preventDefault(); openFile(str); }
            }
        });

        // --- File link marks ---
        var fileMarks = [];
        function updateFileLinks() {
            fileMarks.forEach(function(m) { m.clear(); });
            fileMarks = [];
            var re = /\\.(lisp|txt|lsp|md)$/;
            for (var i = 0; i < editor.lineCount(); i++) {
                var tokens = editor.getLineTokens(i);
                for (var j = 0; j < tokens.length; j++) {
                    var t = tokens[j];
                    if (t.type && t.type.indexOf("string") !== -1) {
                        var s = t.string.replace(/^["']|["']$/g, "");
                        if (s.indexOf("/") !== -1 || re.test(s)) {
                            fileMarks.push(editor.markText(
                                {line: i, ch: t.start}, {line: i, ch: t.end},
                                {className: "cm-file-link", attributes: {"data-file": s}}
                            ));
                        }
                    }
                }
            }
        }
        editor.on("change", function() { clearTimeout(editor._flTimer); editor._flTimer = setTimeout(updateFileLinks, 300); });

        // Click on file link (no modifier needed)
        editor.getWrapperElement().addEventListener("click", function(e) {
            var target = e.target;
            if (target.classList && target.classList.contains("cm-file-link")) {
                var file = target.getAttribute("data-file") || target.textContent.replace(/^["']|["']$/g, "");
                if (file && (file.indexOf("/") !== -1 || file.match(/\\.(lisp|txt|lsp|md)$/))) { openFile(file); }
            }
        });

        // --- Run button visibility by file type ---
        function isRunnableFile(name) { return !name || /\\.(lisp|lsp)$/.test(name); }
        function updateRunBtnVisibility() {
            var show = isRunnableFile(currentFile);
            document.querySelector(".editor-actions").style.display = show ? "" : "none";
        }

        // --- API Key ---
        function toggleKeyVisibility() { var inp = document.getElementById("apiKeyInput"); inp.type = inp.type === "password" ? "text" : "password"; }
        function setApiKey() {
            var key = document.getElementById("apiKeyInput").value.trim();
            if (!key) { alert("请输入 API Key"); return; }
            fetch("/api/config", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ api_key: key }) })
            .then(function(r) { return r.json(); }).then(function(d) {
                if (d.status === "ok") {
                    document.getElementById("apiKeyInput").value = "";
                    document.getElementById("apiKeyInput").placeholder = "已设置: " + key.substring(0,4) + "****" + (key.length>8?key.substring(key.length-4):"");
                    document.getElementById("apiKeyInput").type = "password";
                    document.getElementById("keySetBtn").style.display = "none";
                    document.getElementById("keyClearBtn").style.display = "inline-block";
                    statusEl.textContent = "API Key ✓"; statusEl.className = "status-badge ok";
                } else { alert(d.message); }
            }).catch(function(e) { alert("设置失败: " + e.message); });
        }
        function clearApiKey() {
            if (!confirm("确认清除 API Key？")) return;
            fetch("/api/config", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ clear: true }) })
            .then(function(r) { return r.json(); }).then(function(d) {
                if (d.status === "ok") {
                    document.getElementById("apiKeyInput").placeholder = "DeepSeek API Key";
                    document.getElementById("apiKeyInput").type = "password";
                    document.getElementById("keySetBtn").style.display = "inline-block";
                    document.getElementById("keyClearBtn").style.display = "none";
                    statusEl.textContent = "无 API Key"; statusEl.className = "status-badge";
                }
            }).catch(function(e) { alert("清除失败: " + e.message); });
        }
        document.getElementById("apiKeyInput").addEventListener("keydown", function(e) { if (e.key === "Enter") setApiKey(); });

        // --- Status check ---
        function refreshStatus() {
            fetch("/api/status").then(function(r) { return r.json(); }).then(function(d) {
                statusEl.textContent = d.api_key_set ? "API Key ✓" : "无 API Key";
                statusEl.className = "status-badge " + (d.api_key_set ? "ok" : "");
            }).catch(function() { statusEl.textContent = "连接失败"; statusEl.className = "status-badge"; });
        }
        refreshStatus();
        fetch("/api/config").then(function(r) { return r.json(); }).then(function(d) {
            if (d.api_key_set) {
                document.getElementById("keySetBtn").style.display = "none";
                document.getElementById("keyClearBtn").style.display = "inline-block";
                document.getElementById("apiKeyInput").placeholder = "已设置: " + d.masked_key;
                statusEl.textContent = "API Key ✓"; statusEl.className = "status-badge ok";
            }
        }).catch(function() {});
    </script>
</body>
</html>
'''


def main():
    port = 8080
    print("=" * 50)
    print("Lisp Workflow Web 界面")
    print("=" * 50)
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
