# zhiyu-core

智语 Lisp C 运行时（M1 解释器 + M2 宏/管道/JSON）。

## 构建

```bash
cd zhiyu-core
make
```

## 运行

```bash
# 执行文件（相对路径基于 --base-dir）
./zhiyu run 演示Demo/你好世界.lisp --base-dir ../py/examples

# 求值表达式
./zhiyu eval "(+ 1 2)"

# REPL
./zhiyu repl
```

## 测试

```bash
make test      # M1 回归
make test-m2   # M2 验收：文章生成_函数式 / 工作流组合_pipeline
```

## M2 能力

- 特殊形式：`load`/`引入`、`defmacro`/`定义宏`、`macroexpand`、`pipe`、`->`、`map`/`reduce`/`filter`/`each`
- 内置：`format`、`read-file`、`dict`/`get`/`put`、`parse-json`/`to-json`/`extract-json`、`remove-think`、`regex-*`、`strip`、`call-llm`（mock）
- 类型：`ZY_DICT`、`pair?`

## 规格

见 [docs/zhiyu-spec.md](../docs/zhiyu-spec.md)
