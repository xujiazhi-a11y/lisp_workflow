# 智语 Lisp 回归测试索引（M0）

> 配套规格: [zhiyu-spec.md](../docs/zhiyu-spec.md) §16  
> 运行方式（M1 起）: `zhiyu test --manifest tests/regression/manifest.json`

## 分阶段用例

### M1 — 核心语言（10 项）

| ID | 类型 | 路径 / 说明 |
|----|------|-------------|
| m1-01 | file | `py/examples/演示Demo/你好世界.lisp` |
| m1-02 | file | `py/examples/演示Demo/大模型对话.lisp`（无 API key 时 mock） |
| m1-03 | file | `py/examples/测试语法.lisp` |
| m1-04 | load-only | `py/examples/工具库/通用工具.lisp`（load 无异常） |
| m1-05 | inline | 算术: `(+ 1 (* 2 3))` → `7` |
| m1-06 | inline | 中文: `(定义 x 1) (如果 (> x 0) "ok" "no")` → `"ok"` |
| m1-07 | inline | cond + 否则 |
| m1-08 | inline | let 作用域隔离 |
| m1-09 | inline | set! 更新外层绑定 |
| m1-10 | inline | format 与字符串 |

### M2 — 宏 / load / 工作流语法（+5 项）

| ID | 类型 | 路径 |
|----|------|------|
| m2-01 | file | `py/examples/演示Demo/文章生成_函数式.lisp` |
| m2-02 | file | `py/examples/演示Demo/工作流组合_pipeline.lisp` |
| m2-03 | file | `py/examples/工具库/种子工具.lisp`（load-only） |
| m2-04 | inline | defmacro 展开 |
| m2-05 | inline | `(load "相对路径")` 多文件 |

### M3 — 宿主集成（+4 项）

| ID | 类型 | 路径 |
|----|------|------|
| m3-01 | file | `py/examples/种子搜索.lisp` |
| m3-02 | tree | `py/examples/AI视频创作/`（从 `主入口.lisp` load） |
| m3-03 | file | `py/examples/医疗备案填表.lisp` |
| m3-04 | file | `py/examples/演示Demo/飞书反馈分类.lisp` |

### M4 — 热更新（+3 项，待实现）

| ID | 说明 |
|----|------|
| m4-01 | 运行中长循环，`(load path :reload #t)` 后新 `define` 生效 |
| m4-02 | Web 保存文件 → 宿主触发 reload |
| m4-03 | 旧栈帧继续旧函数，新调用新函数 |

## 全量示例索引（33 文件）

```
py/examples/
├── 种子搜索.lisp
├── 医疗备案填表.lisp
├── AI视频创作.lisp
├── 测试语法.lisp
├── AI视频创作/
│   ├── ai视频创作.lisp
│   ├── 基础设施.lisp
│   ├── 编排引擎.lisp
│   ├── 交互原语.lisp
│   ├── 内容生产.lisp
│   ├── 交互生成视频.lisp
│   ├── 主入口.lisp
│   ├── 拼接成片.lisp
│   ├── 主循环.lisp
│   ├── 单段处理.lisp
│   ├── 交互优化描述.lisp
│   ├── 交互选帧.lisp
│   ├── 辅助函数.lisp
│   └── 输入读取.lisp
├── 工具库/
│   ├── 种子工具.lisp
│   ├── 推荐工具.lisp
│   └── 通用工具.lisp
└── 演示Demo/
    ├── 飞书反馈分类.lisp
    ├── 工作流组合_pipeline.lisp
    ├── 文章生成_函数式.lisp
    ├── 文章生成_完整版.lisp
    ├── 大模型对话.lisp
    ├── 你好世界.lisp
    ├── workflow.lisp
    ├── article.lisp
    ├── feishu_feedback.lisp
    ├── article_workflow.lisp
    ├── llm.lisp
    └── hello.lisp
```

M4 目标: 上表 **全部可运行**（允许 mock 外部 API）。

## 对照运行（过渡期）

```bash
# Python 参考实现
cd py && python3 workflow_lisp.py examples/演示Demo/你好世界.lisp

# C 新引擎（M1 起）
zhiyu run examples/演示Demo/你好世界.lisp

# 双跑对比
python3 scripts/compare_run.py --legacy --zhiyu m1-01
```

`scripts/compare_run.py` 在 M1 脚手架阶段添加。
