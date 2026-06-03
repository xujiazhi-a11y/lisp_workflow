"""
Lisp Workflow 解释器
基于 Lisp.py，扩展支持 AI 工作流

新增特性:
- 英文关键字 (define, lambda, if, begin, quote, set!, pipe, map, reduce, filter)
- 大模型调用 (call-llm)
- JSON 处理 (parse-json, to-json, extract-json)
- 管道操作 (pipe, ->)
- 高阶函数 (map, reduce, filter)
"""

import re
import sys
import math
import os
import io
import functools
from typing import Any, Callable, List, Dict, Optional

# 基准路径（脚本所在目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 导入工作流模块
# ============================================================
try:
    from workflow.llm import call_llm, call_llm_with_system
    from workflow.json_utils import parse_json, to_json, extract_json
    from workflow.text_utils import (
        remove_think_tags, format_string, 
        regex_match, regex_replace,
        split_text, join_text, strip_text
    )
    WORKFLOW_MODULES_LOADED = True
except ImportError:
    WORKFLOW_MODULES_LOADED = False
    print("警告: workflow 模块未找到，部分功能将不可用")

# ============================================================
# 基础类型定义
# ============================================================

class Symbol(str):
    """符号类型"""
    pass

Number = (int, float)
List = list
String = str

# 符号表（用于符号去重）
SYMBOL_TABLE = {}

def to_symbol(s: str, symbol_table: dict = None) -> Symbol:
    """将字符串转为符号"""
    if symbol_table is None:
        symbol_table = SYMBOL_TABLE
    if s not in symbol_table:
        symbol_table[s] = Symbol(s)
    return symbol_table[s]

# ============================================================
# 保留字定义（支持中英文）
# ============================================================

# 英文保留字
KW_DEFINE = to_symbol('define')
KW_LAMBDA = to_symbol('lambda')
KW_IF = to_symbol('if')
KW_BEGIN = to_symbol('begin')
KW_QUOTE = to_symbol('quote')
KW_SET = to_symbol('set!')
KW_DEFMACRO = to_symbol('defmacro')

# 中文保留字（保持兼容）
KW_定义 = to_symbol('定义')
KW_道 = to_symbol('道')
KW_如果 = to_symbol('如果')
KW_开始 = to_symbol('开始')
KW_引 = to_symbol('引')
KW_赋 = to_symbol('！赋')

# 工作流保留字
KW_PIPE = to_symbol('pipe')
KW_THREADED = to_symbol('->')
KW_MAP = to_symbol('map')
KW_REDUCE = to_symbol('reduce')
KW_FILTER = to_symbol('filter')
KW_LET = to_symbol('let')

# 程序终止符
EOF = Symbol('#<eof-object>')

# ============================================================
# 词法分析器（Tokenizer）
# ============================================================

class Tokenizer:
    """词法分析器"""

    def __init__(self, file):
        self.file = file
        self.line = ''

    def next_token(self):
        """读取下一个token"""
        while True:
            # 如果当前行有内容，先处理完
            if self.line == '':
                self.line = self.file.readline()
                if self.line == '':
                    return EOF

            # 替换阶段
            self.line = re.sub('【', ' ( ', self.line)
            self.line = re.sub('】', ' ) ', self.line)
            self.line = re.sub(r'\“', '"', self.line)
            self.line = re.sub(r'\”', '"', self.line)
            self.line = re.sub(r'；', ';', self.line)
            self.line = re.sub(r'（.*?）', '', self.line)

            # 跳过空行
            if not self.line.strip():
                self.line = ''
                continue

            # === 首先检查特殊字符 ===
            first_char = self.line[0]
            if first_char in "()'`[],[":
                self.line = self.line[1:]
                return first_char

            # === 跳过开头空白 ===
            if first_char.isspace():
                self.line = self.line[1:]
                continue

            # === 跳过注释 ===
            if first_char == ';':
                self.line = ''
                continue

            # === 处理字符串 ===
            if first_char == '"':
                rest = self.line[1:]  # Everything after the first quote
                
                # 跳过前导空白
                space_end = 0
                while space_end < len(rest) and rest[space_end].isspace():
                    space_end += 1
                
                # 查找闭合引号（从非空白部分开始搜索）
                has_closing = False
                closing_pos = -1  # Position in rest (0-indexed), +1 for the closing quote
                for i in range(space_end, len(rest)):
                    ch = rest[i]
                    if ch == '\\':
                        continue
                    if ch == '"':
                        has_closing = True
                        closing_pos = i + 1  # Position in rest, +1 includes closing quote
                        break
                    if ch in "()'`;{}[":
                        # 遇到特殊字符，说明引号后面不是字符串
                        break

                if has_closing:
                    # Token includes: opening quote (1 char) + content + closing quote
                    # closing_pos is in rest, so total token length = 1 + closing_pos
                    token = self.line[:1 + closing_pos]
                    self.line = self.line[1 + closing_pos:]
                    return token

                # 当前行没有闭合引号，使用多行字符串处理器
                in_string = True
                string_parts = []
                current_line = rest

                while in_string:
                    j = 0
                    while j < len(current_line):
                        ch = current_line[j]
                        if ch == '\\':
                            j += 2
                            continue
                        if ch == '"':
                            # 找到闭合引号
                            string_parts.append(current_line[:j+1])
                            self.line = current_line[j+1:]
                            in_string = False
                            break
                        j += 1

                    if in_string:
                        string_parts.append(current_line)
                        string_parts.append('\n')
                        self.line = ''

                        next_line = self.file.readline()
                        if next_line == '':
                            raise SyntaxError('字符串未闭合')
                        current_line = next_line

                return '"' + ''.join(string_parts)

            # === 解析标识符 ===
            if first_char.isalpha():
                i = 1
                while i < len(self.line) and not self.line[i].isspace() and self.line[i] not in "()'`,\";{}[]":
                    i += 1
                token = self.line[:i]
                self.line = self.line[i:]
                return token

            # === 解析其他标识符 ===
            i = 1
            while i < len(self.line) and not self.line[i].isspace() and self.line[i] not in "()'`,\";{}[]":
                i += 1
            token = self.line[:i]
            self.line = self.line[i:]
            return token

            # === 查找字符串 ===
            in_string = False
            string_start = -1
            i = 0
            while i < len(self.line):
                ch = self.line[i]
                if ch == '\\':
                    i += 2
                    continue
                if ch == '"':
                    if not in_string:
                        string_start = i
                        in_string = True
                    else:
                        token = self.line[string_start:i+1]
                        self.line = self.line[i+1:]
                        return token
                i += 1

            # 如果在字符串中但字符串未闭合
            if in_string:
                raise SyntaxError('字符串未闭合: ' + self.line)

            # 没有找到字符串，也没有特殊字符
            # === 解析标识符或运算符 ===
            # 如果首字符不是字母数字，需要单独处理
            if not first_char.isalnum() and first_char not in "_-":
                # 这是一个运算符或特殊字符
                self.line = self.line[1:]
                return first_char

            # === 解析标识符 ===
            while i < len(self.line) and not self.line[i].isspace() and self.line[i] not in "()'`,\";{}[]":
                i += 1
            token = self.line[:i]
            self.line = self.line[i:]
            return token

# ============================================================
# 语法解析器（Parser）
# ============================================================

def parse(tokens: Tokenizer):
    """解析token流为AST"""
    # 标记列表是否来自方括号（作为数据）
    DATA_LIST_MARKER = '__data__'

    def read(token):
        if token == '(' or token == '[':
            # 支持方括号作为列表边界
            close = ']' if token == '[' else ')'
            is_data = (token == '[')
            lst = []
            while True:
                token = tokens.next_token()
                if token == close:
                    # 如果来自方括号，标记为数据列表
                    if is_data:
                        return [DATA_LIST_MARKER] + lst
                    return lst
                elif str(token) == '#<eof-object>':
                    raise SyntaxError('程序异常终止')
                else:
                    lst.append(read(token))
        elif token == ')' or token == ']':
            raise SyntaxError('多余的 )')
        elif str(token) == '#<eof-object>':
            raise SyntaxError('程序异常终止')
        else:
            return atom(token)

    next_token = tokens.next_token()
    if str(next_token) == '#<eof-object>':
        return EOF
    if next_token == '(' or next_token == '[':
        close = ']' if next_token == '[' else ')'
        is_data = (next_token == '[')
        lst = []
        while True:
            token = tokens.next_token()
            if token == close:
                if is_data:
                    return [DATA_LIST_MARKER] + lst
                return lst
            elif str(token) == '#<eof-object>':
                raise SyntaxError('程序异常终止')
            else:
                lst.append(read(token))
    else:
        return atom(next_token)


def atom(token: str):
    """将token转换为原子值"""
    if token == '#t' or token == '#true':
        return True
    elif token == '#f' or token == '#false':
        return False
    elif token.startswith('"'):
        s = token[1:-1]
        # 支持常见的转义序列
        s = s.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
        s = s.replace('\\\\', '\\')
        s = s.replace('\\"', '"')
        return s

    # 尝试解析为数字
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            try:
                return complex(token.replace('i', 'j', 1))
            except ValueError:
                return to_symbol(token)

# ============================================================
# 环境与求值
# ============================================================

class Env(dict):
    """环境：存储变量绑定"""
    
    def __init__(self, params=(), args=(), outer=None):
        self.outer = outer
        
        # 如果参数是单个符号，接收所有实参作为列表
        if isinstance(params, Symbol):
            self.update({params: list(args)})
        else:
            if len(params) != len(args):
                raise TypeError(
                    f'形参个数({len(params)})和实参个数({len(args)})不匹配'
                )
            self.update(zip(params, args))
    
    def find(self, var):
        """查找变量所在的环境层"""
        if var in self:
            return self
        elif self.outer is None:
            raise LookupError(f'未定义的符号: {var}')
        else:
            return self.outer.find(var)

    def set_local(self, var, value):
        """设置变量，如果存在则更新，否则创建新的绑定"""
        if var in self:
            self[var] = value
        else:
            self[var] = value


class Procedure:
    """用户定义的过程（lambda）"""

    def __init__(self, params, body, env):
        self.params = params
        # 确保 body 中的符号是 Symbol 类型
        # 但保留字符串类型（用于字符串字面量）
        self.body = self._normalize_body(body)
        self.env = env

    def _normalize_body(self, body):
        """将 body 中的字符串（标识符）转换为 Symbol，保留字符串（字面量）"""
        def convert(item):
            if isinstance(item, str):
                # 保留字符串类型，不转换为 Symbol
                # 这样字符串字面量会被当作常量返回
                return item
            elif isinstance(item, list):
                return [convert(x) for x in item]
            return item
        return convert(body) if isinstance(body, list) else body

    def __call__(self, *args):
        return evaluate(self.body, Env(self.params, args, self.env))


# ============================================================
# 内置函数定义
# ============================================================

def make_global_env():
    """创建全局环境"""
    env = Env()
    
    # 数学函数
    env.update(vars(math))
    
    # 基本运算
    env.update({
        '+': lambda *args: sum(args),
        '-': lambda *args: args[0] - sum(args[1:]) if len(args) > 1 else -args[0],
        '*': lambda *args: functools.reduce(lambda a, b: a * b, args, 1),
        '/': lambda *args: functools.reduce(lambda a, b: a / b, args) if len(args) > 1 else 1/args[0],
        'mod': lambda a, b: a % b,
        '%': lambda a, b: a % b,
        
        # 比较运算
        '>': lambda a, b: a > b,
        '<': lambda a, b: a < b,
        '>=': lambda a, b: a >= b,
        '<=': lambda a, b: a <= b,
        '=': lambda a, b: a == b,
        'eq?': lambda a, b: a is b,
        'equal?': lambda a, b: a == b,
        
        # 布尔运算
        'and': lambda *args: all(args),
        'or': lambda *args: any(args),
        'not': lambda x: not x,
        
        # 列表操作
        'list': lambda *args: list(args),
        'cons': lambda a, b: [a] + (b if isinstance(b, list) else [b]),
        'car': lambda lst: lst[0],
        'cdr': lambda lst: lst[1:],
        'first': lambda lst: lst[0],
        'rest': lambda lst: lst[1:],
        'length': len,
        'append': lambda *lsts: sum(lsts, []),
        'reverse': lambda lst: lst[::-1],
        'nth': lambda n, lst: lst[n],
        'take': lambda n, lst: lst[:n],
        'drop': lambda n, lst: lst[n:],
        
        # 类型判断
        'null?': lambda x: x == [] or x is None,
        'list?': lambda x: isinstance(x, list),
        'number?': lambda x: isinstance(x, Number),
        'string?': lambda x: isinstance(x, str) and not isinstance(x, Symbol),
        'symbol?': lambda x: isinstance(x, Symbol),
        'boolean?': lambda x: isinstance(x, bool),
        'procedure?': callable,
        'empty?': lambda x: len(x) == 0 if hasattr(x, '__len__') else False,
        'dict': lambda *args: {args[i]: args[i+1] for i in range(0, len(args), 2)},
        'dict?': lambda x: isinstance(x, dict),
        
        # 字典操作
        'get': lambda d, k: d.get(k) if isinstance(d, dict) else None,
        'put': lambda d, k, v: (d.update({k: v}), d)[1] if isinstance(d, dict) else d,
        'keys': lambda d: list(d.keys()) if isinstance(d, dict) else [],
        'values': lambda d: list(d.values()) if isinstance(d, dict) else [],
        
        # 字符串操作
        'str': lambda *args: ''.join(str(a) for a in args),
        'str-concat': lambda *args: ''.join(str(a) for a in args),
        'str-join': lambda sep, lst: sep.join(str(x) for x in lst),
        'str-split': lambda sep, s: s.split(sep),
        'str-replace': lambda old, new, s: s.replace(old, new),
        'str-trim': lambda s: s.strip(),
        'str-upper': lambda s: s.upper(),
        'str-lower': lambda s: s.lower(),
        'str-starts?': lambda prefix, s: s.startswith(prefix),
        'str-ends?': lambda suffix, s: s.endswith(suffix),
        'str-contains?': lambda substr, s: substr in s,
        'format': lambda template, *args: template % args if '%' in template else template.format(*args),
        
        # 打印输出
        'print': lambda *args: print(' '.join(to_lisp_str(x) if not isinstance(x, str) else x for x in args)),
        'println': lambda *args: print(' '.join(to_lisp_str(x) if not isinstance(x, str) else x for x in args)),
        'pr': lambda x: print(x, end=''),
        
        # I/O - 使用固定基准路径
        'read-file': lambda path: open(os.path.join(BASE_DIR, path), 'r', encoding='utf-8').read(),
        'write-file': lambda path, content: open(os.path.join(BASE_DIR, path), 'w', encoding='utf-8').write(content),
    })
    
    # ============================================================
    # 高阶函数
    # ============================================================
    
    def lisp_map(fn, lst):
        """map: 对列表每项应用函数"""
        return [fn(x) for x in lst]
    
    def lisp_reduce(fn, init, lst):
        """reduce: 折叠列表"""
        return functools.reduce(fn, lst, init)
    
    def lisp_filter(fn, lst):
        """filter: 过滤列表"""
        return [x for x in lst if fn(x)]
    
    def lisp_pipe(init, *fns):
        """pipe: 管道操作，值依次流经各函数"""
        result = init
        DATA_LIST_MARKER = '__data__'
        for fn in fns:
            if isinstance(fn, list) and len(fn) > 0 and fn[0] == DATA_LIST_MARKER:
                # 移除标记
                fn = fn[1:]
            result = fn(result)
        return result
    
    def lisp_threaded(init, *forms):
        """->: 线程宏，将值作为第一个参数传入后续每个表达式"""
        result = init
        DATA_LIST_MARKER = '__data__'
        for form in forms:
            if isinstance(form, list):
                # 检查是否是带 __data__ 标记的列表
                if len(form) > 0 and form[0] == DATA_LIST_MARKER:
                    # 移除标记
                    form = form[1:]
                if len(form) > 0:
                    # (f args...) -> (f result args...)
                    fn = evaluate(form[0], env)
                    args = [evaluate(a, env) for a in form[1:]]
                    result = fn(result, *args)
            else:
                fn = evaluate(form, env)
                result = fn(result)
        return result
    
    env.update({
        'map': lisp_map,
        'reduce': lisp_reduce,
        'filter': lisp_filter,
        'pipe': lisp_pipe,
        '->': lisp_threaded,
        'each': lambda fn, lst: [fn(x) for x in lst][-1],  # 执行副作用
    })
    
    # ============================================================
    # JSON 处理
    # ============================================================
    
    if WORKFLOW_MODULES_LOADED:
        env.update({
            'parse-json': parse_json,
            'to-json': lambda data: to_json(data),
            'extract-json': lambda s, d=None: extract_json(s, default=d),
        })
    else:
        import json
        env.update({
            'parse-json': json.loads,
            'to-json': lambda data: json.dumps(data, ensure_ascii=False, indent=2),
            'extract-json': lambda s: json.loads(re.search(r'(\[.*\]|\{.*\})', s, re.DOTALL).group(1)),
        })
    
    # ============================================================
    # 文本处理
    # ============================================================
    
    if WORKFLOW_MODULES_LOADED:
        env.update({
            'remove-think': remove_think_tags,
            'regex-match': regex_match,
            'regex-replace': regex_replace,
            'strip': strip_text,
        })
    else:
        env.update({
            'remove-think': lambda s: re.sub(r'<(think|thinking|thought)[^>]*>.*?</\1\s*>', '', s, flags=re.DOTALL).strip(),
            'regex-match': lambda p, s: re.search(p, s).group(0) if re.search(p, s) else None,
            'regex-replace': lambda p, r, s: re.sub(p, r, s),
            'strip': lambda s: s.strip(),
        })
    
    # ============================================================
    # 大模型调用
    # ============================================================
    
    if WORKFLOW_MODULES_LOADED:
        env.update({
            'call-llm': call_llm,
            'llm': call_llm,  # 别名
        })
    else:
        def mock_llm(prompt):
            return f"[MOCK LLM RESPONSE] {prompt[:50]}..."
        env.update({
            'call-llm': mock_llm,
            'llm': mock_llm,
        })
    
    return env


# 全局环境
GLOBAL_ENV = make_global_env()

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
        req = urllib.request.Request(FEISHU_WEBHOOK, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return "飞书发送成功" if result.get('code') == 0 or result.get('StatusCode') == 0 else f"发送失败: {result}"
    except Exception as e:
        return f"飞书发送失败: {str(e)}"

GLOBAL_ENV['send-to-feishu'] = feishu_send


# ============================================================
# 求值器
# ============================================================

def evaluate(exp, env: Env = GLOBAL_ENV):
    """求值表达式"""

    # None 直接返回
    if exp is None:
        return exp

    # 符号：从环境查找
    if isinstance(exp, Symbol):
        return env.find(exp)[exp]

    # 非列表：常量直接返回
    if not isinstance(exp, list):
        return exp

    # 空列表返回 None
    if len(exp) == 0:
        return None

    # ========== 数据列表（来自方括号） ==========
    # 检查是否是标记为数据的列表（如 [1 2 3]）
    DATA_LIST_MARKER = '__data__'
    if len(exp) > 0 and exp[0] == DATA_LIST_MARKER:
        # 返回列表内容（去掉标记）
        # 需要递归移除所有层的 __data__ 标记
        def unwrap_data_list(lst):
            result = []
            for item in lst:
                if isinstance(item, list) and len(item) > 0 and item[0] == DATA_LIST_MARKER:
                    # 这个元素本身也是来自方括号，递归处理
                    result.append(unwrap_data_list(item[1:]))
                elif isinstance(item, list) and len(item) > 0:
                    # 检查是否有深层的 __data__ 标记（如 lambda 参数中的）
                    result.append(unwrap_data_list(item))
                else:
                    result.append(item)
            return result
        return unwrap_data_list(exp[1:])

    # ========== 特殊形式 ==========

    op = exp[0]

    # 检查 op 是否有效（字符串或符号）
    # 注意：如果是列表（来自方括号解析的 lambda 表达式），会在下面处理

    # quote / 引
    if op == KW_QUOTE or op == KW_引:
        return exp[1]
    
    # if / 如果
    if op == KW_IF or op == KW_如果:
        _, test, conseq, *alt = exp
        alt = alt[0] if alt else None
        return evaluate(conseq if evaluate(test, env) else alt, env)
    
    # define / 定义
    if op == KW_DEFINE or op == KW_定义:
        if isinstance(exp[1], list):
            # (define (f x) body) -> (define f (lambda (x) body))
            name, params = exp[1][0], exp[1][1:]
            body = exp[2] if len(exp) == 3 else [KW_BEGIN] + exp[2:]
            env[name] = Procedure(params, body, env)
        else:
            _, name, value = exp
            env[name] = evaluate(value, env)
        return None
    
    # set! / 赋
    if op == KW_SET or op == KW_赋:
        _, var, val = exp
        env.find(var)[var] = evaluate(val, env)
        return None
    
    # lambda / 道
    if op == KW_LAMBDA or op == KW_道:
        _, params, *body = exp
        # 支持方括号参数: (lambda [x y] ...) 或 (lambda (x y) ...)
        # 移除 __data__ 标记
        DATA_LIST_MARKER = '__data__'
        if isinstance(params, list) and len(params) > 0 and params[0] == DATA_LIST_MARKER:
            params = params[1:]  # 移除标记
        if isinstance(params, list):
            # 参数已经是列表（如来自圆括号解析）
            params = [to_symbol(str(p)) if isinstance(p, Symbol) else to_symbol(p) for p in params]
        elif isinstance(params, Symbol):
            s = str(params)
            if s.startswith('[') and s.endswith(']'):
                # 解析 [x y z] 为参数列表
                inner = s[1:-1].strip()
                if inner:
                    params = [to_symbol(p.strip()) for p in inner.split() if p.strip()]
                else:
                    params = []
        body = body[0] if len(body) == 1 else [KW_BEGIN] + body
        return Procedure(params, body, env)
    
    # begin / 开始
    if op == KW_BEGIN or op == KW_开始:
        result = None
        for e in exp[1:]:
            result = evaluate(e, env)
        return result
    
    # let: (let [[x 1] [y 2]] body1 body2 ...)
    # 支持方括号绑定语法: (let [[name value] ...] body...)
    if op == KW_LET:
        _, bindings, *bodies = exp
        # 处理绑定列表：可能是 [name value] 或 (name value)
        # 如果 bindings 本身带有 __data__ 标记，需要移除
        DATA_LIST_MARKER = '__data__'
        if isinstance(bindings, list) and len(bindings) > 0 and bindings[0] == DATA_LIST_MARKER:
            # bindings 来自方括号解析：['__data__', [binding1], [binding2], ...]
            binding_list = bindings[1:]  # 移除标记
        else:
            binding_list = bindings

        # 创建新的环境层
        new_env = Env((), (), env)

        # 逐个处理绑定，让后续绑定能引用前面的绑定
        for b in binding_list:
            # 检查是否是带 __data__ 标记的绑定（来自方括号）
            if isinstance(b, list) and len(b) > 0 and b[0] == DATA_LIST_MARKER:
                # 格式: ['__data__', name, value]
                # 移除标记，取 name 和 value
                if len(b) >= 3:
                    name = b[1]
                    value = evaluate(b[2], new_env)
                    new_env[name] = value
                elif len(b) == 2:
                    new_env[b[1]] = None
            elif isinstance(b, list) and len(b) >= 2:
                # 普通绑定 (name value)
                name = b[0]
                value = evaluate(b[1], new_env)
                new_env[name] = value
            elif isinstance(b, list) and len(b) == 1:
                # 单元素列表
                new_env[b[0]] = None

        # 执行所有 body 表达式，返回最后一个
        result = None
        for body in bodies:
            result = evaluate(body, new_env)
        return result
    
    # pipe: (pipe init fn1 fn2 ...)
    if op == KW_PIPE:
        _, init, *fns = exp
        result = evaluate(init, env)
        for fn_exp in fns:
            fn = evaluate(fn_exp, env)
            result = fn(result)
        return result
    
    # ->: (-> init (fn args...) (fn2 args...) ...)
    if op == KW_THREADED:
        _, init, *forms = exp
        result = evaluate(init, env)
        for form in forms:
            if isinstance(form, list):
                # 检查是否是 lambda 或其他特殊形式
                if form[0] == KW_LAMBDA or form[0] == KW_道:
                    # (lambda ...) 先求值得到函数，然后调用
                    fn = evaluate(form, env)
                    result = fn(result)
                else:
                    # (fn args...) -> (fn result args...)
                    fn = evaluate(form[0], env)
                    args = [evaluate(a, env) for a in form[1:]]
                    result = fn(result, *args)
            else:
                fn = evaluate(form, env)
                result = fn(result)
        return result
    
    # map: (map fn list)
    if op == KW_MAP:
        _, fn_exp, lst_exp = exp
        fn = evaluate(fn_exp, env)
        lst = evaluate(lst_exp, env)
        return [fn(x) for x in lst]
    
    # reduce: (reduce fn init list)
    if op == KW_REDUCE:
        _, fn_exp, init_exp, lst_exp = exp
        fn = evaluate(fn_exp, env)
        init = evaluate(init_exp, env)
        lst = evaluate(lst_exp, env)
        # 转换列表中的 Symbol 为对应的值
        lst = [env.find(x)[x] if isinstance(x, Symbol) else x for x in lst]
        return functools.reduce(fn, lst, init)
    
    # filter: (filter fn list)
    if op == KW_FILTER:
        _, fn_exp, lst_exp = exp
        fn = evaluate(fn_exp, env)
        lst = evaluate(lst_exp, env)
        return [x for x in lst if fn(x)]
    
    # ========== 函数调用 ==========
    # 处理函数调用
    proc = evaluate(exp[0], env)
    # 如果 proc 是 lambda 表达式（列表），先求值
    if isinstance(proc, list) and len(proc) > 0:
        DATA_LIST_MARKER = '__data__'
        if isinstance(proc[0], Symbol) and proc[0] == KW_LAMBDA:
            proc = evaluate(proc, env)
    args = [evaluate(arg, env) for arg in exp[1:]]
    return proc(*args)


# ============================================================
# 辅助函数
# ============================================================

def to_lisp_str(exp) -> str:
    """将 Python 值转换为 Lisp 字符串表示"""
    if exp is True:
        return "#t"
    elif exp is False:
        return "#f"
    elif isinstance(exp, Symbol):
        return exp
    elif isinstance(exp, str):
        return f'"{exp}"'
    elif isinstance(exp, list):
        return '(' + ' '.join(map(to_lisp_str, exp)) + ')'
    else:
        return str(exp)


def run(code: str, env: Env = GLOBAL_ENV):
    """运行 Lisp 代码字符串"""
    from io import StringIO
    tokens = Tokenizer(StringIO(code))
    result = None
    while True:
        exp = parse(tokens)
        if exp is EOF:
            break
        result = evaluate(exp, env)
    return result


def run_file(path: str, env: Env = GLOBAL_ENV):
    """运行 Lisp 文件"""
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()
    return run(code, env)


def repl(prompt: str = "workflow-lisp> "):
    """交互式 REPL"""
    while True:
        try:
            code = input(prompt)
            if code.strip() == '':
                continue
            if code.strip() in ('exit', 'quit', '(exit)', '(quit)'):
                break
            result = run(code)
            if result is not None:
                print(to_lisp_str(result) if not isinstance(result, str) else result)
        except EOFError:
            break
        except Exception as e:
            print(f"错误: {type(e).__name__}: {e}")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 运行文件
        run_file(sys.argv[1])
    else:
        # 进入 REPL
        print("Lisp Workflow")
        print("输入 (exit) 退出")
        print()
        repl()
