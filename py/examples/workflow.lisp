;; ============================================
;; 文章生成工作流 - 代码即数据
;; 展示：用简洁的主函数串联复杂的工作流
;; ============================================

;; ---------- 第一步：定义各个处理节点 ----------

;; 节点1: 输入标题和章节
(define (input-data ctx)
  (put ctx "title" "Lisp语言入门指南"))

;; 节点2: 调用 LLM 生成大纲
(define (generate-outline ctx)
  (let [[prompt (str-concat "请为《" (get ctx "title") "》生成3个大纲章节")]]
    (print ">>> 调用大模型生成大纲...")
    (put ctx "outline" (call-llm prompt))))

;; 节点3: 解析大纲为列表
(define (parse-outline ctx)
  (let [[raw (get ctx "outline")]]
    (let [[parsed (extract-json raw)]]
      (print ">>> 解析大纲...")
      (put ctx "sections"
        (if (null? parsed)
            (list "第一章：Lisp简介" "第二章：函数定义" "第三章：宏")
            parsed)))))

;; 节点4: 调用 LLM 扩写章节
(define (expand-sections ctx)
  (let [[sections (get ctx "sections")]]
    (print ">>> 调用大模型扩写章节...")
    (put ctx "articles"
      (map (lambda [s]
             (let [[prompt (str-concat
               "请为文章章节《" s "》撰写正文内容，约300字。要求：只输出正文，不要使用任何标题格式。")]]
               (let [[content (remove-think (call-llm prompt))]]
                 (str-concat "## " s "\n\n" content))))
           sections))))

;; 节点5: 合并最终文章
(define (build-article ctx)
  (let [[title (get ctx "title")]]
    (let [[articles (get ctx "articles")]]
      (print ">>> 生成最终文章...")
      (put ctx "final"
        (str-concat "# " title "\n\n"
          (str-join "\n\n" articles))))))

;; ---------- 第二步：定义工作流主函数 ----------
(define (run-workflow ctx)
  (reduce (lambda [c f] (f c)) ctx
    [input-data generate-outline parse-outline expand-sections build-article]))

;; ---------- 第三步：执行工作流 ----------
(print "=== 执行文章生成工作流 ===")
(let [[result (run-workflow (dict))]]
  (print "")
  (print "=== 生成的文章 ===")
  (print (get result "final")))

(print "")
(print "=== 简洁优雅的主函数定义 ===")
(print "整个工作流只有一行:")
(print "")
(print "  (define (run-workflow ctx)")
(print "    (reduce (lambda [c f] (f c)) ctx")
(print "      [input-data generate-outline parse-outline")
(print "       expand-sections build-article]))")
(print "")
(print "这就是函数式编程的优雅：列表即工作流定义!")