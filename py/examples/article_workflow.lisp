;; ============================================================
;; 文章生成工作流示例
;; 
;; 这个示例展示了如何用 Lisp 语言定义 AI 工作流
;; 对应的工作流节点：
;;   1. 输入节点 -> 接收标题和章节
;;   2. 大模型节点 -> 生成大纲
;;   3. 代码节点 -> 解析 JSON
;;   4. 迭代体 -> 扩写每个章节
;;   5. 合并节点 -> 输出完整文章
;; ============================================================

;; ------------------------------------------------------------
;; 1. 输入定义
;; ------------------------------------------------------------
(define title "庄子的人生感悟")
(define chapters "1.得失的故事 2.困境的故事 3.选择的故事")

;; ------------------------------------------------------------
;; 2. 定义 Prompt 模板
;; ------------------------------------------------------------

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
;; 3. 定义工作流节点函数
;; ------------------------------------------------------------

;; 节点1：生成大纲
(define (generate-outline title chapters)
  (-> (format outline-prompt-template title chapters)
      (call-llm)
      (remove-think)
      (extract-json)))

;; 节点2：扩写单个章节
(define (expand-chapter title full-outline chapter-info)
  (-> (format expand-prompt-template 
              title 
              (to-json chapter-info) 
              (to-json full-outline))
      (call-llm)
      (remove-think)))

;; 节点3：处理大纲数据，提取章节列表
(define (extract-chapters outline-data)
  (map (lambda (item) (get item "chapter")) outline-data))

;; 节点4：合并文章
(define (merge-articles articles)
  (str-join "\n\n--------华丽分割线--------\n\n" articles))

;; ------------------------------------------------------------
;; 4. 主工作流
;; ------------------------------------------------------------

(define (workflow-main title chapters)
  ;; Step 1: 生成大纲
  (define outline (generate-outline title chapters))
  
  ;; Step 2: 迭代扩写每个章节
  (define articles 
    (map (lambda (chapter-info)
           (expand-chapter title outline chapter-info))
         outline))
  
  ;; Step 3: 合并输出
  (merge-articles articles))

;; ------------------------------------------------------------
;; 5. 执行工作流
;; ------------------------------------------------------------

;; 运行工作流（取消注释以执行）
;; (define result (workflow-main title chapters))
;; (print result)
;; (write-file "examples/output.txt" result)

;; 测试：打印大纲
(print "测试工作流...")
(print "标题：" title)
(print "章节：" chapters)
