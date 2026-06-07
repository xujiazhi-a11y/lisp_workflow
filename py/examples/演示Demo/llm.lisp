;; 大模型对话
(print "=== 大模型对话 ===")

(print ">>> 调用大模型...")
(define response (call-llm "用一句话介绍庄子"))
(print response)

(print ">>> 再次调用...")
(define detail (call-llm "请用三个要点介绍庄子的核心思想"))
(print detail)

(print "=== 完成 ===")
"Done!"