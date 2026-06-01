# Lisp Workflow

用 Lisp 重新理解 AI Workflow 的一次尝试。

## 缘起

大模型落地时往往离不开多步骤的工作流编排，而当下的主流做法是拖拉拽的可视化画布。画布上的连线固然直观，但当节点数量攀升，维护成本也随之急剧上升。

这个项目尝试换一个思路：用代码（而不是连线）来表达工作流。具体来说，是借助 Lisp 及其函数式编程的思想，将二维的连线图折叠成一维的极简代码。

## 核心理念

**过程即变量**。在 Lisp 中，任何复杂的过程都可以被抽象成一个简单的函数名，直接塞进过程体中。Workflow 的节点本质上就是"过程"，而 Lisp 把"过程"当成数据自由传递的特性，使其天然具备承载工作流图谱的潜力。

**高阶函数替代循环节点**。Map、Reduce、Filter 等函数可以优雅地替代传统画布上的迭代器节点。

## 项目状态

这是一个简陋的起步，实现还非常基础。代码谈不上优雅，但希望能抛砖引玉，提供一种不同的视角来思考 Workflow 的终态。

## 快速开始

```bash
cd py
python3 workflow_server.py
```

然后打开 http://localhost:8080

## 示例

### 文章生成工作流

```lisp
;; 定义输入
(define title "庄子的人生感悟")
(define chapters "1.得失的故事 2.困境的故事 3.选择的故事")

;; 调用 LLM 生成大纲
(define outline-raw (call-llm outline-prompt))
(define outline-parsed (extract-json outline-raw))

;; 迭代扩写
(define articles (map expand-chapter outline))

;; 合并输出
(define full-article (str-join "\n\n" articles))
(print full-article)
```

### 工作流组合：一屏 DAG 压缩成一行

传统可视化画布上需要拖拽多个节点并连线的复杂工作流，在 Lisp 中可以用 `reduce` 优雅地压缩成一句话：

```lisp
;; 定义各个处理节点
(define (input-data ctx) ...)
(define (generate-outline ctx) ...)
(define (parse-outline ctx) ...)
(define (expand-sections ctx) ...)
(define (build-article ctx) ...)

;; 整个 workflow 主函数只有一行！
(define (run-workflow ctx)
  (reduce (lambda [c f] (f c)) ctx
    [input-data generate-outline parse-outline expand-sections build-article]))
```

这种写法的精髓在于：
- **节点即函数**：每个处理节点就是一个普通函数
- **列表即工作流**：用列表定义执行顺序，直观且易于修改
- **上下文贯穿**：`ctx` 承载所有中间状态，在节点间流转

这就是函数式编程的优雅：列表即工作流定义！

## 内置函数

- 基础运算：`+`, `-`, `*`, `/`, `str`, `list`, `dict` 等
- 控制流：`if`, `begin`, `lambda`, `define`, `let`
- 高阶函数：`map`, `filter`, `reduce`
- LLM 调用：`call-llm`, `llm`
- 文本处理：`str-concat`, `str-replace`, `read-file`, `extract-json`, `to-json`
- 管道操作：`->`, `pipe`

## 欢迎交流

如果你也对可视化的臃肿感到疲劳，如果你相信代码与大模型的结合应该有更优雅的解法，欢迎来聊聊。

GitHub: https://github.com/xujiazhi-a11y/lisp_workflow