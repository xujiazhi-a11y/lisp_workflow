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


# 初始化时注入
update_llm_env()


def stream_print(text):
    """流式打印 - 检查全局 markdown_mode"""
    global should_stop, markdown_mode
    if not should_stop:
        # 转义换行符，保证多行内容作为一条消息发送
        prefix = "__MD__:" if markdown_mode else "__TEXT__:"
        escaped = str(text).replace('\n', '↎')
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
            for fname in ['hello.lisp', 'article.lisp', 'workflow.lisp', 'llm.lisp']:
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
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
        .btn-stop { background: transparent; color: #4e6ef2; border: 1px solid #4e6ef2; display: none; }
        .btn-stop:hover { background: #4e6ef2; color: white; }
        .examples { padding: 8px 12px; background: #1a1a2e; color: #eee; border: 1px solid #0f3460; border-radius: 6px; }
        .main { flex: 1; display: flex; gap: 1px; background: #0f3460; min-height: 0; }
        .panel { display: flex; flex-direction: column; background: #1a1a2e; overflow: hidden; }
        .editor-panel { flex: 1; min-height: 0; }
        .console-panel { flex: 1; min-height: 0; }
        .panel-header { padding: 10px 15px; background: #16213e; font-size: 13px; color: #888; border-bottom: 1px solid #0f3460; }
        .code-area { flex: 1; width: 100%; padding: 15px; background: #1a1a2e; color: #eee; border: none; font-family: Monaco, Consolas, monospace; font-size: 14px; resize: none; outline: none; line-height: 1.6; }
        .console-output { flex: 1; padding: 15px; overflow-y: auto; font-family: Monaco, Consolas, monospace; font-size: 13px; line-height: 1.5; background: #1a1a2e; min-height: 0; }
        .console-output .error { color: #ff6b6b; }
        .console-output .md-content { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; color: #ddd; }
        .console-output .md-content h1, .console-output .md-content h2, .console-output .md-content h3 { color: #4e6ef2; margin: 1em 0 0.5em; }
        .console-output .md-content p { margin: 0.5em 0; }
        .console-output .md-content code { background: #2a2f42; padding: 2px 6px; border-radius: 3px; font-family: Monaco, Consolas, monospace; }
        .console-output .md-content pre { background: #16213e; padding: 12px; border-radius: 6px; overflow-x: auto; }
        .console-output .md-content pre code { background: transparent; padding: 0; }
        .console-output .md-content ul, .console-output .md-content ol { margin: 0.5em 0; padding-left: 1.5em; }
        .console-output .md-content blockquote { border-left: 3px solid #4e6ef2; margin: 0.5em 0; padding-left: 1em; color: #888; }
        .console-output .result { color: #4ecca3; font-weight: 500; }
        .console-output .output-line { padding: 2px 0; }
        .mode-toggle { display: flex; gap: 8px; margin-left: auto; align-items: center; }
        .btn-md { padding: 4px 10px; font-size: 11px; background: #2a2f42; color: #888; border: 1px solid #3a3f52; border-radius: 4px; cursor: pointer; transition: all 0.2s; }
        .btn-md:hover { background: #3a3f52; color: #ddd; }
        .btn-md.active { background: #4e6ef2; color: white; border-color: #4e6ef2; }
        .footer { padding: 8px 20px; background: #16213e; font-size: 12px; color: #666; border-top: 1px solid #0f3460; }
        .key-group { display: flex; align-items: center; gap: 4px; margin-left: auto; }
        .key-group input { padding: 6px 10px; background: #1a1a2e; color: #eee; border: 1px solid #0f3460; border-radius: 4px; font-size: 12px; width: 190px; }
        .key-group input:focus { outline: none; border-color: #4e6ef2; }
        .key-btn { padding: 6px 10px; border: 1px solid #0f3460; border-radius: 4px; background: transparent; color: #888; cursor: pointer; font-size: 12px; transition: 0.2s; }
        .key-btn:hover { background: #0f3460; color: #eee; }
        .key-btn.set { background: #4e6ef2; color: white; border-color: #4e6ef2; }
        .key-btn.set:hover { background: #6b8af9; }
        .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid #0f3460; border-top-color: #4e6ef2; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <h1>Lisp Workflow</h1>
        <span class="status ok" id="status">检查中...</span>
        <select class="examples" id="exampleSelect" onchange="loadExample()">
            <option value="">-- 加载示例 --</option>
            <option value="hello">Hello World</option>
            <option value="article">文章生成工作流</option>
            <option value="workflow">工作流组合</option>
            <option value="llm">大模型对话</option>
        </select>
        <button class="btn btn-run" id="runBtn" onclick="runCode()">▶ 运行</button>
        <button class="btn btn-stop" id="stopBtn" onclick="stopCode()">⏹ 停止</button>
        <div class="key-group">
            <input type="password" id="apiKeyInput" placeholder="输入 DeepSeek API Key" onkeydown="if(event.key==='Enter')setApiKey()">
            <button class="key-btn" id="keyToggleBtn" onclick="toggleKeyVisibility()" title="显示/隐藏">👁</button>
            <button class="key-btn set" id="keySetBtn" onclick="setApiKey()">设置</button>
            <button class="key-btn" id="keyClearBtn" onclick="clearApiKey()" style="display:none">清除</button>
        </div>
        <div class="mode-toggle">
            <button class="btn-md active" id="mdModeBtn" onclick="toggleMarkdownMode()">📄 Markdown</button>
        </div>
    </div>
    <div class="main">
        <div class="panel editor-panel">
            <div class="panel-header">📝 代码编辑区 (Ctrl+Enter 运行)</div>
            <textarea class="code-area" id="codeArea" spellcheck="false">;; Hello World
(print "Hello, Lisp Workflow!")
(print (str-concat "1 + 2 = " (str (+ 1 2))))
"Done!"</textarea>
        </div>
        <div class="panel console-panel">
            <div class="panel-header">💻 控制台</div>
            <div class="console-output" id="consoleOutput">准备就绪</div>
        </div>
    </div>
    <div class="footer">
        <span>提示: Ctrl+Enter 快速运行 | Esc 停止执行</span>
        <span id="footerStatus">就绪</span>
    </div>
    
    <script>
        const consoleOutput = document.getElementById('consoleOutput');
        const codeArea = document.getElementById('codeArea');
        const runBtn = document.getElementById('runBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusEl = document.getElementById('status');
        const footerStatus = document.getElementById('footerStatus');
        const mdModeBtn = document.getElementById('mdModeBtn');
        
        let isRunning = false;
        let abortController = null;
        let markdownMode = true;  // 默认开启 Markdown 渲染
        
        const examples = {
            hello: "",
            article: "",
            workflow: "",
            llm: ""
        };
        
        // 加载示例列表
        async function loadExamples() {
            console.log('[Debug] loadExamples called');
            try {
                const r = await fetch('/api/examples');
                console.log('[Debug] fetch completed');
                const d = await r.json();
                console.log('[Debug] JSON parsed, examples count:', d.examples ? d.examples.length : 0);
                if (d.examples) {
                    d.examples.forEach(ex => {
                        console.log('[Debug] Loading example:', ex.name);
                        examples[ex.name] = ex.code;
                    });
                }
            } catch (e) {
                console.error('[Debug] loadExamples error:', e);
            }
        }
        loadExamples();
        
        function loadExample() {
            console.log('[Debug] loadExample called, value:', document.getElementById('exampleSelect').value);
            const select = document.getElementById('exampleSelect');
            if (select.value && examples[select.value]) {
                console.log('[Debug] Setting codeArea, example:', select.value, 'length:', examples[select.value].length);
                codeArea.value = examples[select.value];
            } else {
                console.log('[Debug] No example found for:', select.value);
                console.log('[Debug] available examples:', Object.keys(examples));
            }
        }
        
        function log(msg, type = 'text') {
            const el = document.createElement('div');
            el.className = 'output-line';
            
            if (type === 'error') {
                el.classList.add('error');
                el.textContent = msg;
            } else if (type === 'result') {
                el.classList.add('result');
                el.textContent = msg;
            } else if (type === 'md' || (markdownMode && type === 'text')) {
                el.classList.add('md-content');
                el.innerHTML = DOMPurify.sanitize(marked.parse(msg));
            } else {
                el.textContent = msg;
            }
            
            consoleOutput.appendChild(el);
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }

        function clearConsole() {
            consoleOutput.innerHTML = '';
        }
        
        function toggleMarkdownMode() {
            markdownMode = !markdownMode;
            mdModeBtn.classList.toggle('active', markdownMode);
            
            // 如果启用 Markdown，实时渲染已有内容
            if (markdownMode) {
                const items = consoleOutput.querySelectorAll('.output-line');
                items.forEach(item => {
                    if (item.classList.contains('md-content')) return; // 跳过已渲染的
                    const text = item.textContent;
                    const newEl = document.createElement('div');
                    newEl.className = 'output-line md-content';
                    newEl.innerHTML = DOMPurify.sanitize(marked.parse(text));
                    item.replaceWith(newEl);
                });
            }
        }
        
        function setRunning(running) {
            isRunning = running;
            runBtn.style.display = running ? 'none' : 'block';
            stopBtn.style.display = running ? 'block' : 'none';
            runBtn.disabled = running;
            footerStatus.textContent = running ? '执行中... (按 Esc 停止)' : '就绪';
        }
        
        async function runCode() {
            if (isRunning) return;
            
            const code = codeArea.value;
            setRunning(true);
            clearConsole();
            log('>>> 开始执行...');
            
            abortController = new AbortController();
            
            try {
                console.log('[Frontend] Sending request, markdownMode:', markdownMode);
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: code, markdown: markdownMode }),
                    signal: abortController.signal
                });
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const text = decoder.decode(value);
                    const lines = text.split('\\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.substring(6);
                            if (data === '__DONE__') {
                                log('执行完成', 'text');
                            } else if (data.startsWith('__ERROR__:')) {
                                log('错误: ' + data.substring(10), 'error');
                            } else if (data.startsWith('__RESULT__:')) {
                                log('=> ' + data.substring(11), 'result');
                            } else if (data.startsWith('__MD__:')) {
                                const content = data.substring(7).replace(/↎/g, String.fromCharCode(10));
                                log(content, 'md');
                            } else if (data.startsWith('__TEXT__:')) {
                                const content = data.substring(8).replace(/↎/g, String.fromCharCode(10));
                                log(content, 'text');
                            } else if (data) {
                                // 向后兼容：无前缀的普通文本
                                const decoded = data.replace(/↎/g, String.fromCharCode(10));
                                log(decoded, 'text');
                            }
                        }
                    }
                }
            } catch (e) {
                if (e.name === 'AbortError') {
                    log('\\n>>> 已停止');
                } else {
                    log('\\n请求失败: ' + e.message);
                }
            }
            
            setRunning(false);
        }
        
        async function stopCode() {
            log('\\n>>> 正在停止...');
            
            // 中止前端请求
            if (abortController) {
                abortController.abort();
            }
            
            // 通知后端停止
            try {
                await fetch('/api/stop', { method: 'POST' });
            } catch (e) {}
            
            setRunning(false);
        }
        
        // 快捷键
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter' && !isRunning) runCode();
            if (e.key === 'Escape' && isRunning) stopCode();
        });
        
        // 检查状态
        async function refreshStatus() {
            try {
                const r = await fetch('/api/status');
                const d = await r.json();
                statusEl.textContent = d.api_key_set ? 'API Key ✓' : '无 API Key';
                statusEl.className = 'status ' + (d.api_key_set ? 'ok' : '');
            } catch {
                statusEl.textContent = '连接失败';
                statusEl.className = 'status';
            }
        }
        refreshStatus();

        // 检查是否已有 key
        fetch('/api/config')
            .then(r => r.json())
            .then(d => {
                if (d.api_key_set) {
                    document.getElementById('keySetBtn').style.display = 'none';
                    document.getElementById('keyClearBtn').style.display = 'inline-block';
                    document.getElementById('apiKeyInput').placeholder = '已设置: ' + d.masked_key;
                    statusEl.textContent = 'API Key ✓';
                    statusEl.className = 'status ok';
                }
            })
            .catch(() => {});

        function toggleKeyVisibility() {
            const inp = document.getElementById('apiKeyInput');
            inp.type = inp.type === 'password' ? 'text' : 'password';
        }

        async function setApiKey() {
            const key = document.getElementById('apiKeyInput').value.trim();
            if (!key) { alert('请输入 API Key'); return; }
            try {
                const r = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_key: key })
                });
                const d = await r.json();
                if (d.status === 'ok') {
                    document.getElementById('apiKeyInput').value = '';
                    document.getElementById('apiKeyInput').placeholder = '已设置: ' + key.substring(0,4) + '****' + (key.length>8?key.substring(key.length-4):'');
                    document.getElementById('apiKeyInput').type = 'password';
                    document.getElementById('keySetBtn').style.display = 'none';
                    document.getElementById('keyClearBtn').style.display = 'inline-block';
                    statusEl.textContent = 'API Key ✓';
                    statusEl.className = 'status ok';
                } else {
                    alert(d.message);
                }
            } catch (e) { alert('设置失败: ' + e.message); }
        }

        async function clearApiKey() {
            if (!confirm('确认清除 API Key？')) return;
            try {
                const r = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ clear: true })
                });
                const d = await r.json();
                if (d.status === 'ok') {
                    document.getElementById('apiKeyInput').placeholder = '输入 DeepSeek API Key';
                    document.getElementById('apiKeyInput').type = 'password';
                    document.getElementById('keySetBtn').style.display = 'inline-block';
                    document.getElementById('keyClearBtn').style.display = 'none';
                    statusEl.textContent = '无 API Key';
                    statusEl.className = 'status';
                }
            } catch (e) { alert('清除失败: ' + e.message); }
        }
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
