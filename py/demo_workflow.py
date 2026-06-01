"""
Lisp Workflow Demo
展示 Lisp 的优雅：万物皆函数，代码即数据

这个 Demo 展示了如何用简洁的 Lisp 代码定义复杂的工作流。
"""

import sys
sys.path.insert(0, '.')
from workflow_lisp import run, GLOBAL_ENV

GLOBAL_ENV['print'] = lambda *args: print(' '.join(str(a) for a in args))

# ============================================================
# 文章生成工作流 Demo
# 展示：如何把庞大的 workflow 压缩成简洁的函数过程
# ============================================================

demo_code = '''
;; ============================================================
;; Lisp Workflow - 文章生成工作流
;; 展示 Lisp 的核心特性：万物皆函数，代码即数据
;; ============================================================

;; 【第一步：定义工作流节点（每个节点是一个函数）】
;; 每个节点接收 ctx，返回更新后的 ctx

;; 节点1：设置标题
(define set-title (lambda [ctx]
  (let [[title (get ctx "title")]]
    (put ctx "html-title" (str "<h1>" title "</h1>")))))

;; 节点2：设置大纲
(define set-outline (lambda [ctx]
  (let [[outline (get ctx "outline")]]
    (put ctx "html-outline" (str "<outline>" outline "</outline>")))))

;; 节点3：设置章节
(define set-sections (lambda [ctx]
  (let [[chapters (get ctx "chapters")]]
    (put ctx "html-sections"
         (reduce str "" (map (lambda [s] (str "<section>" s "</section>")) chapters))))))

;; 节点4：组装全文
(define build-article (lambda [ctx]
  (put ctx "article"
       (str "<article>"
            (get ctx "html-title")
            (get ctx "html-outline")
            (get ctx "html-sections")
            "</article>"))))

;; 【第二步：定义工作流组合器（万物皆函数）】
(define workflow (lambda [nodes]
  (lambda [ctx]
    (reduce (lambda [c f] (f c)) ctx nodes))))

;; 【第三步：拼装工作流（代码即数据）】
;; 这是简洁优雅的函数过程体，一行代码串联所有节点
(define article-workflow
  (workflow [set-title set-outline set-sections build-article]))

;; 【第四步：执行工作流】
(print "=== 文章生成工作流 Demo ===")
(let [[ctx (dict
    "title" "Lisp语言入门指南"
    "outline" "1. 简介 2. 基础语法 3. 函数式编程"
    "chapters" ["第一章：Lisp简介" "第二章：函数定义" "第三章：宏"])]]
  (print "输入:")
  (print "  标题: " (get ctx "title"))
  (print "  大纲: " (get ctx "outline"))
  (print "  章节: " (get ctx "chapters"))
  (print "")
  (let [[result (article-workflow ctx)]]
    (print "输出:")
    (print (get result "article"))))

;; 【第五步：展示简洁优雅的函数过程体】
(print "")
(print "=== 简洁优雅的函数过程体 ===")
(print "整个工作流可以用一行代码表示:")
(print "")
(print "  (define article-workflow")
(print "    (workflow [set-title set-outline set-sections build-article]))")
(print "")
(print "这体现了 Lisp 的核心特性:")
(print "  - 万物皆函数：reduce 将节点折叠成函数")
(print "  - 代码即数据：[set-title set-outline ...] 是列表，也是执行顺序")

;; 【第六步：管道写法】
(print "")
(print "=== 管道写法 ===")
(let [[r (pipe "测试数据"
      (lambda [x] (str x "-步骤1"))
      (lambda [x] (str x "-步骤2"))
      (lambda [x] (str x "-步骤3")))]]
  (print "管道结果: " r))

(print "")
(print "=== Demo 完成 ===")
'''

print("=" * 70)
print("Lisp Workflow - 文章生成工作流 Demo")
print("展示：如何把庞大的 workflow 压缩成简洁优雅的函数过程")
print("=" * 70)
print()

try:
    run(demo_code)
    print()
    print("=" * 70)
    print("✓ Demo 执行成功!")
    print("=" * 70)
except Exception as e:
    import traceback
    print("\n✗ Demo 执行失败:")
    traceback.print_exc()