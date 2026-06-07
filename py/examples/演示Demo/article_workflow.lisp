;; ============================================================
;; 文章生成工作流
;;
;; 流程：
;;
;;   输入(标题, 章节)
;;       │
;;       ▼
;;   ┌─────────────┐
;;   │ 生成大纲     │  LLM 根据标题+章节生成 JSON 结构
;;   └─────┬───────┘
;;         │
;;         ▼
;;   ┌─────────────┐
;;   │ 解析大纲     │  extract-json 提取章节列表
;;   └─────┬───────┘
;;         │
;;         ▼
;;   ┌─────────────┐
;;   │ 迭代扩写     │  map: 对每个章节调用 LLM 生成正文
;;   └─────┬───────┘
;;         │
;;         ▼
;;   ┌─────────────┐
;;   │ 合并输出     │  str-join 拼接完整文章
;;   └─────────────┘
;;
;; 依赖：call-llm, extract-json, remove-think
;; ============================================================


;; ------------------------------------------------------------
;; 1. 输入定义
;; ------------------------------------------------------------

(define title "庄子的人生感悟")
(define chapters "1.得失的故事 2.困境的故事 3.选择的故事")


;; ------------------------------------------------------------
;; 2. Prompt 模板
;;    所有提示词集中管理，与流程逻辑分离
;; ------------------------------------------------------------

;; 大纲生成：要求 LLM 输出标准 JSON
(define outline-prompt-template
  "## 技能：你根据用户输入的文章标题 %s 和各章节名称 %s，生成各个章节及子章节

## 目标：
- 确保生成的每个子章节和父章节紧密相关
- 纵观整体章节，必须保证各章节过渡连贯流畅
- 最终输出json字符串

## 限制：
- 输出内容必须是标准json字符串
- 请严格按照输出示例中的数据格式输出
- 不要输出任何与json无关的内容

## 输出示例：
[{\"chapter\": \"引言\", \"subchapter\": [\"1. 概述\", \"2. 重要性\"]}, {\"chapter\": \"正文\", \"subchapter\": [\"1. 核心观点\", \"2. 案例分析\"]}]")

;; 章节扩写：基于大纲上下文写出有深度的正文
(define expand-prompt-template
  "你是一名文章撰写专家，擅长写有吸引力的长篇文章。
你正在写一篇标题为 %s 的文章。

请根据以下章节信息撰写本章节内容：
%s

完整大纲参考：
%s

要求：
- 内容充实，有深度
- 语言流畅，有感染力
- 适当引用典故或案例")


;; ------------------------------------------------------------
;; 3. 节点函数
;;    每个函数对应流程图中的一个处理步骤
;; ------------------------------------------------------------

;; 调用 LLM 生成结构化大纲，返回 JSON 列表
(define (generate-outline title chapters)
  (-> (format outline-prompt-template title chapters)
      (call-llm)
      (remove-think)
      (extract-json)))

;; 对单个章节调用 LLM 扩写，返回完整正文
(define (expand-chapter title full-outline chapter-info)
  (-> (format expand-prompt-template
              title
              (to-json chapter-info)
              (to-json full-outline))
      (call-llm)
      (remove-think)))

;; 将多个章节正文用分割线拼接为完整文章
(define (merge-articles articles)
  (str-join "\n\n--------华丽分割线--------\n\n" articles))


;; ------------------------------------------------------------
;; 4. 主工作流
;;    三步串联：生成大纲 → 迭代扩写 → 合并输出
;; ------------------------------------------------------------

(define (workflow-main title chapters)
  ;; Step 1: 生成大纲（LLM → JSON 解析）
  (define outline (generate-outline title chapters))

  ;; Step 2: 逐章扩写（map 迭代，每章独立调用 LLM）
  (define articles
    (map (lambda (chapter-info)
           (expand-chapter title outline chapter-info))
         outline))

  ;; Step 3: 合并为最终文章
  (merge-articles articles))


;; ------------------------------------------------------------
;; 5. 执行
;; ------------------------------------------------------------

(print ">>> 文章生成工作流")
(print "  标题：" title)
(print "  章节：" chapters)
(print "")

;; 取消注释以实际执行完整工作流：
;; (define result (workflow-main title chapters))
;; (print result)
;; (write-file "examples/output.txt" result)
