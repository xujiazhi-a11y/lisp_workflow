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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_lisp import run as run_lisp, GLOBAL_ENV, to_lisp_str

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
        
        # 执行代码
        result = run_lisp(code)
        
        if not should_stop and result is not None:
            output_queue.put(f"__RESULT__:{result}")
        
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
        elif self.path == '/api/examples':
            # 返回示例列表
            examples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples')
            examples_list = []
            for fname in ['hello.lisp', 'article.lisp', 'workflow.lisp', 'llm.lisp', 'feishu_feedback.lisp']:
                fpath = os.path.join(examples_dir, fname)
                if os.path.exists(fpath):
                    with open(fpath, 'r', encoding='utf-8') as f:
                        examples_list.append({
                            "name": fname.replace('.lisp', ''),
                            "label": fname.replace('.lisp', '').title(),
                            "code": f.read()
                        })
            self.send_json({"examples": examples_list})
        else:
            self.send_error(404)
    
    def do_POST(self):
        global current_thread, should_stop, _server_api_key
        
        content_length = int(self.headers.get('Content-Length', 0))
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
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Lisp Workflow</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/lib/codemirror.min.css">
    <script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/lib/codemirror.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/addon/edit/matchbrackets.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/addon/edit/closebrackets.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #1a1a2e; color: #eee; height: 100vh;
            display: flex; flex-direction: column;
        }
        .header {
            background: #16213e; padding: 12px 20px;
            display: flex; align-items: center; gap: 15px;
            border-bottom: 2px solid #0f3460; flex-shrink: 0;
        }
        .header h1 { font-size: 18px; color: #4e6ef2; font-weight: 500; }
        .status { font-size: 12px; padding: 4px 10px; border-radius: 12px; background: #0f3460; }
        .status.ok { color: #4ecca3; }
        .btn { padding: 8px 18px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; transition: all 0.2s; }
        .btn-run { background: #4e6ef2; color: white; }
        .btn-run:hover { background: #6b8af9; }
        .btn-run:disabled { background: #444; cursor: not-allowed; }
        .btn-stop { background: transparent; color: #ff6b6b; border: 1px solid #ff6b6b; display: none; }
        .btn-stop:hover { background: #ff6b6b; color: white; }
        .examples { padding: 8px 12px; background: #1a1a2e; color: #eee; border: 1px solid #0f3460; border-radius: 6px; font-size: 13px; }
        .main { flex: 1; display: flex; gap: 1px; background: #0f3460; min-height: 0; }
        .panel { display: flex; flex-direction: column; background: #1a1a2e; overflow: hidden; }
        .editor-panel { flex: 1; min-height: 0; }
        .console-panel { flex: 1; min-height: 0; }
        .panel-header { padding: 10px 15px; background: #16213e; font-size: 13px; color: #888; border-bottom: 1px solid #0f3460; display: flex; align-items: center; }
        .editor-container { flex: 1; overflow: hidden; min-height: 0; position: relative; }

        /* CodeMirror 5 dark theme overrides */
        .CodeMirror { height: 100%; background: #1a1a2e; color: #eeffff; font-family: Monaco, Consolas, "Courier New", monospace; font-size: 14px; line-height: 1.6; }
        .CodeMirror-gutters { background: #16213e; border-right: 1px solid #0f3460; }
        .CodeMirror-linenumber { color: #444; padding: 0 8px; }
        .CodeMirror-cursor { border-left: 2px solid #4e6ef2; }
        .CodeMirror-selected { background: rgba(78, 110, 242, 0.15) !important; }
        .CodeMirror-activeline-background { background: rgba(78, 110, 242, 0.05); }
        .CodeMirror-matchingbracket { color: #fff !important; background: rgba(78, 110, 242, 0.3); outline: 1px solid rgba(78, 110, 242, 0.6); }
        .CodeMirror-focused .CodeMirror-selected { background: rgba(78, 110, 242, 0.2) !important; }
        .cm-s-lisp-dark .cm-keyword { color: #c792ea; font-weight: bold; }
        .cm-s-lisp-dark .cm-builtin { color: #82aaff; }
        .cm-s-lisp-dark .cm-stdlib { color: #ffcb6b; }
        .cm-s-lisp-dark .cm-string { color: #c3e88d; }
        .cm-s-lisp-dark .cm-number { color: #f78c6c; }
        .cm-s-lisp-dark .cm-comment { color: #676e95; font-style: italic; }
        .cm-s-lisp-dark .cm-atom { color: #ff5370; }
        .cm-s-lisp-dark .cm-bracket { color: #89ddff; }
        .cm-s-lisp-dark .cm-variable { color: #eeffff; }

        .console-status-bar {
            display: flex; align-items: center; gap: 16px;
            padding: 8px 15px; background: #16213e;
            border-bottom: 1px solid #0f3460; font-size: 12px;
            font-family: Monaco, Consolas, monospace; flex-shrink: 0;
        }
        .status-indicator { display: flex; align-items: center; gap: 6px; color: #aaa; font-weight: 500; }
        .state-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
        .state-dot.idle { background: #555; }
        .state-dot.running { background: #4e6ef2; animation: pulse 1.2s ease-in-out infinite; }
        .state-dot.done { background: #4ecca3; }
        .state-dot.error { background: #ff6b6b; }
        @keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.8); } }
        .status-time { color: #666; }
        .status-steps { color: #666; margin-left: auto; }

        .console-output {
            flex: 1; padding: 2px 0; overflow-y: auto;
            font-family: Monaco, Consolas, monospace;
            font-size: 12px; line-height: 1.3; background: #1a1a2e; min-height: 0;
        }
        .console-output::-webkit-scrollbar { width: 5px; }
        .console-output::-webkit-scrollbar-track { background: transparent; }
        .console-output::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        .console-output::-webkit-scrollbar-thumb:hover { background: #555; }

        .output-line { padding: 1px 10px 1px 12px; border-left: 3px solid transparent; }
        .output-line.type-output { border-left-color: #2a3a2a; color: #bbb; }
        .output-line.type-result { border-left-color: #4ecca3; color: #4ecca3; font-weight: 500; background: rgba(78,204,163,0.05); border-radius: 0 3px 3px 0; margin: 3px 4px 3px 0; padding: 3px 10px 3px 12px; }
        .output-line.type-error { border-left-color: #ff6b6b; color: #ff6b6b; background: rgba(255,107,107,0.07); border-radius: 0 3px 3px 0; margin: 3px 4px 3px 0; padding: 4px 10px 4px 12px; }
        .output-line.type-md { border-left-color: #c792ea; padding: 2px 10px 2px 12px; }
        .output-line.type-step { border-left-color: #4e6ef2; padding: 3px 10px 3px 12px; margin-top: 4px; }
        .step-badge { display: inline-block; font-size: 9px; padding: 1px 5px; border-radius: 3px; background: #0f3460; color: #4e6ef2; font-weight: 700; margin-right: 6px; letter-spacing: 0.5px; vertical-align: middle; }
        .step-text { color: #aaa; font-size: 12px; }

        .output-line .md-content { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 13px; line-height: 1.4; color: #ddd; }
        .output-line .md-content h1, .output-line .md-content h2, .output-line .md-content h3 { color: #4e6ef2; margin: 0.3em 0 0.2em; font-size: 13px; }
        .output-line .md-content p { margin: 0.2em 0; }
        .output-line .md-content code { background: #2a2f42; padding: 1px 4px; border-radius: 2px; font-family: Monaco, Consolas, monospace; font-size: 11px; }
        .output-line .md-content pre { background: #16213e; padding: 8px; border-radius: 4px; overflow-x: auto; margin: 0.3em 0; font-size: 11px; }
        .output-line .md-content pre code { background: transparent; padding: 0; }
        .output-line .md-content ul, .output-line .md-content ol { margin: 0.2em 0; padding-left: 1.2em; }
        .output-line .md-content blockquote { border-left: 2px solid #4e6ef2; margin: 0.2em 0; padding-left: 0.8em; color: #888; }

        .console-stats-bar {
            display: flex; align-items: center; justify-content: space-between;
            padding: 6px 15px; background: #16213e;
            border-top: 1px solid #0f3460; font-size: 11px;
            color: #555; font-family: Monaco, Consolas, monospace; flex-shrink: 0;
        }

        .mode-toggle { display: flex; gap: 8px; margin-left: auto; align-items: center; }
        .btn-md { padding: 4px 10px; font-size: 11px; background: #2a2f42; color: #888; border: 1px solid #3a3f52; border-radius: 4px; cursor: pointer; transition: all 0.2s; }
        .btn-md:hover { background: #3a3f52; color: #ddd; }
        .btn-md.active { background: #4e6ef2; color: white; border-color: #4e6ef2; }
        .footer { padding: 8px 20px; background: #16213e; font-size: 12px; color: #666; border-top: 1px solid #0f3460; display: flex; justify-content: space-between; }
        .key-group { display: flex; align-items: center; gap: 4px; margin-left: auto; }
        .key-group input { padding: 6px 10px; background: #1a1a2e; color: #eee; border: 1px solid #0f3460; border-radius: 4px; font-size: 12px; width: 190px; }
        .key-group input:focus { outline: none; border-color: #4e6ef2; }
        .key-btn { padding: 6px 10px; border: 1px solid #0f3460; border-radius: 4px; background: transparent; color: #888; cursor: pointer; font-size: 12px; transition: 0.2s; }
        .key-btn:hover { background: #0f3460; color: #eee; }
        .key-btn.set { background: #4e6ef2; color: white; border-color: #4e6ef2; }
        .key-btn.set:hover { background: #6b8af9; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Lisp Workflow</h1>
        <span class="status ok" id="status">检查中...</span>
        <select class="examples" id="exampleSelect">
            <option value="">-- 加载示例 --</option>
            <option value="hello">Hello World</option>
            <option value="article">文章生成工作流</option>
            <option value="workflow">工作流组合</option>
            <option value="llm">大模型对话</option>
            <option value="feishu_feedback">飞书反馈处理</option>
        </select>
        <button class="btn btn-run" id="runBtn" onclick="runCode()">&#9654; 运行</button>
        <button class="btn btn-stop" id="stopBtn" onclick="stopCode()">&#9724; 停止</button>
        <div class="key-group">
            <input type="password" id="apiKeyInput" placeholder="输入 DeepSeek API Key">
            <button class="key-btn" id="keyToggleBtn" onclick="toggleKeyVisibility()" title="显示/隐藏">&#128065;</button>
            <button class="key-btn set" id="keySetBtn" onclick="setApiKey()">设置</button>
            <button class="key-btn" id="keyClearBtn" onclick="clearApiKey()" style="display:none">清除</button>
        </div>
        <div class="mode-toggle">
            <button class="btn-md active" id="mdModeBtn" onclick="toggleMarkdownMode()">Markdown</button>
        </div>
    </div>
    <div class="main">
        <div class="panel editor-panel">
            <div class="panel-header">代码编辑区 (Ctrl+Enter 运行)</div>
            <div class="editor-container" id="editorContainer">
                <textarea id="codeArea">;; Hello World
(print "Hello, Lisp Workflow!")
(print (str-concat "1 + 2 = " (str (+ 1 2))))
"Done!"</textarea>
            </div>
        </div>
        <div class="panel console-panel">
            <div class="console-status-bar">
                <span class="status-indicator" id="execState"><span class="state-dot idle"></span> Idle</span>
                <span class="status-time" id="execTime">0.0s</span>
                <span class="status-steps" id="execSteps">0 steps</span>
            </div>
            <div class="console-output" id="consoleOutput"><div class="output-line type-system">准备就绪</div></div>
            <div class="console-stats-bar">
                <span id="totalLines">0 lines</span>
                <span id="totalTime">-</span>
            </div>
        </div>
    </div>
    <div class="footer">
        <span>Ctrl+Enter 快速运行 | Esc 停止执行</span>
        <span id="footerStatus">就绪</span>
    </div>

    <script>
        // --- Custom Lisp mode for CodeMirror 5 ---
        (function() {
            var KEYWORDS = /^(define|lambda|if|let|begin|pipe|quote|set!|defmacro|map|reduce|filter|cond|when|unless|do|and|or|not)$/;
            var KEYWORDS_CN = /^(定义|道|如果|开始|引|！赋)$/;
            var BUILTINS = /^(call-llm|llm|send-to-feishu|str-concat|str-join|str-split|str-replace|str-trim|str-upper|str-lower|str-starts\?|str-ends\?|str-contains\?|format|print|println|pr|parse-json|to-json|extract-json|remove-think|regex-match|regex-replace|read-file|write-file|each|dict|get|put|keys|values|http-post|http-get|pipe|->)$/;
            var STDLIB = /^(list|cons|car|cdr|first|rest|length|append|reverse|nth|take|drop|null\?|list\?|number\?|string\?|symbol\?|boolean\?|procedure\?|empty\?|dict\?|eq\?|equal\?|mod|str|abs|max|min|floor|ceil|round)$/;

            CodeMirror.defineMode("lisp-workflow", function() {
                return {
                    startState: function() { return { inString: false }; },
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
                        if (ch === "(" || ch === ")" || ch === "[" || ch === "]" || ch === "{" || ch === "}") { stream.next(); return "bracket"; }
                        if (stream.match(/^#[tf](rue|alse)?\\b/)) return "atom";
                        if (stream.match(/^-?\\d+(\\.\\d+)?/)) return "number";
                        var word = "";
                        while (!stream.eol()) {
                            ch = stream.peek();
                            if (/[\\s()\\[\\]{}";\\'\\\\]/.test(ch)) break;
                            word += stream.next();
                        }
                        if (word) {
                            if (KEYWORDS.test(word) || KEYWORDS_CN.test(word)) return "keyword";
                            if (BUILTINS.test(word)) return "builtin";
                            if (STDLIB.test(word)) return "stdlib";
                            return "variable";
                        }
                        stream.next();
                        return null;
                    }
                };
            });
        })();

        // --- Initialize CodeMirror ---
        var editor = CodeMirror.fromTextArea(document.getElementById("codeArea"), {
            mode: "lisp-workflow",
            theme: "lisp-dark",
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            indentUnit: 2,
            tabSize: 2,
            indentWithTabs: false,
            lineWrapping: true,
            styleActiveLine: true,
            extraKeys: {
                "Ctrl-Enter": function() { runCode(); },
                "Cmd-Enter": function() { runCode(); },
                "Esc": function() { if (isRunning) stopCode(); }
            }
        });

        // --- State ---
        var consoleOutput = document.getElementById("consoleOutput");
        var runBtn = document.getElementById("runBtn");
        var stopBtn = document.getElementById("stopBtn");
        var statusEl = document.getElementById("status");
        var footerStatus = document.getElementById("footerStatus");
        var mdModeBtn = document.getElementById("mdModeBtn");
        var isRunning = false;
        var abortController = null;
        var markdownMode = true;
        var executionTimer = null;
        var startTime = 0;
        var stepCount = 0;
        var lineCount = 0;

        // --- Status bar ---
        function setExecState(state) {
            var labels = { idle: "Idle", running: "Running", done: "Done", error: "Error" };
            document.getElementById("execState").innerHTML = "<span class=\\"state-dot " + state + "\\"></span> " + labels[state];
        }
        function startTimer() {
            startTime = performance.now();
            stepCount = 0; lineCount = 0;
            document.getElementById("execTime").textContent = "0.0s";
            document.getElementById("execSteps").textContent = "0 steps";
            document.getElementById("totalLines").textContent = "0 lines";
            executionTimer = setInterval(function() {
                document.getElementById("execTime").textContent = ((performance.now() - startTime) / 1000).toFixed(1) + "s";
            }, 100);
        }
        function stopTimer() {
            if (executionTimer) { clearInterval(executionTimer); executionTimer = null; }
            var total = ((performance.now() - startTime) / 1000).toFixed(2);
            document.getElementById("totalTime").textContent = total + "s";
            document.getElementById("execTime").textContent = total + "s";
        }
        function updateStats() {
            document.getElementById("totalLines").textContent = lineCount + " lines";
            document.getElementById("execSteps").textContent = stepCount + " steps";
        }

        // --- Examples ---
        var examples = {};
        function loadExamples() {
            fetch("/api/examples").then(function(r) { return r.json(); }).then(function(d) {
                if (d.examples) d.examples.forEach(function(ex) { examples[ex.name] = ex.code; });
            }).catch(function() {});
        }
        loadExamples();

        document.getElementById("exampleSelect").addEventListener("change", function() {
            if (this.value && examples[this.value]) {
                editor.setValue(examples[this.value]);
            }
        });

        // --- Console ---
        function escapeHtml(s) {
            return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
        }
        function log(msg, type) {
            type = type || "text";
            var el = document.createElement("div");
            el.className = "output-line";
            if (type === "system") {
                if (msg.indexOf(">>>") === 0) {
                    stepCount++;
                    var text = msg.replace(/^>>>\s*/, "");
                    el.innerHTML = "<span class=\\"step-badge\\">STEP " + stepCount + "</span><span class=\\"step-text\\">" + escapeHtml(text) + "</span>";
                    el.classList.add("type-step");
                } else {
                    el.classList.add("type-step");
                    el.innerHTML = "<span class=\\"step-text\\">" + escapeHtml(msg) + "</span>";
                }
            } else if (type === "error") {
                el.classList.add("type-error");
                el.textContent = msg;
            } else if (type === "result") {
                el.classList.add("type-result");
                el.textContent = msg;
            } else if (type === "md" || (markdownMode && type === "text")) {
                el.classList.add("type-md");
                var md = document.createElement("div");
                md.className = "md-content";
                md.innerHTML = DOMPurify.sanitize(marked.parse(msg));
                el.appendChild(md);
            } else {
                el.classList.add("type-output");
                el.textContent = msg;
            }
            lineCount++;
            consoleOutput.appendChild(el);
            updateStats();
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }

        function clearConsole() { consoleOutput.innerHTML = ""; lineCount = 0; updateStats(); }

        function toggleMarkdownMode() {
            markdownMode = !markdownMode;
            mdModeBtn.classList.toggle("active", markdownMode);
        }

        // --- Run/Stop ---
        function setRunning(running) {
            isRunning = running;
            runBtn.style.display = running ? "none" : "inline-block";
            stopBtn.style.display = running ? "inline-block" : "none";
            runBtn.disabled = running;
            footerStatus.textContent = running ? "执行中... (按 Esc 停止)" : "就绪";
            if (running) { setExecState("running"); startTimer(); }
        }

        function runCode() {
            if (isRunning) return;
            var code = editor.getValue();
            setRunning(true);
            clearConsole();
            log(">>> 开始执行...", "system");
            abortController = new AbortController();
            fetch("/api/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: code, markdown: markdownMode }),
                signal: abortController.signal
            }).then(function(response) {
                var reader = response.body.getReader();
                var decoder = new TextDecoder();
                function read() {
                    reader.read().then(function(result) {
                        if (result.done) { setRunning(false); return; }
                        var text = decoder.decode(result.value);
                        var lines = text.split("\\n");
                        for (var i = 0; i < lines.length; i++) {
                            var line = lines[i];
                            if (line.indexOf("data: ") === 0) {
                                var data = line.substring(6);
                                if (data === "__DONE__") {
                                    stopTimer(); setExecState("done");
                                    log(">>> 执行完成", "system");
                                } else if (data.indexOf("__ERROR__:") === 0) {
                                    stopTimer(); setExecState("error");
                                    log(data.substring(10), "error");
                                } else if (data.indexOf("__RESULT__:") === 0) {
                                    stepCount++;
                                    log("=> " + data.substring(11), "result");
                                } else if (data.indexOf("__MD__:") === 0) {
                                    stepCount++;
                                    var content = data.substring(7).replace(/↎/g, "\\n");
                                    log(content, "md");
                                } else if (data.indexOf("__TEXT__:") === 0) {
                                    stepCount++;
                                    var content = data.substring(8).replace(/↎/g, "\\n");
                                    log(content, "text");
                                } else if (data) {
                                    stepCount++;
                                    var decoded = data.replace(/↎/g, "\\n");
                                    log(decoded, "text");
                                }
                            }
                        }
                        read();
                    }).catch(function(e) {
                        stopTimer();
                        if (e.name === "AbortError") {
                            setExecState("idle");
                            log(">>> 已停止", "system");
                        } else {
                            setExecState("error");
                            log("请求失败: " + e.message, "error");
                        }
                        setRunning(false);
                    });
                }
                read();
            }).catch(function(e) {
                stopTimer();
                if (e.name === "AbortError") {
                    setExecState("idle");
                    log(">>> 已停止", "system");
                } else {
                    setExecState("error");
                    log("请求失败: " + e.message, "error");
                }
                setRunning(false);
            });
        }

        function stopCode() {
            log(">>> 正在停止...", "system");
            if (abortController) abortController.abort();
            fetch("/api/stop", { method: "POST" }).catch(function() {});
        }

        // --- Keyboard shortcuts ---
        document.addEventListener("keydown", function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !isRunning) runCode();
            if (e.key === "Escape" && isRunning) stopCode();
        });

        // --- API Key ---
        function toggleKeyVisibility() {
            var inp = document.getElementById("apiKeyInput");
            inp.type = inp.type === "password" ? "text" : "password";
        }
        function setApiKey() {
            var key = document.getElementById("apiKeyInput").value.trim();
            if (!key) { alert("请输入 API Key"); return; }
            fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ api_key: key }) })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.status === "ok") {
                    document.getElementById("apiKeyInput").value = "";
                    document.getElementById("apiKeyInput").placeholder = "已设置: " + key.substring(0,4) + "****" + (key.length>8?key.substring(key.length-4):"");
                    document.getElementById("apiKeyInput").type = "password";
                    document.getElementById("keySetBtn").style.display = "none";
                    document.getElementById("keyClearBtn").style.display = "inline-block";
                    statusEl.textContent = "API Key \\u2713";
                    statusEl.className = "status ok";
                } else { alert(d.message); }
            }).catch(function(e) { alert("设置失败: " + e.message); });
        }
        function clearApiKey() {
            if (!confirm("确认清除 API Key？")) return;
            fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ clear: true }) })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.status === "ok") {
                    document.getElementById("apiKeyInput").placeholder = "输入 DeepSeek API Key";
                    document.getElementById("apiKeyInput").type = "password";
                    document.getElementById("keySetBtn").style.display = "inline-block";
                    document.getElementById("keyClearBtn").style.display = "none";
                    statusEl.textContent = "无 API Key";
                    statusEl.className = "status";
                }
            }).catch(function(e) { alert("清除失败: " + e.message); });
        }
        document.getElementById("apiKeyInput").addEventListener("keydown", function(e) { if (e.key === "Enter") setApiKey(); });

        // --- Status check ---
        function refreshStatus() {
            fetch("/api/status").then(function(r) { return r.json(); }).then(function(d) {
                statusEl.textContent = d.api_key_set ? "API Key \\u2713" : "无 API Key";
                statusEl.className = "status " + (d.api_key_set ? "ok" : "");
            }).catch(function() { statusEl.textContent = "连接失败"; statusEl.className = "status"; });
        }
        refreshStatus();
        fetch("/api/config").then(function(r) { return r.json(); }).then(function(d) {
            if (d.api_key_set) {
                document.getElementById("keySetBtn").style.display = "none";
                document.getElementById("keyClearBtn").style.display = "inline-block";
                document.getElementById("apiKeyInput").placeholder = "已设置: " + d.masked_key;
                statusEl.textContent = "API Key \\u2713";
                statusEl.className = "status ok";
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
    print(f"\n服务器: http://localhost:{port}")
    print("按 Ctrl+C 停止\n")
    
    server = HTTPServer(('localhost', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    main()
