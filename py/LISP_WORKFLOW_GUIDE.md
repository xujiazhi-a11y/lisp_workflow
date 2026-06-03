# Lisp Workflow 开发指南

本文档总结了在 `lisp-workflow` 项目中编写工作流脚本的经验教训，帮助你编写正确无误的 Lisp 工作流。

## ⚠️ 已知的 Lisp 解释器 Bug

### Bug 1: let 绑定中引用前面绑定的变量会导致错误

**问题描述：**
在单个 `let` 的多个绑定中，后面的绑定不能引用前面绑定的变量。例如：

```lisp
;; ❌ 错误写法 - 会报错 "未定义的符号: x"
(let [[x (call-llm "a")]
      [c (str-contains? "test" x)]]
  (print c))
```

**解决方案：**
使用嵌套的 `let` 来替代：

```lisp
;; ✅ 正确写法
(let [[x (call-llm "a")]]
  (let [[c (str-contains? x "test")]]  ;; 注意参数顺序：先字符串，后子串
    (print c)))
```

**⚠️ 重要：str-starts? 和 str-contains? 的参数顺序**

这两个函数的参数顺序是：**先匹配内容，后字符串**

```lisp
;; str-starts?: (str-starts? prefix text) - 检查 text 是否以 prefix 开头
(str-starts? "positive" "positive反馈")  ;; => True

;; str-contains?: (str-contains? sub text) - 检查 text 是否包含 sub
(str-contains? "物流" "物流慢")  ;; => True
```

### Bug 2: if 条件的 equals 比较可能有问题

**问题描述：**
在 `let` 绑定中使用 `=` 进行字符串比较可能出错：

```lisp
;; ❌ 可能报错
(let [[x "test"]]
  (let [[e (if (= x "test") "a" "b")]]
    (print e)))  ;; TypeError: 'str' object is not callable
```

**解决方案：**
使用 `str-starts?` 或 `str-contains?` 来进行字符串判断：

```lisp
;; ✅ 正确写法 (参数顺序：先匹配内容，后字符串)
(let [[x "test"]]
  (let [[e (if (str-starts? "test" x) "a" "b")]]  ;; x 是否以 "test" 开头
    (print e)))
```

## 📝 Lisp 工作流编写规范

### 1. 工作流结构

```
;; ============================================================
;; 工作流标题
;; 描述工作流的功能
;; ============================================================

;; 主工作流
(define (workflow-name input)
  ;; Step 1: 处理步骤
  (print "Step 1: ...")
  (let [[result (some-function input)]]
    (print "  结果: " result)

    ;; Step 2: 条件分支 (参数顺序：先匹配内容，后字符串)
    (if (str-starts? "expected" result)
      ;; 分支1
      (do-something)
      ;; 分支2
      (do-something-else))))

;; 执行测试
(workflow-name "测试输入")
```

### 2. 定义节点函数

```lisp
;; 节点函数接收一个参数
(define (node-function input)
  (let [[processed (some-operation input)]]
    processed))
```

### 3. 调用 LLM

```lisp
;; 调用 LLM 并处理结果
(let [[response (str-trim (call-llm prompt))]
      [clean (remove-think response)]]
  (print clean))
```

### 4. 条件分支

```lisp
;; 使用 str-starts? 或 str-contains? 进行判断 (参数顺序：先匹配内容，后字符串)
(if (str-starts? "positive" sentiment)
  (print "正向")
  (print "负向"))
```

### 5. 避免嵌套过深的 let

**不好的写法（可能触发 bug）：**
```lisp
(let [[x 1]
      [y 2]
      [z 3]
      [result (some-func x y z)]]
  ...)
```

**推荐写法：**
```lisp
(let [[x 1]]
  (let [[y 2]]
    (let [[z 3]]
      (let [[result (some-func x y z)]]
        ...))))
```

## 🔧 常用内置函数

| 函数 | 用法 | 说明 |
|------|------|------|
| `call-llm` | `(call-llm prompt)` | 调用 LLM |
| `str-trim` | `(str-trim text)` | 去除空白 |
| `str-starts?` | `(str-starts? prefix text)` | 检查 text 是否以 prefix 开头 |
| `str-contains?` | `(str-contains? sub text)` | 检查 text 是否包含 sub |
| `format` | `(format "Hello %s" name)` | 字符串格式化 |
| `get` | `(get dict "key")` | 获取字典值 |
| `put` | `(put dict "key" value)` | 设置字典值 |
| `dict` | `(dict "a" 1 "b" 2)` | 创建字典 |
| `send-to-feishu` | `(send-to-feishu title content)` | 发送飞书消息 |
| `print` | `(print "Hello" var)` | 打印输出 |

## 📦 飞书消息发送

已在 `workflow_lisp.py` 中注册了 `send-to-feishu` 函数：

```lisp
;; 发送简单文本消息
(send-to-feishu "标题" "内容")

;; 发送格式化内容
(let [[msg (str "类型：" type "\n\n内容：" content)]]
  (send-to-feishu title msg))
```

## ✅ 示例代码

### 完整的工作流示例

```lisp
;; ============================================================
;; 示例工作流
;; ============================================================

(define (process input)
  (print "收到输入: " input)

  ;; Step 1: 调用 LLM
  (print "Step 1: 分析...")
  (let [[result (str-trim (call-llm (format "分析：%s" input)))]]
    (print "  结果: " result)

    ;; Step 2: 条件判断 (参数顺序：先匹配内容，后字符串)
    (if (str-starts? "positive" result)
      (print "处理正向情况")
      (print "处理负向情况"))))

;; 执行
(process "测试输入")
```

### 带飞书通知的工作流

```lisp
;; ============================================================
;; 带飞书通知的工作流
;; ============================================================

(define (notify-workflow feedback)
  (print "处理反馈: " feedback)

  ;; 分析反馈
  (let [[sentiment (str-trim (call-llm (format "判断positive还是negative：%s" feedback)))]]

    ;; 判断类型并发送通知 (参数顺序：先匹配内容，后字符串)
    (if (str-starts? "positive" sentiment)
      (send-to-feishu "正向反馈" feedback)
      (send-to-feishu "负向反馈" feedback))))

;; 执行
(notify-workflow "用户反馈内容")
```

## 🐛 调试技巧

1. **逐步测试**：先写简单版本，确保能运行，再逐步添加复杂逻辑
2. **使用 print**：在关键步骤添加 print 语句查看变量值
3. **避免复杂嵌套**：如果代码复杂，考虑拆分成多个函数

```lisp
;; 调试时添加打印
(let [[x (call-llm "test")]]
  (print "x = " x)  ;; 查看变量值
  ...)
```

## 📋 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `未定义的符号: x` | 在 let 绑定中引用了前面的变量 | 使用嵌套 let |
| `TypeError: 'str' object is not callable` | 在 let 绑定中使用了 `=` 比较 | 使用 `str-starts?` |
| `多余的 )` | 括号不匹配 | 检查括号配对 |

## 🚀 最佳实践

1. **保持代码简洁**：每个函数只做一件事
2. **添加注释**：说明每个步骤的作用
3. **先测试后集成**：单独测试每个节点，再组合成完整流程
4. **使用描述性命名**：变量名和函数名要清晰表达意图