;; ============================================
;; 文章生成工作流（完整版）
;; 节点化工作流: 输入 -> LLM大纲 -> 代码清洗 -> 迭代扩写 -> 合并
;; ============================================

;; ---------- 节点1: 输入节点 ----------
(define title "庄子的人生感悟")
(define chapters "1.得失的故事 2.困境的故事 3.选择的故事")

(print "╔════════════════════════════════╗")
(print "║    文章生成工作流 - 完整版     ║")
(print "╚════════════════════════════════╝")
(print "")
(print (str-concat "标题: " title))
(print (str-concat "章节: " chapters))

;; ---------- 节点2: 定义固定大纲 ----------
(print "")
(print ">>> 节点2: 定义文章大纲...")

;; 固定的三章结构（仅章节标题）
(define outline
  (list
    "得失的故事"
    "困境的故事"
    "选择的故事"))

(print (str-concat "标题: " title))
(print "")
(print "大纲结构:")
(print "  1. 得失的故事")
(print "  2. 困境的故事")
(print "  3. 选择的故事")
(print "")

(print (str-concat "大纲完成! 共 " (str (length outline)) " 个章节"))
(print "")

;; ---------- 节点3: 迭代体 - 逐章调用LLM扩写 ----------
(print ">>> 节点3: 逐章扩写文章内容...")
(print "")

(define (expand-chapter chapter-name)
  ;; 构建扩写 prompt
  (define expand-prompt
    (str-concat
      "你是一名文章撰写专家，正在撰写《" title "》这篇文章。\n\n"
      "当前章节：**" chapter-name "**\n\n"
      "请撰写这个章节的完整文章内容。要求：\n"
      "1. 只输出正文内容，不要使用任何markdown标题格式（#、##等）\n"
      "2. 内容要有深度，引用庄子的典故来论证观点\n"
      "3. 语言优美流畅，有思想性\n\n"
      "请开始撰写："))

  (print (str-concat "    正在扩写章节: " chapter-name "..."))
  ;; 返回带章节标题的内容
  (define content (remove-think (call-llm expand-prompt)))
  (str-concat "## " chapter-name "\n\n" content))

(define articles (map expand-chapter outline))

(print "")
(print (str-concat "所有章节扩写完成! 共生成 " (str (length articles)) " 个章节内容"))

;; ---------- 节点5: 合并节点 - 拼接完整文章 ----------
(print "")
(print ">>> 节点5: 合并所有章节...")

;; 构建完整文章：添加主标题
(define header (str-concat "# " title "\n\n"))
(define full-article (str-concat header (str-join "\n\n" articles)))

(print "")
(print "══════════════ 完整文章 ══════════════")
(print full-article)
(print "═══════════════════════════════════════")

full-article