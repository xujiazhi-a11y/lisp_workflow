// --- Theme ---
(function() {
    var saved = localStorage.getItem("lisp-theme");
    if (saved === "light") document.body.classList.add("theme-light");
})();
function toggleTheme() {
    var isLight = document.body.classList.toggle("theme-light");
    localStorage.setItem("lisp-theme", isLight ? "light" : "dark");
    document.getElementById("themeBtn").innerHTML = isLight ? "&#9790;" : "&#9788;";
    syncMobileThemeBtn();
}
function syncMobileThemeBtn() {
    var btn = document.getElementById("mobileThemeBtn");
    if (!btn) return;
    var isLight = document.body.classList.contains("theme-light");
    btn.textContent = isLight ? "浅色" : "深色";
}
if (document.body.classList.contains("theme-light")) {
    document.getElementById("themeBtn").innerHTML = "&#9790;";
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
                        if (ch === "\\") stream.next();
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
                if (stream.match(/^#[tf](rue|alse)?\b/)) return "atom";
                if (stream.match(/^-?\d+(\.\d+)?/)) return "number";
                var word = "";
                while (!stream.eol()) {
                    ch = stream.peek();
                    if (/[\s()\[\]{}\u3010\u3011\uff08\uff09";'\\]/.test(ch)) break;
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

// --- Mobile Tab Navigation ---
var currentMobileTab = 'explorer';
var mobileMq = window.matchMedia('(max-width: 768px)');

function isMobile() { return mobileMq.matches; }

function mobileLucide(name, extraClass) {
    var cls = "m-icon" + (extraClass ? " " + extraClass : "");
    return '<span class="' + cls + '"><i data-lucide="' + name + '"></i></span>';
}
function refreshMobileIcons(root) {
    if (typeof lucide === "undefined") return;
    var opts = { attrs: { "stroke-width": 2 }, nameAttr: "data-lucide" };
    if (root) opts.root = root;
    lucide.createIcons(opts);
}

function applyMobileMode() {
    if (isMobile()) {
        document.body.classList.add('is-mobile');
        var anyActive = document.querySelector('.sidebar.mobile-active') ||
            document.querySelector('.editor-area.mobile-active') ||
            document.querySelector('.output-area.mobile-active');
        if (!anyActive) switchTab(currentMobileTab);
    } else {
        document.body.classList.remove('is-mobile');
        document.querySelector('.sidebar').classList.remove('mobile-active');
        document.querySelector('.editor-area').classList.remove('mobile-active');
        document.querySelector('.output-area').classList.remove('mobile-active');
        closeMobileSettings();
        closeMobileActionSheet();
    }
    if (waitingForInput) syncInputVisibility();
    refreshMobileIcons();
    setTimeout(function() { editor.refresh(); }, 80);
}

function switchTab(tab) {
    currentMobileTab = tab;
    var sidebar = document.querySelector('.sidebar');
    var editorArea = document.querySelector('.editor-area');
    var outputArea = document.querySelector('.output-area');
    sidebar.classList.remove('mobile-active');
    editorArea.classList.remove('mobile-active');
    outputArea.classList.remove('mobile-active');
    document.getElementById('tabExplorer').classList.remove('active');
    document.getElementById('tabEditor').classList.remove('active');
    document.getElementById('tabOutput').classList.remove('active');
    if (tab === 'explorer') {
        sidebar.classList.add('mobile-active');
        document.getElementById('tabExplorer').classList.add('active');
    } else if (tab === 'editor') {
        editorArea.classList.add('mobile-active');
        document.getElementById('tabEditor').classList.add('active');
        setTimeout(function() { editor.refresh(); }, 50);
    } else if (tab === 'output') {
        outputArea.classList.add('mobile-active');
        document.getElementById('tabOutput').classList.add('active');
    }
    updateMobileFabVisibility();
}

function updateMobileFab(running) {
    var fab = document.getElementById("mobileFab");
    var icon = document.getElementById("mobileFabIcon");
    if (!fab || !icon) return;
    if (running) {
        fab.classList.add("running");
        fab.setAttribute("aria-label", "停止");
    } else {
        fab.classList.remove("running");
        fab.setAttribute("aria-label", "运行");
    }
    icon.innerHTML = '<i data-lucide="' + (running ? 'square' : 'play') + '"></i>';
    refreshMobileIcons(icon);
}
function updateMobileFabVisibility() {
    var fab = document.getElementById("mobileFab");
    if (!fab || !isMobile()) return;
    var show = currentMobileTab === "editor" && isRunnableFile(currentFile);
    fab.classList.toggle("hidden", !show);
}

if (isMobile()) { switchTab('explorer'); }
applyMobileMode();
refreshMobileIcons();
window.addEventListener('resize', applyMobileMode);
if (mobileMq.addEventListener) {
    mobileMq.addEventListener('change', applyMobileMode);
} else if (mobileMq.addListener) {
    mobileMq.addListener(applyMobileMode);
}

// --- Mobile Settings Modal ---
function openMobileSettings() {
    document.getElementById('mobileSettingsModal').classList.add('open');
    document.body.classList.add('mobile-settings-open');
    syncMobileThemeBtn();
    syncMobileMdBtn();
}
function closeMobileSettings() {
    document.getElementById('mobileSettingsModal').classList.remove('open');
    document.body.classList.remove('mobile-settings-open');
    if (waitingForInput) syncInputVisibility();
}
function toggleMobileKeyVisibility() {
    var inp = document.getElementById('mobileApiKeyInput');
    inp.type = inp.type === 'password' ? 'text' : 'password';
    var eyeBtn = document.querySelector('.mobile-key-eye');
    if (eyeBtn) {
        eyeBtn.innerHTML = mobileLucide(inp.type === 'password' ? 'eye' : 'eye-off');
        refreshMobileIcons(eyeBtn);
    }
}
function setMobileApiKey() {
    var key = document.getElementById('mobileApiKeyInput').value.trim();
    if (!key) { alert('请输入 API Key'); return; }
    fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ api_key: key }) })
    .then(function(r) { return r.json(); }).then(function(d) {
        if (d.status === 'ok') {
            document.getElementById('mobileApiKeyInput').value = '';
            var hint = key.substring(0,4) + '****' + (key.length>8?key.substring(key.length-4):'');
            document.getElementById('mobileKeyHint').textContent = '已设置: ' + hint;
            document.getElementById('mobileKeyClearBtn').style.display = 'block';
            statusEl.textContent = 'API Key ✓'; statusEl.className = 'status-badge ok';
            closeMobileSettings();
        } else { alert(d.message); }
    }).catch(function(e) { alert('设置失败: ' + e.message); });
}
function clearMobileApiKey() {
    if (!confirm('确认清除 API Key？')) return;
    fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ clear: true }) })
    .then(function(r) { return r.json(); }).then(function(d) {
        if (d.status === 'ok') {
            document.getElementById('mobileApiKeyInput').placeholder = 'DeepSeek API Key';
            document.getElementById('mobileKeyHint').textContent = '未设置 API Key';
            statusEl.textContent = '无 API Key'; statusEl.className = 'status-badge';
            closeMobileSettings();
        }
    }).catch(function(e) { alert('清除失败: ' + e.message); });
}
document.getElementById('mobileApiKeyInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') setMobileApiKey();
});

// --- Mobile Action Sheet (touch-friendly file menu) ---
function openMobileActionSheet(path, type) {
    if (!isMobile()) { showCtxMenu({ clientX: window.innerWidth / 2, clientY: window.innerHeight / 2, preventDefault: function() {} }, path, type); return; }
    document.getElementById('mobileActionTitle').textContent = path;
    var container = document.getElementById('mobileActionItems');
    container.innerHTML = '';
    var actions = buildFileActions(path, type);
    actions.forEach(function(act) {
        var btn = document.createElement('button');
        btn.className = 'mobile-action-item' + (act.danger ? ' danger' : '');
        btn.textContent = act.label;
        btn.onclick = function() { closeMobileActionSheet(); act.fn(); };
        container.appendChild(btn);
    });
    document.getElementById('mobileActionSheet').classList.add('open');
}
function closeMobileActionSheet() {
    document.getElementById('mobileActionSheet').classList.remove('open');
}
function buildFileActions(path, type) {
    var actions = [];
    if (type === 'dir') {
        actions.push({ label: '📄 新建文件', fn: function() { startCreateIn(path, 'file'); } });
        actions.push({ label: '📁 新建文件夹', fn: function() { startCreateIn(path, 'dir'); } });
    }
    actions.push({ label: '✏️ 重命名', fn: function() {
        var el = document.querySelector('[data-path="' + path + '"]');
        if (el) startRename(el, path, type);
    }});
    actions.push({ label: '📋 复制', fn: function() {
        fetch("/api/file/duplicate", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({name: path}) })
        .then(function(r) { return r.json(); }).then(function(d) { if (d.status === "ok") loadFileList(); else alert(d.message); });
    }});
    if (path.indexOf("/") > -1) {
        actions.push({ label: '⬆️ 移出到上级', fn: function() {
            var parentDir = path.substring(0, path.lastIndexOf("/"));
            var grandParent = parentDir.indexOf("/") > -1 ? parentDir.substring(0, parentDir.lastIndexOf("/")) : "";
            var fileName = path.split("/").pop();
            var newPath = grandParent ? grandParent + "/" + fileName : fileName;
            fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: path, new: newPath}) })
            .then(function(r) { return r.json(); }).then(function(d) {
                if (d.status === "ok") { if (path === currentFile) { currentFile = newPath; updateMobileFileName(); } loadFileList(); }
                else alert(d.message);
            });
        }});
    }
    actions.push({ label: '🗑 删除', danger: true, fn: function() {
        if (confirm("确认删除 " + path + " ?")) deleteFile(path);
    }});
    return actions;
}
function attachLongPress(el, path, type) {
    var timer = null, moved = false;
    el.addEventListener('touchstart', function(e) {
        if (e.target.closest('.item-actions') || e.target.closest('.mobile-more-btn')) return;
        moved = false;
        timer = setTimeout(function() {
            if (!moved) { openMobileActionSheet(path, type); }
        }, 500);
    }, { passive: true });
    el.addEventListener('touchmove', function() { moved = true; if (timer) { clearTimeout(timer); timer = null; } }, { passive: true });
    el.addEventListener('touchend', function() { if (timer) { clearTimeout(timer); timer = null; } }, { passive: true });
}
function updateMobileFileName() {
    var el = document.getElementById('mobileFileName');
    if (el) el.textContent = currentFile || '未打开文件';
}
function updateMobileExecStatus(text) {
    var el = document.getElementById('mobileExecStatus');
    if (el) el.textContent = text;
}
function syncMobileMdBtn() {
    var btn = document.getElementById('mobileMdBtn');
    var toggle = document.getElementById('mobileMdToggle');
    var label = markdownMode ? 'ON' : 'OFF';
    if (btn) btn.textContent = 'MD: ' + label;
    if (toggle) {
        toggle.textContent = label;
        toggle.classList.toggle('on', markdownMode);
    }
}

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

// --- Client identity (multi-tab / multi-device isolation) ---
var clientId = (function() {
    var key = "lisp-client-id";
    var id = localStorage.getItem(key);
    if (!id) {
        id = "c-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
        localStorage.setItem(key, id);
    }
    return id;
})();

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
var waitingForInput = false;
var sseLineBuffer = "";

function setExecState(state) {
    stateDot.className = "state-dot " + state;
    document.getElementById("mobileDot").className = "state-dot " + state;
    var statusMap = { idle: "就绪", running: "运行中", waiting: "等待输入", done: "已完成", error: "出错" };
    updateMobileExecStatus(statusMap[state] || state);
    var badge = document.getElementById("outputTabBadge");
    if (badge) badge.classList.toggle("show", state === "running");
}
function startTimer() {
    startTime = performance.now(); stepCount = 0; lineCount = 0;
    execTimeEl.textContent = "0.0s";
    var mel = document.getElementById("mobileExecTime");
    if (mel) mel.textContent = "0.0s";
    executionTimer = setInterval(function() {
        var t = ((performance.now() - startTime) / 1000).toFixed(1) + "s";
        execTimeEl.textContent = t;
        if (mel) mel.textContent = t;
    }, 100);
}
function stopTimer() {
    if (executionTimer) { clearInterval(executionTimer); executionTimer = null; }
    var t = ((performance.now() - startTime) / 1000).toFixed(2) + "s";
    execTimeEl.textContent = t;
    var mel = document.getElementById("mobileExecTime");
    if (mel) mel.textContent = t;
}

// --- File tree ---
var currentFile = "";
var expandedDirs = {};
var ctxMenu = null;

function loadFileList() {
    fetch("/api/files").then(function(r) { return r.json(); }).then(function(d) {
        _cachedTree = d.tree;
        var list = document.getElementById("fileList");
        list.innerHTML = "";
        renderTree(d.tree, list, "");
        refreshMobileIcons(list);
    });
}
function collapseAll() { expandedDirs = {}; loadFileList(); }
function expandAll() {
    function walkExpand(items, prefix) {
        items.forEach(function(item) {
            if (item.type === "dir") {
                var p = prefix ? prefix + "/" + item.name : item.name;
                expandedDirs[p] = true;
                if (item.children) walkExpand(item.children, p);
            }
        });
    }
    walkExpand(_cachedTree, "");
    loadFileList();
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
            if (isMobile()) {
                var chevron = mobileLucide(expandedDirs[path] ? "chevron-down" : "chevron-right", "m-icon-sm");
                el.innerHTML = chevron + mobileLucide("folder", "m-icon-sm") + '<span class="fname">' + item.name + '</span>'
                    + '<span class="item-actions">'
                    + '<button class="mobile-more-btn m-icon-btn" title="更多" data-act="more" aria-label="更多">' + mobileLucide("ellipsis") + '</button>'
                    + '</span>';
            } else {
                var arrow = expandedDirs[path] ? "▼" : "▶";
                el.innerHTML = '<span class="icon">' + arrow + '</span><span class="icon">📁</span><span class="fname">' + item.name + '</span>'
                    + '<span class="item-actions">'
                    + '<button class="act-btn" title="新建文件" data-act="newfile">+📄</button>'
                    + '<button class="act-btn" title="新建文件夹" data-act="newdir">+📁</button>'
                    + '<button class="act-btn" title="删除" data-act="del">🗑</button>'
                    + '<button class="mobile-more-btn" title="更多" data-act="more">⋯</button>'
                    + '</span>';
            }
            el.onclick = function(e) {
                if (e.target.tagName === "INPUT" || e.target.closest(".item-actions")) return;
                expandedDirs[path] = !expandedDirs[path]; loadFileList();
            };
            el.querySelector('[data-act="more"]').onclick = function(e) { e.stopPropagation(); openMobileActionSheet(path, "dir"); };
            if (!isMobile()) {
                el.querySelector('[data-act="newfile"]').onclick = function(e) { e.stopPropagation(); startCreateIn(path, "file"); };
                el.querySelector('[data-act="newdir"]').onclick = function(e) { e.stopPropagation(); startCreateIn(path, "dir"); };
                el.querySelector('[data-act="del"]').onclick = function(e) { e.stopPropagation(); if (confirm("确认删除 " + path + " ?")) deleteFile(path); };
            }
            attachLongPress(el, path, "dir");
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
                // Drop on open children area also moves into this folder
                (function(dirPath) {
                    cc.addEventListener("dragover", function(e) {
                        if (e.dataTransfer.types.indexOf("text/x-path") > -1 && !e.target.closest("[data-type='dir']")) { e.preventDefault(); cc.classList.add("drag-over"); }
                    });
                    cc.addEventListener("dragleave", function(e) { if (!cc.contains(e.relatedTarget)) cc.classList.remove("drag-over"); });
                    cc.addEventListener("drop", function(e) {
                        cc.classList.remove("drag-over");
                        var srcPath = e.dataTransfer.getData("text/x-path");
                        if (!srcPath) return;
                        if (e.target.closest("[data-type='dir']")) return;
                        if (srcPath === dirPath || dirPath.indexOf(srcPath + "/") === 0) return;
                        var srcParent = srcPath.lastIndexOf("/") > -1 ? srcPath.substring(0, srcPath.lastIndexOf("/")) : "";
                        if (srcParent === dirPath) return;
                        e.preventDefault(); e.stopPropagation();
                        var fileName = srcPath.split("/").pop();
                        var newPath = dirPath + "/" + fileName;
                        fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: srcPath, new: newPath}) })
                        .then(function(r) { return r.json(); }).then(function(d) {
                            if (d.status === "ok") { if (srcPath === currentFile) { currentFile = newPath; sbFile.textContent = newPath; } loadFileList(); }
                            else alert(d.message);
                        });
                    });
                })(path);
                renderTree(item.children, cc, path); container.appendChild(cc);
            }
        } else {
            el.className = "file-item" + (path === currentFile ? " active" : "");
            if (isMobile()) {
                el.innerHTML = mobileLucide("file-text", "m-icon-sm") + '<span class="fname">' + item.name + '</span>'
                    + '<span class="item-actions">'
                    + '<button class="mobile-more-btn m-icon-btn" title="更多" data-act="more" aria-label="更多">' + mobileLucide("ellipsis") + '</button>'
                    + '</span>';
            } else {
                el.innerHTML = '<span class="icon">📄</span><span class="fname">' + item.name + '</span>'
                    + '<span class="item-actions">'
                    + '<button class="act-btn" title="删除" data-act="del">🗑</button>'
                    + '<button class="mobile-more-btn" title="更多" data-act="more">⋯</button>'
                    + '</span>';
            }
            el.onclick = function(e) { if (e.target.tagName === "INPUT" || e.target.closest(".item-actions")) return; openFile(path); };
            el.querySelector('[data-act="more"]').onclick = function(e) { e.stopPropagation(); openMobileActionSheet(path, "file"); };
            if (!isMobile()) {
                el.querySelector('[data-act="del"]').onclick = function(e) { e.stopPropagation(); if (confirm("确认删除 " + path + " ?")) deleteFile(path); };
            }
            attachLongPress(el, path, "file");
            container.appendChild(el);
        }
        el.oncontextmenu = function(e) { e.preventDefault(); showCtxMenu(e, path, item.type); };
        el.ondblclick = function(e) { e.preventDefault(); e.stopPropagation(); startRename(el, path, item.type); };
    });
}

// --- Context Menu ---
function getAllDirs(items, prefix) {
    var dirs = [];
    items.forEach(function(item) {
        if (item.type === "dir") {
            var p = prefix ? prefix + "/" + item.name : item.name;
            dirs.push(p);
            if (item.children) dirs = dirs.concat(getAllDirs(item.children, p));
        }
    });
    return dirs;
}
var _cachedTree = [];
function showCtxMenu(e, path, type) {
    hideCtxMenu();
    ctxMenu = document.createElement("div");
    ctxMenu.className = "ctx-menu";
    var items = [
        {label: "重命名", fn: function() { var el = document.querySelector('[data-path="' + path + '"]'); if (el) startRename(el, path, type); }},
        {label: "复制", fn: function() {
            fetch("/api/file/duplicate", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({name: path}) })
            .then(function(r) { return r.json(); }).then(function(d) { if (d.status === "ok") loadFileList(); else alert(d.message); });
        }},
        {label: "删除", fn: function() { if (confirm("确认删除 " + path + " ?")) deleteFile(path); }}
    ];
    if (type === "dir") {
        items.unshift({label: "新建文件", fn: function() { startCreateIn(path, "file"); }});
        items.unshift({label: "新建文件夹", fn: function() { startCreateIn(path, "dir"); }});
    }
    // "移出到上级" — only if item is inside a folder
    if (path.indexOf("/") > -1) {
        var parentDir = path.substring(0, path.lastIndexOf("/"));
        var grandParent = parentDir.indexOf("/") > -1 ? parentDir.substring(0, parentDir.lastIndexOf("/")) : "";
        items.push({label: "移出到上级", fn: function() {
            var fileName = path.split("/").pop();
            var newPath = grandParent ? grandParent + "/" + fileName : fileName;
            fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: path, new: newPath}) })
            .then(function(r) { return r.json(); }).then(function(d) {
                if (d.status === "ok") { if (path === currentFile) { currentFile = newPath; sbFile.textContent = newPath; } loadFileList(); }
                else alert(d.message);
            });
        }});
    }
    // "移动到..." — submenu with all dirs
    var allDirs = getAllDirs(_cachedTree, "");
    var currentParent = path.indexOf("/") > -1 ? path.substring(0, path.lastIndexOf("/")) : "";
    var validDirs = allDirs.filter(function(d) { return d !== path && d !== currentParent && d.indexOf(path + "/") !== 0; });
    if (validDirs.length > 0 || currentParent) {
        var moveTargets = [];
        if (currentParent) {
            moveTargets.push({label: "📂 / (根目录)", fn: function() {
                var fileName = path.split("/").pop();
                fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: path, new: fileName}) })
                .then(function(r) { return r.json(); }).then(function(dd) {
                    if (dd.status === "ok") { if (path === currentFile) { currentFile = fileName; sbFile.textContent = fileName; } loadFileList(); }
                    else alert(dd.message);
                });
            }});
        }
        validDirs.forEach(function(d) {
            moveTargets.push({label: "📁 " + d, fn: function() {
                var fileName = path.split("/").pop();
                var newPath = d + "/" + fileName;
                fetch("/api/file/rename", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({old: path, new: newPath}) })
                .then(function(r) { return r.json(); }).then(function(dd) {
                    if (dd.status === "ok") { expandedDirs[d] = true; if (path === currentFile) { currentFile = newPath; sbFile.textContent = newPath; } loadFileList(); }
                    else alert(dd.message);
                });
            }});
        });
        items.push({label: "移动到 ▸", submenu: moveTargets});
    }
    items.forEach(function(it) {
        var mi = document.createElement("div"); mi.className = "ctx-item"; mi.textContent = it.label;
        if (it.submenu) {
            mi.style.position = "relative";
            mi.onmouseenter = function() {
                var sub = mi.querySelector(".ctx-submenu");
                if (sub) { sub.style.display = "block"; return; }
                sub = document.createElement("div"); sub.className = "ctx-menu ctx-submenu";
                sub.style.position = "absolute"; sub.style.left = "100%"; sub.style.top = "0"; sub.style.maxHeight = "200px"; sub.style.overflowY = "auto";
                it.submenu.forEach(function(si) {
                    var smi = document.createElement("div"); smi.className = "ctx-item"; smi.textContent = si.label;
                    smi.onclick = function(ev) { ev.stopPropagation(); hideCtxMenu(); si.fn(); };
                    sub.appendChild(smi);
                });
                mi.appendChild(sub);
            };
            mi.onmouseleave = function() { var sub = mi.querySelector(".ctx-submenu"); if (sub) sub.style.display = "none"; };
        } else {
            mi.onclick = function() { hideCtxMenu(); it.fn(); };
        }
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
        var container = document.querySelector('[data-dir="' + dir + '"]') || document.getElementById("fileList");
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
        editor.setValue(d.content); currentFile = name; sbFile.textContent = name; updateMobileFileName(); loadFileList();
        updateRunBtnVisibility(); updateFileLinks();
        if (isMobile()) switchTab('editor');
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
        // Only move to root if not dropped on a dir item and not inside a dir-children container
        if (e.target.closest("[data-type='dir']")) return;
        if (e.target.closest(".dir-children")) return;
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
    .then(function(r) { return r.json(); }).then(function() {
        if (name === currentFile) { currentFile = ""; editor.setValue(""); sbFile.textContent = "未打开文件"; updateMobileFileName(); }
        loadFileList();
    });
}
loadFileList();
if (document.body.classList.contains("theme-light")) document.getElementById("themeBtn").innerHTML = "&#9790;";

// --- Console ---
function escapeHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function linkifyMagnets(text) {
    return text.replace(/(magnet:\?xt=urn:btih:[a-fA-F0-9]+[^\s<]*)/g, function(m) {
        return '<a href="' + m + '" class="magnet-link" title="点击复制磁力链接">🧲 ' + m.substring(0, 60) + '...</a>';
    });
}
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
    } else {
        el.classList.add("type-output");
        var escaped = escapeHtml(msg);
        if (escaped.indexOf("magnet:") > -1) {
            el.innerHTML = linkifyMagnets(escaped);
        } else {
            el.textContent = msg;
        }
    }
    lineCount++; consoleOutput.appendChild(el); consoleOutput.scrollTop = consoleOutput.scrollHeight;
}
function clearConsole() { consoleOutput.innerHTML = ""; lineCount = 0; searchProgressEl = null; }

// --- Search Progress ---
var searchProgressEl = null;
var searchProgressTimer = null;
var searchProgressStartTime = 0;
var searchProgressServerEta = 45;
var searchProgressLastPct = 3;

function formatSearchTiming(elapsed, eta) {
    var e = Math.max(0, elapsed || 0);
    var t = Math.max(0, eta != null ? eta : 0);
    return "已等待 " + e + " 秒 · 预计还需约 " + t + " 秒";
}

function updateSearchProgress(data) {
    if (!searchProgressEl) {
        searchProgressEl = document.createElement("div");
        searchProgressEl.className = "search-progress";
        searchProgressEl.id = "searchProgress";
        consoleOutput.appendChild(searchProgressEl);
    }
    if (!searchProgressStartTime) searchProgressStartTime = Date.now();
    if (data.eta != null) searchProgressServerEta = data.eta;
    if (data.percent != null) searchProgressLastPct = data.percent;

    var elapsed = data.elapsed != null
        ? data.elapsed
        : Math.floor((Date.now() - searchProgressStartTime) / 1000);
    var pct = data.percent != null ? data.percent : searchProgressLastPct;
    var eta = data.eta != null ? data.eta : Math.max(0, searchProgressServerEta - elapsed);

    searchProgressEl.innerHTML =
        '<div class="search-progress-head">' +
            '<span class="search-progress-spinner"></span>' +
            '<span class="search-progress-msg">' + escapeHtml(data.message || "搜索中…") + '</span>' +
            '<span class="search-progress-pct">' + pct + '%</span>' +
        '</div>' +
        '<div class="search-progress-timing">' + formatSearchTiming(elapsed, eta) + '</div>' +
        '<div class="search-progress-bar"><div class="search-progress-fill" style="width:' + pct + '%"></div></div>';

    consoleOutput.scrollTop = consoleOutput.scrollHeight;
    if (isMobile()) switchTab("output");

    if (!searchProgressTimer && isRunning) {
        searchProgressTimer = setInterval(tickSearchProgress, 1000);
    }
}

function tickSearchProgress() {
    if (!searchProgressEl || !searchProgressStartTime) return;
    var elapsed = Math.floor((Date.now() - searchProgressStartTime) / 1000);
    var eta = Math.max(0, searchProgressServerEta - elapsed);
    var timingEl = searchProgressEl.querySelector(".search-progress-timing");
    if (timingEl) timingEl.textContent = formatSearchTiming(elapsed, eta);
    var pctEl = searchProgressEl.querySelector(".search-progress-pct");
    var fillEl = searchProgressEl.querySelector(".search-progress-fill");
    if (pctEl && fillEl && elapsed > 2) {
        var cur = parseInt(pctEl.textContent, 10) || searchProgressLastPct;
        if (cur < 90) {
            cur = Math.min(90, cur + 1);
            pctEl.textContent = cur;
            fillEl.style.width = cur + "%";
        }
    }
}

function startSearchProgress(keyword) {
    if (!isRunning) return;
    searchProgressStartTime = Date.now();
    searchProgressServerEta = 45;
    searchProgressLastPct = 3;
    if (searchProgressTimer) { clearInterval(searchProgressTimer); searchProgressTimer = null; }
    updateSearchProgress({
        message: "已收到「" + keyword + "」，正在启动搜索…",
        percent: 3,
        eta: 45,
        elapsed: 0
    });
}

function clearSearchProgress() {
    if (searchProgressTimer) { clearInterval(searchProgressTimer); searchProgressTimer = null; }
    searchProgressStartTime = 0;
    searchProgressServerEta = 45;
    searchProgressLastPct = 3;
    if (searchProgressEl) {
        searchProgressEl.remove();
        searchProgressEl = null;
    }
}
function toggleMarkdownMode() {
    markdownMode = !markdownMode;
    mdModeBtn.textContent = "MD: " + (markdownMode ? "ON" : "OFF");
    syncMobileMdBtn();
}

// --- Torrent Cards ---
var SOURCE_LABELS = {
    apibay: "TPB",
    dmhy: "花园",
    btsow: "DHT",
    skrbtmv: "DHT",
    skrbtla: "DHT",
    torrentdownload: "TD"
};
function formatSourceLabel(r) {
    return r.source_label || SOURCE_LABELS[r.source] || r.source || "";
}
function getQualityBadgeInfo(r) {
    var t = (r.title || "").toUpperCase();
    var tier = r.quality_tier || 1;
    if (tier >= 4 || /4K|2160P|UHD|IMAX/.test(t)) return { cls: "q-4k", label: "4K" };
    if (tier >= 3 || /1080P|FHD|BLURAY|BDRIP/.test(t)) return { cls: "q-1080", label: "1080p" };
    if (tier >= 2 || /720P/.test(t)) return { cls: "q-720", label: "720p" };
    return null;
}
function renderTorrentCards(results) {
    var container = document.createElement("div");
    container.className = "torrent-cards";
    for (var i = 0; i < results.length; i++) {
        var r = results[i];
        var card = document.createElement("div");
        if (isMobile()) {
            var badge = getQualityBadgeInfo(r);
            var badgeHtml = badge ? '<span class="torrent-quality-badge ' + badge.cls + '">' + badge.label + '</span>' : '';
            var seedText = (r.seeders != null ? r.seeders : (r.seeds != null ? r.seeds : "?"));
            var srcLabel = formatSourceLabel(r);
            var hideSeeders = r.source === "skrbtmv" || r.source === "skrbtla";
            card.className = "torrent-card" + (badge ? " has-badge" : "");
            card.innerHTML = badgeHtml +
                '<div class="torrent-card-title">' + escapeHtml(r.title || '') + '<span class="torrent-card-source">' + escapeHtml(srcLabel) + '</span></div>' +
                '<div class="torrent-card-meta">' +
                '<span class="meta-item">' + mobileLucide('hard-drive', 'm-icon-sm') + escapeHtml(r.size || '未知') + '</span>' +
                (!hideSeeders ? '<span class="meta-item">' + mobileLucide('users', 'm-icon-sm') + escapeHtml(String(seedText)) + '</span>' : '') +
                '<span class="meta-item source-tag">' + mobileLucide('link', 'm-icon-sm') + escapeHtml(srcLabel) + '</span>' +
                '</div>' +
                '<div class="torrent-card-actions">' +
                '<button class="copy-btn" data-magnet="' + escapeHtml(r.magnet || '') + '">复制链接</button>' +
                '<button class="preview-btn" data-magnet="' + escapeHtml(r.magnet || '') + '" data-title="' + escapeHtml(r.title || '') + '">预览</button>' +
                '</div>';
        } else {
            var srcLabel = formatSourceLabel(r);
            var hideSeeders = r.source === "skrbtmv" || r.source === "skrbtla";
            card.className = "torrent-card";
            card.innerHTML = '<div class="torrent-card-title">[' + (i+1) + '] ' + escapeHtml(r.title || '') + '<span class="torrent-card-source">' + escapeHtml(srcLabel) + '</span></div>' +
                '<div class="torrent-card-meta">大小: ' + escapeHtml(r.size || '未知') + (!hideSeeders ? ' | 做种: ' + (r.seeds != null ? r.seeds : (r.seeders != null ? r.seeders : '?')) : '') + ' | 来源: ' + escapeHtml(srcLabel) + '</div>' +
                '<div class="torrent-card-actions">' +
                '<button class="copy-btn" data-magnet="' + escapeHtml(r.magnet || '') + '">📋 复制链接</button>' +
                '<button class="preview-btn" data-magnet="' + escapeHtml(r.magnet || '') + '" data-title="' + escapeHtml(r.title || '') + '">预览</button>' +
                '</div>';
        }
        container.appendChild(card);
    }
    consoleOutput.appendChild(container);
    if (isMobile()) refreshMobileIcons(container);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// --- Recommendations ---
function renderRecommendations(items) {
    var el = document.createElement("div");
    el.className = "recommend-container";
    var labelPrefix = isMobile()
        ? mobileLucide("clapperboard", "m-icon-sm")
        : "🎬 ";
    el.innerHTML = '<div class="recommend-label">' + labelPrefix + '根据搜索历史为你推荐：</div><div class="recommend-chips">' +
        items.map(function(item) { return '<button class="recommend-chip" data-keyword="' + escapeHtml(item) + '">' + escapeHtml(item) + '</button>'; }).join("") +
        '</div>';
    consoleOutput.appendChild(el);
    if (isMobile()) refreshMobileIcons(el);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// --- Video Preview（移动端 magnet / 桌面端 aria2 流式） ---
function isMobilePreview() {
    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) return true;
    return isMobile();
}

function openMagnetLink(magnetURI) {
    var a = document.createElement("a");
    a.href = magnetURI;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
}

function previewTorrent(magnetURI, title, btn) {
    if (!magnetURI) return;
    if (isMobilePreview()) {
        openMagnetLink(magnetURI);
        return;
    }

    var card = btn && btn.closest(".torrent-card");
    if (!card) return;

    var existing = card.querySelector(".torrent-preview");
    if (existing) existing.remove();

    var wrap = document.createElement("div");
    wrap.className = "torrent-preview";
    wrap.innerHTML = '<div class="torrent-preview-status">正在准备播放…</div>';
    card.appendChild(wrap);

    var encoded = encodeURIComponent(magnetURI);
    var pollCount = 0;
    var maxPolls = 30;

    function fallbackMagnet() {
        wrap.remove();
        openMagnetLink(magnetURI);
    }

    function poll() {
        fetch("/api/preview/status?magnet=" + encoded)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.aria2 === false) {
                    fallbackMagnet();
                    return;
                }
                var statusEl = wrap.querySelector(".torrent-preview-status");
                if (data.ready) {
                    if (statusEl) statusEl.remove();
                    var video = document.createElement("video");
                    video.controls = true;
                    video.preload = "metadata";
                    video.style.width = "100%";
                    video.style.borderRadius = "8px";
                    video.src = "/api/preview?magnet=" + encoded;
                    video.onerror = fallbackMagnet;
                    wrap.appendChild(video);
                    return;
                }
                var prog = data.progress != null ? data.progress : 0;
                var eta = Math.max(0, (maxPolls - pollCount) * 2);
                if (statusEl) {
                    statusEl.textContent = (data.filename ? data.filename + " · " : "")
                        + "正在缓冲… " + prog + "% · 约 " + eta + " 秒";
                }
                pollCount++;
                if (pollCount < maxPolls) {
                    setTimeout(poll, 2000);
                } else {
                    fallbackMagnet();
                }
            })
            .catch(function() {
                fallbackMagnet();
            });
    }
    poll();
}

// Magnet link click -> copy full link to clipboard
document.getElementById("consoleOutput").addEventListener("click", function(e) {
    var link = e.target.closest(".magnet-link");
    if (link) {
        e.preventDefault();
        var magnet = link.getAttribute("href");
        navigator.clipboard.writeText(magnet).then(function() {
            var orig = link.textContent;
            link.textContent = "✓ 已复制到剪贴板";
            setTimeout(function() { link.textContent = orig; }, 1500);
        });
        return;
    }
    var copyBtn = e.target.closest(".copy-btn");
    if (copyBtn) {
        var m = copyBtn.getAttribute("data-magnet");
        navigator.clipboard.writeText(m).then(function() {
            copyBtn.textContent = "✓ 已复制";
            copyBtn.style.background = "#4ec9b0"; copyBtn.style.color = "#1e1e1e";
            setTimeout(function() { copyBtn.textContent = "📋 复制链接"; copyBtn.style.background = ""; copyBtn.style.color = ""; }, 1500);
        });
        return;
    }
    var previewBtn = e.target.closest(".preview-btn");
    if (previewBtn) {
        previewTorrent(
            previewBtn.getAttribute("data-magnet"),
            previewBtn.getAttribute("data-title"),
            previewBtn
        );
        return;
    }
    var chip = e.target.closest(".recommend-chip");
    if (chip) {
        var keyword = chip.getAttribute("data-keyword");
        if (waitingForInput) {
            var inp = getActiveInputEl();
            if (inp) inp.value = keyword;
            submitInput();
        }
        return;
    }
});

// --- Run/Stop ---
function setRunning(running) {
    isRunning = running;
    runBtn.style.display = running ? "none" : "inline-block";
    stopBtn.style.display = running ? "inline-block" : "none";
    var mStop = document.getElementById("mobileStopBtn");
    if (mStop) {
        if (isMobile()) mStop.style.display = running ? "inline-flex" : "none";
        else mStop.style.removeProperty("display");
    }
    updateMobileFab(running);
    document.getElementById("mobileDot").className = "state-dot " + (running ? "running" : "idle");
    updateRunBtnVisibility();
    if (running) {
        document.body.classList.add("exec-running");
        setExecState("running");
        startTimer();
        if (isMobile()) switchTab("output");
    } else {
        document.body.classList.remove("exec-running");
    }
}
function handleSseData(data) {
    if (!data || data === "keepalive") return;
    if (data.indexOf("__SESSION__:") === 0) return;
    if (data === "__DONE__") {
        clearSearchProgress();
        stopTimer(); setExecState("done"); waitingForInput = false; hideInput();
        setRunning(false);
        log(">>> 执行完成", "system");
    } else if (data === "__STOPPED__") {
        clearSearchProgress();
        stopTimer(); setExecState("idle"); waitingForInput = false; hideInput();
        setRunning(false);
        log(">>> 执行已终止", "system");
    } else if (data.indexOf("__ERROR__:") === 0) {
        clearSearchProgress();
        stopTimer(); setExecState("error"); waitingForInput = false; hideInput();
        setRunning(false);
        log(data.substring(10), "error");
    } else if (data.indexOf("__RESULT__:") === 0) {
        stepCount++; log("=> " + data.substring(11).replace(/↎/g, "\n"), "result");
    } else if (data.indexOf("__MD__:") === 0) {
        stepCount++; log(data.substring(7).replace(/↎/g, "\n"), "md");
    } else if (data.indexOf("__TEXT__:") === 0) {
        stepCount++; log(data.substring(8).replace(/↎/g, "\n"), "text");
    } else if (data.indexOf("__INPUT__:") === 0) {
        showInput(data.substring(10).replace(/↎/g, "\n"));
    } else if (data.indexOf("__PROGRESS__:") === 0) {
        try { updateSearchProgress(JSON.parse(data.substring(12))); } catch (e) {}
    } else if (data.indexOf("__TORRENT__:") === 0) {
        clearSearchProgress();
        renderTorrentCards(JSON.parse(data.substring(12)));
    } else if (data.indexOf("__RECOMMEND__:") === 0) {
        renderRecommendations(JSON.parse(data.substring(14)));
    } else {
        stepCount++; log(data.replace(/↎/g, "\n"), "text");
    }
}
function runCode() {
    if (isRunning) return;
    hideInput();
    sseLineBuffer = "";
    setRunning(true); clearConsole(); log(">>> 开始执行...", "system");
    abortController = new AbortController();
    fetch("/api/execute", { method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ code: editor.getValue(), markdown: markdownMode, client_id: clientId }),
        signal: abortController.signal
    }).then(function(response) {
        var reader = response.body.getReader(), decoder = new TextDecoder();
        function read() {
            reader.read().then(function(result) {
                if (result.done) {
                    if (!waitingForInput) setRunning(false);
                    return;
                }
                sseLineBuffer += decoder.decode(result.value, {stream: true});
                var lines = sseLineBuffer.split("\n");
                sseLineBuffer = lines.pop();
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.indexOf("data: ") === 0) {
                        handleSseData(line.substring(6));
                    }
                }
                read();
            }).catch(function(e) {
                stopTimer();
                if (e.name === "AbortError") {
                    setExecState("idle");
                    log(">>> 已停止", "system");
                    waitingForInput = false;
                    hideInput();
                } else {
                    setExecState("error");
                    log("请求失败: " + e.message, "error");
                }
                if (!waitingForInput) setRunning(false);
            });
        }
        read();
    }).catch(function(e) {
        stopTimer();
        if (e.name === "AbortError") {
            setExecState("idle");
            log(">>> 已停止", "system");
            waitingForInput = false;
            hideInput();
        } else {
            setExecState("error");
            log("请求失败: " + e.message, "error");
        }
        if (!waitingForInput) setRunning(false);
    });
}
function stopCode() { waitingForInput = false; hideInput(); log(">>> 正在停止...", "system"); if (abortController) abortController.abort(); fetch("/api/stop", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ client_id: clientId }) }).catch(function() {}); }

// --- Console Input ---
function cleanInputPrompt(prompt) {
    var text = (prompt || "请输入:").replace(/↎/g, "\n");
    return text
        .replace(/[（(][^）)]*[）)]/g, " ")
        .replace(/输入\s*q\s*退出[^\n]*/gi, "")
        .replace(/\s+/g, " ")
        .trim() || "请输入";
}
function getActiveInputEl() {
    if (isMobile()) {
        return document.getElementById("mobileConsoleInput");
    }
    return document.getElementById("consoleInput");
}
function syncInputVisibility() {
    var row = document.getElementById("consoleInputRow");
    var sheet = document.getElementById("mobileInputSheet");
    if (!row || !sheet) return;

    var mobile = isMobile();
    document.body.classList.toggle("waiting-for-input", waitingForInput);

    row.style.removeProperty("display");
    sheet.style.removeProperty("display");
    row.classList.toggle("visible", waitingForInput && !mobile);
    sheet.classList.toggle("open", waitingForInput && mobile);

    if (waitingForInput && mobile) switchTab("output");
}

function hideInput() {
    waitingForInput = false;
    syncInputVisibility();
    document.getElementById("consoleInput").value = "";
    var mobileInp = document.getElementById("mobileConsoleInput");
    if (mobileInp) mobileInp.value = "";
    consoleOutput.style.paddingBottom = "";
}

function showInput(prompt) {
    waitingForInput = true;
    var raw = prompt || "请输入:";
    document.getElementById("inputPrompt").textContent = raw;
    document.getElementById("mobileInputPrompt").textContent = cleanInputPrompt(raw);
    document.getElementById("consoleInput").value = "";
    document.getElementById("mobileConsoleInput").value = "";

    syncInputVisibility();
    setExecState("waiting");

    setTimeout(function() {
        syncInputVisibility();
        if (isMobile()) {
            var sheet = document.getElementById("mobileInputSheet");
            var mobileInp = document.getElementById("mobileConsoleInput");
            if (mobileInp) mobileInp.focus();
            var content = sheet && sheet.querySelector(".mobile-input-sheet-content");
            var h = (sheet && sheet.offsetHeight) || (content && content.offsetHeight) || 160;
            consoleOutput.style.paddingBottom = (h + 16) + "px";
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        } else {
            consoleOutput.style.paddingBottom = "";
            var row = document.getElementById("consoleInputRow");
            var inp = document.getElementById("consoleInput");
            if (inp) inp.focus();
            if (row) row.scrollIntoView({ behavior: "smooth", block: "nearest" });
            var outputArea = document.querySelector(".output-area");
            if (outputArea) outputArea.scrollTop = outputArea.scrollHeight;
        }
    }, 50);
}
function submitInput() {
    var inp = getActiveInputEl();
    var val = inp ? inp.value : "";
    var savedPrompt = document.getElementById("inputPrompt").textContent;
    log("> " + val, "text");
    if (isRunning && val && val.toLowerCase() !== "q") startSearchProgress(val);
    fetch("/api/input", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({input: val, client_id: clientId}) })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.status === "ok") {
            hideInput();
            setExecState("running");
        } else {
            showInput(savedPrompt);
        }
    })
    .catch(function(e) {
        log("输入提交失败: " + e.message, "error");
        showInput(savedPrompt);
    });
}
document.getElementById("consoleInput").addEventListener("keydown", function(e) {
    if (e.key === "Enter") { e.preventDefault(); submitInput(); }
});
document.getElementById("mobileConsoleInput").addEventListener("keydown", function(e) {
    if (e.key === "Enter") { e.preventDefault(); submitInput(); }
});

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
        if (str.indexOf("/") !== -1 || str.match(/\.(lisp|txt)$/)) { e.preventDefault(); openFile(str); }
    }
});

// --- File link marks ---
var fileMarks = [];
function updateFileLinks() {
    fileMarks.forEach(function(m) { m.clear(); });
    fileMarks = [];
    var re = /\.(lisp|txt|lsp|md)$/;
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
        if (file && (file.indexOf("/") !== -1 || file.match(/\.(lisp|txt|lsp|md)$/))) { openFile(file); }
    }
});

// --- Run button visibility by file type ---
function isRunnableFile(name) { return !name || /\.(lisp|lsp)$/.test(name); }
function updateRunBtnVisibility() {
    var show = isRunnableFile(currentFile);
    document.querySelector(".editor-actions").style.display = show ? "" : "none";
    updateMobileFabVisibility();
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
syncMobileMdBtn();
syncMobileThemeBtn();