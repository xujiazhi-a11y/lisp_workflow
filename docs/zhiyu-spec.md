# 智语 Lisp（Zhiyu Lisp）运行时规格 — M0

> **版本**: M0（规格冻结）  
> **基准实现**: `py/workflow_lisp.py` + `py/workflow_server.py`（Python 参考实现）  
> **目标实现**: `zhiyu-core/`（C 解释器/VM + Python FFI 宿主）  
> **状态**: 本文档为 C 重构的单一事实来源（Single Source of Truth）

---

## 1. 目标与范围

### 1.1 项目目标

用 **C 语言**实现更基础、健壮的工作流 Lisp 运行时，具备：

- 更高执行性能（相对 Python 树遍历解释器）
- **Incremental Compilation + Runtime Redefinition**（运行中 `(load ...)` / 重定义函数不停机）
- 完整保留现有 **汉化语法**、**标准库契约**、**AI/工作流宿主能力**

Python 解释器 (`workflow_lisp.py`) **保留不删**，作为 `--legacy` 对照与回退路径；产品默认执行路径在 M3 完成后切换至 `zhiyu-core`。

### 1.2 M0 交付物

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 语言规格 | `docs/zhiyu-spec.md` | 本文档 |
| Builtin 清单 | `docs/zhiyu-builtin-manifest.json` | 机器可读，供 C/测试生成 |
| 回归索引 | `tests/regression/README.md` | 分阶段验收用例 |

### 1.3 非目标（M0 不写实现）

- 字节码编译器优化（M4）
- Common Lisp 全兼容
- 将 AI/浏览器/种子搜索重写为 C

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│  workflow_server.py（Python 宿主）                       │
│  SSE I/O · 配置 · Session · 静态前端                      │
└───────────────────────────┬─────────────────────────────┘
                            │ FFI（M3：子进程管道 / pybind11）
┌───────────────────────────▼─────────────────────────────┐
│  zhiyu-core（C）                                          │
│  Lexer · Parser · Evaluator · Symbol 表 · GC · load     │
│  中文脱糖 · 宏展开 · 热更新（symbol 间接调用）            │
└───────────────────────────┬─────────────────────────────┘
                            │ 宿主原语回调
┌───────────────────────────▼─────────────────────────────┐
│  py/workflow/*.py                                        │
│  ai_services · llm · torrent · json_utils · text_utils   │
│  Playwright 浏览器 · Excel · 飞书                        │
└─────────────────────────────────────────────────────────┘
```

**原则**: 语言语义在 C；副作用与外部服务在 Python。

---

## 3. 词法（Lexer）

### 3.1 源文件

- 编码: **UTF-8**
- 换行: `\n`（`\r\n` 应归一化）
- 注释: `;` 至行尾；`；`（全角）归一化为 `;`

### 3.2 括号与分隔符

| 输入 | 解析为 |
|------|--------|
| `(` `)` | 列表 |
| `[` `]` | 列表（与 `()` 等价） |
| `（` `）` | `(` `)` |
| `【` `】` | `(` `)` |
| `` ` `` | 反引号（保留 token，M1 可不实现 quasiquote） |
| `'` | 简引号（保留 token） |
| `,` | 保留 token |

### 3.3 字符串

- 定界符: `"..."`
- 支持 `\n` `\t` `\r` `\\` `\"` 转义
- **多行字符串**: 开引号未闭合时继续读下一行，直至闭合
- 未闭合 → 错误: `字符串未闭合`

### 3.4 原子（Atom）

| Token | 类型 |
|-------|------|
| `#t` `#true` `#真` | 布尔真 |
| `#f` `#false` `#假` | 布尔假 |
| 整数 / 浮点 | number |
| 含 `i` 且以数字开头的 token | complex（可选，与 Python 版一致） |
| 其它标识符 | symbol（intern 到全局符号表） |

标识符字符: 字母、数字、及 `_-!?+%*/<>=` 等（与 Python 版一致：非空白、非括号即继续读入）。**中文标识符完全支持**。

### 3.5 关键字参数（Keyword）

- 以 `:` 开头的 symbol（如 `:image`）在求值时 **自求值**（不求值 lookup）
- 用于 `(ai-text ... :image path)` 等宿主原语

---

## 4. 语法（Parser）

- S 表达式；多个顶层形式顺序求值，**返回最后一个顶层形式的值**
- 空列表 `()` → 求值为 `nil`（Python 版为 `None`，新实现统一为 **nil 对象**；对外可打印为 `()` 或 `#nil`）
- EOF 在非平衡括号内 → `程序异常终止`
- 多余 `)` → `多余的 )`

---

## 5. 特殊形式（Special Forms）

以下形式 **不求值第一个子表达式**（除 noted）。

### 5.1 绑定与过程

| 英文 | 中文 | 语法 | 语义 |
|------|------|------|------|
| `define` | `定义` | `(define name expr)` | 求值 expr，绑定到 name（当前 env） |
| | | `(define name e1 e2 ...)` | 等价 `(define name (begin e1 e2 ...))` |
| | | `(define (f x ...) body...)` | 等价 `(define f (lambda (x ...) body...))` |
| `lambda` | `道` `规定` | `(lambda (x ...) body...)` | 创建闭包；多 body → `(begin ...)` |
| `let` | `令` `命` | `(let ((x 1) (y 2)) body...)` | 新 env；绑定顺序求值（递归 let，非 let*） |
| `set!` | `！赋` `赋` | `(set! var expr)` | 在 **var 所在 env 链** 上更新绑定 |

### 5.2 控制流

| 英文 | 中文 | 语法 | 语义 |
|------|------|------|------|
| `if` | `如果` | `(if test conseq alt?)` | 短路分支 |
| `cond` | `情况符合` | `(cond (t1 e...) (else e...) ...)` | 顺序测试；`else`/`否则`/`其它情况` 为无条件分支 |
| `begin` | `开始` | `(begin e...)` | 顺序求值，返回最后值 |
| `quote` | `引` | `(quote x)` | 返回 x 不求值 |
| `and` | `与` | `(and e...)` | 短路；返回最后真值或第一个假值 |
| `or` | `或` | `(or e...)` | 短路；返回第一个真值或 `#f` |

### 5.3 宏与模块

| 英文 | 中文 | 语法 | 语义 |
|------|------|------|------|
| `defmacro` | `定义宏` | `(defmacro name (p...) template)` | 注册宏；调用时模板替换后 re-eval |
| `macroexpand` | `宏展开` | `(macroexpand name)` | 返回宏模板 AST |
| `load` | `引入` | `(load "path")` | 见 §8 |

### 5.4 工作流语法糖（内置特殊形式）

| 形式 | 中文别名 | 语法 | 语义 |
|------|----------|------|------|
| `pipe` | — | `(pipe init f1 f2 ...)` | `init` 依次过函数 |
| `->` | — | `(-> init (f a...) ...)` | 线程宏：首参插入 |
| `map` | `映射` `批处理` | `(map fn list)` | 列表映射 |
| `reduce` | `归约` `顺序执行` | `(reduce fn init list)` | 折叠 |
| `filter` | `过滤` `筛选` | `(filter fn list)` | 过滤 |
| `each` | `遍历` | `(each fn list)` | 副作用遍历，返回最后一项结果 |

### 5.5 函数调用

`(operator arg...)` — operator 与 args 均求值；operator 必须为可调用过程。

**额外规则**（与 Python 版一致）:

- 若 operator 求值为「未求值的 lambda 列表」`(lambda ...)`，先对其求值得闭包再调用
- `and` / `or` 作为特殊形式处理，**不**走函数调用路径

---

## 6. 数据模型

| 类型 | 说明 | 备注 |
|------|------|------|
| nil | 空值 | `null?` 对 `nil` 和 `()` 为真 |
| bool | `#t` / `#f` | |
| number | int / float / complex | |
| string | UTF-8 字符串 | 与 symbol 区分 |
| symbol | intern 唯一 | 含中文名 |
| pair / list | 可变或不可变列表（M1 可用数组实现） | `cons` 语义见 §7 |
| procedure | 用户 `lambda` 闭包 | |
| native | C/FFI 内置过程 | |
| dict | 键值映射 | 字符串键；`(dict k1 v1 k2 v2 ...)` |

**真值**: 仅 `#f` 为假；`nil`、空列表、`0` 均为真（与 Python 版一致）。

---

## 7. 求值语义（关键细节）

### 7.1 环境（Env）

- 链式作用域；`define` 写入 **当前** env
- `set!` 使用 `find` 定位已有绑定层
- `lambda` 捕获定义时 env（静态作用域）
- 单参数 rest: `(lambda xs ...)` — xs 绑定为 **实参列表**

### 7.2 `cons` / 列表

Python 参考实现:

```lisp
(cons a b) => (cons a b)  ; b 非 list 时结果为 improper list 的近似 [a]++b
```

C 版 M1 可简化为: `b` 必须为 list；M2 对齐 Python 行为。

### 7.3 `append`

- **可变语义**: 第一个参数原地 `extend`（与 Python 版一致）

### 7.4 `format`

- 若模板含 `{{key}}` → 按 `(format tpl key1 val1 key2 val2 ...)` 替换
- 否则 → Python `%` 格式化 `(format tpl arg...)`

### 7.5 `sort`

- `(sort cmp-fn list)` — 比较函数接收两个元素，返回 bool

### 7.6 错误

- 未定义符号: `未定义的符号: {name}`（Python 版现用 `NameError`）
- 参数个数不匹配: `形参个数(n)和实参个数(m)不匹配`
- 用户可见错误 **一律中文**（见 §12）

---

## 8. 模块加载（`load` / `引入`）

```
(load "相对或绝对路径")
```

- **BASE_DIR**: 宿主设置；Web 模式下为 `py/examples/`
- 相对路径相对于 BASE_DIR
- **已加载缓存**: 同一规范化绝对路径默认只加载一次（Python 版 `_loaded_files`）
- **热更新模式**（M4，新引擎）:
  - `(load "path" :reload #t)` 或宿主 API 强制 reload
  - 重新执行文件内 `define` → 更新 symbol 函数槽
  - 已在执行的旧调用栈继续用旧闭包；新调用用新定义

---

## 9. 宏系统

- 存储于全局 `MACRO_TABLE`: `name → (params, template)`
- 展开: 实参替换模板中的 symbol（无 hygiene，与 Python 版一致）
- 中文宏名: `_CN_MACRO_ALIASES`（当前与英文名相同，预留扩展）
- 展开后 **递归 evaluate**

---

## 10. 汉化层

### 10.1 特殊形式中文关键字

| 中文 | 英文 |
|------|------|
| 定义 | define |
| 道 / 规定 | lambda |
| 如果 | if |
| 情况符合 | cond |
| 否则 / 其它情况 | cond else 分支 |
| 开始 | begin |
| 引 | quote |
| ！赋 / 赋 | set! |
| 定义宏 | defmacro |
| 宏展开 | macroexpand |
| 引入 | load |
| 令 / 命 | let |
| 映射 / 批处理 | map |
| 归约 / 顺序执行 | reduce |
| 过滤 / 筛选 | filter |
| 遍历 | each |
| 与 / 或 | and / or |

### 10.2 内置函数中文别名（`_CN_ALIASES`）

完整映射见 `docs/zhiyu-builtin-manifest.json` → `cn_aliases`。

解析规则:

1. 特殊形式: 求值器直接识别中文 op
2. 普通调用: env 中预注册中文名 → 同一 native 函数
3. 兜底: 符号 lookup 失败时查 `_CN_ALIASES` → 再查 GLOBAL_ENV

---

## 11. 内置函数注册表

分 **Tier** 表示 C 实现阶段；**FFI** 表示保留 Python 实现。

### Tier 0 — 核心（M1 必须）

算术: `+` `-` `*` `/` `mod` `%`  
比较: `>` `<` `>=` `<=` `=` `eq?` `equal?`  
逻辑: `and` `or` `not`  
列表: `list` `cons` `car` `cdr` `first` `rest` `length` `append` `reverse` `nth` `take` `drop` `member?`  
数学: `square` `sqrt` `expt` `abs` `min` `max` `average` `even?` `odd?` `prime?` `divides?` + `math` 常用导出  
类型: `null?` `list?` `number?` `string?` `symbol?` `boolean?` `procedure?` `empty?`  
字符串: `str` `str-concat` `str-join` `str-split` `str-replace` `str-trim` `str-upper` `str-lower` `str-starts?` `str-ends?` `str-contains?` `format`  
字典: `dict` `dict?` `get` `put` `keys` `values`  
I/O: `read-file` `write-file`（相对 BASE_DIR）  
转换: `to-number`  
排序: `sort`  
输出: `print` `println` `pr`（宿主可替换）

### Tier 1 — 工作流（M2）

高阶: `map` `reduce` `filter` `pipe` `->` `each`（特殊形式 + env 注册）  
JSON: `parse-json` `to-json` `extract-json`  
文本: `remove-think` `regex-match` `regex-replace` `strip`

### Tier 2 — 宿主 FFI（M3，Python 实现）

#### AI / 媒体

| 函数 | 中文 | 签名 | 实现 |
|------|------|------|------|
| `call-llm` | 调用模型 | `(call-llm prompt)` | `workflow/llm.py` |
| `llm` | — | 别名 | |
| `ai-text` | AI文本 | `(ai-text provider model prompt [:image path])` | `workflow/ai_services.py` |
| `ai-image` | AI图像 | `(ai-image provider model prompt [:ref-image path])` | |
| `ai-video` | AI视频 | `(ai-video provider first last prompt duration)` | |
| `video-concat` | 视频拼接 | `(video-concat paths output)` | |
| `slideshow-video` | 静帧拼视频 | `(slideshow-video paths output duration [:title t])` | **Python 版未注册，M3 必须补齐** |

#### 种子 / 历史

| 函数 | 中文 | 签名 |
|------|------|------|
| `torrent-search` | 搜索种子 | `(torrent-search keyword)` |
| `torrent-guess-en` | 猜测英文片名 | `(torrent-guess-en title)` |
| `build-search-term` | 构建搜索词 | `(build-search-term cn en?)` |
| `search-progress` | 发送搜索进度 | `(search-progress msg [percent] [eta])` |
| `emit-torrent-results` | 发送种子结果 | `(emit-torrent-results results)` |
| `emit-recommendations` | 发送推荐 | `(emit-recommendations items)` |
| `load-history` | 读取历史 | `(load-history)` |
| `save-history` | 保存历史 | `(save-history data)` |

#### 交互 I/O（Web 宿主注入）

| 函数 | 中文 | 行为 |
|------|------|------|
| `print` / `println` | 打印/输出/显示 | SSE `__TEXT__:` / `__MD__:` |
| `input` | 输入 | SSE `__INPUT__:` 阻塞 |
| `interact` | 选择/交互 | SSE `__INTERACT__:` JSON 选项卡 |
| `user-input` | 用户输入 | CLI `input()` |
| `client-input` | 用户输入数据 | 执行前注入 dict（多字段表单） |
| `wait-seconds` | 等待秒数 | sleep |

#### 通知 / 集成

| 函数 | 中文 |
|------|------|
| `send-to-feishu` | 发送飞书 |

#### 浏览器自动化（Playwright）

| 函数 | 中文 |
|------|------|
| `browser-start` | 浏览器启动 |
| `browser-open` | 浏览器打开 |
| `browser-close` | 浏览器关闭 |
| `page-find` | 页面查找 |
| `page-find-all` | 页面查找所有 |
| `elem-fill` | 元素填写 |
| `elem-click` | 元素点击 |
| `page-exec` | 页面执行 |
| `page-screenshot` | 页面截图 |
| `page-scan` | 扫描页面元素 |
| `page-wait-login` | 等待登录跳转 |
| `page-click` | 点击元素 |
| `page-click-text` | 点击文本 |
| `page-wait-selector` | 等待元素出现 |
| `page-check` | 勾选 |
| `page-click-checkbox` | 勾选文本 |

#### 其它

| 函数 | 中文 |
|------|------|
| `excel-read` | Excel读取 |
| `format-date` | 格式化日期 |

### 已知 Python 版缺口（新引擎应修复）

| 项 | 说明 |
|----|------|
| `pair?` / `成对?` | 别名存在，**无实现** → M2 添加 `(pair? x)` |
| `slideshow-video` | 别名存在，**未注册 GLOBAL_ENV** → M3 注册 |

---

## 12. 错误与国际化

- 所有 **用户可见** 错误消息为 **中文**
- Python 参考: `py/workflow/user_errors.py` → `format_user_error`
- C 版: 内置异常类型映射 + 常见 errno 消息翻译
- **Traceback / 堆栈** 不对用户展示时可保留英文；SSE `__ERROR__:` 仅发 `format_user_error` 结果

---

## 13. 宿主集成契约（workflow_server）

### 13.1 执行生命周期

1. `update_llm_env()` — 注入 API key
2. 替换 `print` / `input` / `interact` 为 stream 版本
3. `BASE_DIR = py/examples/`；清空 `_loaded_files`
4. `run(code)` → SSE 事件流
5. 结束: `__DONE__` / `__STOPPED__` / `__ERROR__:` / `__RESULT__:`

### 13.2 SSE 事件（Lisp 侧不可见，宿主协议）

| 前缀 | 含义 |
|------|------|
| `__TEXT__:` | 普通输出 |
| `__MD__:` | Markdown 输出 |
| `__INPUT__:` | 请求用户输入 |
| `__INTERACT__:` | 结构化选择 JSON |
| `__PROGRESS__:` | 搜索进度 JSON |
| `__TORRENTS__:` | 种子卡片 JSON |
| `__RECS__:` | 推荐 JSON |
| `__ERROR__:` | 错误 |
| `__RESULT__:` | 最终返回值 |
| `__DONE__` | 正常结束 |
| `__STOPPED__` | 用户停止 |

### 13.3 配置

- `py/.user_config.json` → `api_keys.{deepseek,siliconflow,kling,...}`
- C/FFI 通过 Python 回调 `get_api_keys()` 获取，不在 C 中读文件

### 13.4 C 接入模式（M3 择一，规格预留）

**模式 A — 子进程**

```
zhiyu run --server --base-dir examples/
stdin:  Lisp 表达式 / 控制命令
stdout: SSE 兼容行
```

**模式 B — 动态库**

```c
ZhiyuVM *zhiyu_vm_new(ZhiyuHostCallbacks *cb);
zhiyu_eval(vm, "(load \"主入口.lisp\")");
```

`ZhiyuHostCallbacks` 必须包含: `print`, `input`, `interact`, `ffi_call(name, args)`.

---

## 14. 热更新（Runtime Redefinition）

### 14.1 要求

| ID | 要求 |
|----|------|
| HR-1 | 全局函数通过 **symbol 函数槽** 间接调用 |
| HR-2 | `(define (f ...) ...)` 替换 f 的函数槽，**不终止 VM** |
| HR-3 | `(load "path" :reload #t)` 重新执行文件并更新绑定 |
| HR-4 | 执行中的 f 旧栈帧继续旧闭包；新调用用新闭包 |
| HR-5 | 宿主可通过控制通道发送 reload（Web 保存文件后） |

### 14.2 不要求（M4+）

- 热更新 `defmacro` 的已展开 AST
- 内联函数的重编译

---

## 15. 分阶段验收（M1–M4）

| 阶段 | 验收标准 |
|------|----------|
| **M1** | Tier 0 + 特殊形式 + `examples/演示Demo/你好世界.lisp` |
| **M2** | + 宏 + load + 中文 + Tier 1 + `文章生成_函数式.lisp` |
| **M3** | + Tier 2 FFI + workflow_server 切换 + 种子搜索 + AI 视频主流程 |
| **M4** | + 热更新 HR-1–5 + 性能基准 + 全回归绿 |

---

## 16. 回归测试集

见 `tests/regression/README.md`。M0 冻结 **10 个最小集** + **全量 33 个示例索引**。

### 16.1 M1 最小集（10）

1. `演示Demo/你好世界.lisp`
2. `演示Demo/大模型对话.lisp`（mock 模式）
3. `测试语法.lisp`
4. `工具库/通用工具.lisp`（仅加载不报错）
5. 内联: 算术 + 列表 + `if` + `lambda` + `define`
6. 内联: 中文 `定义` / `如果` / `道`
7. 内联: `(cond ...)` + `否则` 分支
8. 内联: `(let ...)` 作用域
9. 内联: `(set! ...)` 更新
10. 内联: 字符串 + `format`

### 16.2 M3 集成集（关键产品路径）

1. `种子搜索.lisp` + `工具库/种子工具.lisp`
2. `AI视频创作/主入口.lisp`（及子模块 load 链）
3. `医疗备案填表.lisp`
4. `演示Demo/飞书反馈分类.lisp`

---

## 17. 参考文件索引

| 文件 | 内容 |
|------|------|
| `py/workflow_lisp.py` | 词法/语法/求值/宏/别名 |
| `py/workflow_server.py` | 宿主注入/GLOBAL_ENV/SSE |
| `py/workflow/ai_services.py` | AI 原语签名 |
| `py/workflow/llm.py` | call-llm |
| `py/workflow/torrent.py` | 种子搜索 |
| `py/workflow/user_errors.py` | 中文错误 |
| `docs/zhiyu-builtin-manifest.json` | 机器可读 builtin 表 |

---

## 18. 变更流程

M0 之后对语义的修改:

1. 先改本文档 + manifest
2. 同步 Python 参考实现（若仍维护）
3. 添加/更新 `tests/regression/`
4. 再改 `zhiyu-core`

---

*文档生成基准: lisp-workflow 仓库 workflow_lisp.py @ M0 冻结*
