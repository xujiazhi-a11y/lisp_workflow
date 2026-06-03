;; ============================================================
;; 飞书反馈分类通知工作流
;;
;; 流程图：
;;
;;   用户反馈
;;       |
;;       v
;;   [情感分类] --- positive ---> [发送正向通知]
;;       |
;;     negative
;;       |
;;       v
;;   [问题细分] ---> 物流慢 ---> [发送物流通知]
;;       |--------> 质量差 ---> [发送质量通知]
;;       |--------> 其它   ---> [发送其它通知]
;;
;; 依赖：call-llm, send-to-feishu
;; ============================================================


;; ------------------------------------------------------------
;; 1. 数据定义：Prompt 模板与消息模板
;; ------------------------------------------------------------

;; LLM 分类用的 Prompt
(define sentiment-prompt
  "请判断以下用户反馈是 positive 还是 negative，只回答一个词：
%s")

(define category-prompt
  "请判断以下负面反馈属于哪个类别，只回答一个词（物流慢/质量差/其它）：
%s")

;; 飞书消息模板
(define positive-msg-template
  "用户提交正向反馈

内容：
%s")

(define negative-msg-template
  "用户提交负向反馈

问题类型：%s

反馈内容：
%s")


;; ------------------------------------------------------------
;; 2. 过程定义：每个函数只做一件事
;; ------------------------------------------------------------

;; 判断情感极性：返回 "positive" 或 "negative"
(define (classify-sentiment feedback)
  (str-trim (call-llm (format sentiment-prompt feedback))))

;; 判断负面反馈类型：返回 "物流慢" / "质量差" / "其它"
(define (classify-issue feedback)
  (let [[raw (str-trim (call-llm (format category-prompt feedback)))]]
    (if (str-contains? "物流" raw) "物流慢"
      (if (str-contains? "质量" raw) "质量差"
        "其它"))))

;; 构造飞书消息标题
(define (make-title category)
  (if (str-contains? "物流" category) "🚚 负向反馈 - 物流慢"
    (if (str-contains? "质量" category) "📦 负向反馈 - 质量差"
      "📝 负向反馈 - 其它")))

;; 发送正向通知
(define (notify-positive feedback)
  (send-to-feishu "✅ 正向反馈通知"
                  (format positive-msg-template feedback)))

;; 发送负向通知
(define (notify-negative feedback category)
  (send-to-feishu (make-title category)
                  (format negative-msg-template category feedback)))


;; ------------------------------------------------------------
;; 3. 主工作流：串联各步骤
;; ------------------------------------------------------------

(define (process-feedback feedback)
  (print ">>> 收到反馈: " feedback)

  ;; Step 1: 情感分类
  (print ">>> 情感分类...")
  (let [[sentiment (classify-sentiment feedback)]]
    (print "  结果: " sentiment)

    ;; Step 2: 分流处理
    (if (str-starts? "positive" sentiment)
      (begin
        (print ">>> 发送正向通知...")
        (notify-positive feedback))
      (begin
        (print ">>> 细分问题类型...")
        (let [[category (classify-issue feedback)]]
          (print "  类型: " category)
          (print ">>> 发送负向通知...")
          (notify-negative feedback category))))))


;; ------------------------------------------------------------
;; 4. 测试执行
;; ------------------------------------------------------------

(print ">>> 测试1：质量差反馈")
(process-feedback "收到货后发现包装破了，东西也摔坏了")

(print ">>> 测试2：物流慢反馈")
(process-feedback "等了一周才收到货，物流太慢了")

(print ">>> 测试3：正向反馈")
(process-feedback "产品非常好，用起来很顺手，客服态度也很棒")
