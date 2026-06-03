;; ============================================================
;; 文章生成工作流（pipeline 版）
;;
;; 流程：
;;
;;   空上下文(dict)
;;       │
;;       ▼
;;   ┌─────────────┐
;;   │ input-data   │  注入标题到上下文
;;   └─────┬───────┘
;;         │
;;         ▼
;;   ┌──────────────────┐
;;   │ generate-outline  │  LLM 生成大纲文本
;;   └─────┬────────────┘
;;         │
;;         ▼
;;   ┌─────────────────┐
;;   │ parse-outline    │  extract-json 解析为列表
;;   └─────┬───────────┘
;;         │
;;         ▼
;;   ┌──────────────────┐
;;   │ expand-sections   │  map: 逐章调用 LLM 扩写
;;   └─────┬────────────┘
;;         │
;;         ▼
;;   ┌─────────────────┐
;;   │ build-article    │  拼接标题 + 各章内容
;;   └─────────────────┘
;;
;; 特点：用 reduce 将节点列表串联为 pipeline，
;;       上下文(ctx)在节点间传递，实现「代码即工作流」
;;
;; 依赖：call-llm, extract-json, remove-think
;; ============================================================


;; ------------------------------------------------------------
;; 1. Prompt 模板
;; ------------------------------------------------------------

(define outline-prompt-template
  "请为《%s》生成3个大纲章节")

(define expand-prompt-template
  "请为文章章节《%s》撰写正文内容，约300字。要求：只输出正文，不要使用任何标题格式。")


;; ------------------------------------------------------------
;; 2. Pipeline 节点
;;    每个节点接收 ctx(dict)，处理后返回更新的 ctx
;; ------------------------------------------------------------

;; 注入文章标题
(define (input-data ctx)
  (put ctx "title" "Lisp语言入门指南"))

;; 调用 LLM 生成大纲文本
(define (generate-outline ctx)
  (let [[prompt (format outline-prompt-template (get ctx "title"))]]
    (print ">>> 调用大模型生成大纲...")
    (put ctx "outline" (call-llm prompt))))

;; 解析大纲 JSON，失败则使用默认章节
(define (parse-outline ctx)
  (let [[parsed (extract-json (get ctx "outline"))]]
    (print ">>> 解析大纲...")
    (put ctx "sections"
      (if (null? parsed)
          (list "第一章：Lisp简介" "第二章：函数定义" "第三章：宏")
          parsed))))

;; 逐章调用 LLM 扩写
(define (expand-sections ctx)
  (let [[sections (get ctx "sections")]]
    (print ">>> 调用大模型扩写章节...")
    (put ctx "articles"
      (map (lambda [s]
             (let [[content (remove-think
                    (call-llm (format expand-prompt-template s)))]]
               (str-concat "## " s "\n\n" content)))
           sections))))

;; 拼接标题 + 所有章节为完整文章
(define (build-article ctx)
  (let [[title (get ctx "title")]]
    (let [[articles (get ctx "articles")]]
      (print ">>> 生成最终文章...")
      (put ctx "final"
        (str-concat "# " title "\n\n"
          (str-join "\n\n" articles))))))


;; ------------------------------------------------------------
;; 3. 主工作流
;;    reduce 将节点列表串联：每个节点的输出是下一个的输入
;; ------------------------------------------------------------

(define (run-workflow ctx)
  (reduce (lambda [c f] (f c)) ctx
    [input-data generate-outline parse-outline expand-sections build-article]))


;; ------------------------------------------------------------
;; 4. 执行
;; ------------------------------------------------------------

(print ">>> 执行文章生成工作流（pipeline 模式）")
(let [[result (run-workflow (dict))]]
  (print "")
  (print ">>> 生成的文章：")
  (print (get result "final")))
