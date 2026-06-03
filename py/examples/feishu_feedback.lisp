;; ============================================================
;; 飞书反馈处理工作流
;; 展示：Lisp 风格的 AI 工作流编排
;; ============================================================

;; 主工作流
(define (process f)
  (print "========================================")
  (print "飞书反馈处理工作流")
  (print "========================================")
  (print "")
  (print "收到反馈: " f)
  (print "")

  ;; Step 1: 分类情感
  (print "Step 1: 分类情感...")
  (let [[s (str-trim (call-llm (format "判断positive还是negative：%s" f)))]]
    (print "  情感: " s)

    ;; 判断正向 (s 是 LLM 返回的情感文本，检测它是否以 "positive" 开头)
    (if (str-starts? "positive" s)
      ;; 正向反馈处理
      (begin
        (print "")
        (print "Step 2: 发送正向反馈通知...")
        (let [[msg (str "用户提交正向反馈\n\n内容：\n" f)]]
          (send-to-feishu "正向反馈通知" msg))
        (print "✓ 完成"))

      ;; 负向反馈处理
      (begin
        (print "")
        (print "Step 2: 细分问题类型...")
        (let [[raw (str-trim (call-llm (format "判断物流慢质量差其它：%s" f)))]]
          (print "  LLM返回: " raw)
          (print "")
          (print "Step 3: 发送负向反馈通知...")
          (if (str-contains? "物流" raw)
            (begin
              (print "  类型: 物流慢")
              (send-to-feishu "🚚 负向反馈 - 物流慢"
                              (str "用户提交负向反馈\n\n问题类型：物流慢\n\n反馈内容：\n" f)))
            (if (str-contains? "质量" raw)
              (begin
                (print "  类型: 质量差")
                (send-to-feishu "📦 负向反馈 - 质量差"
                                (str "用户提交负向反馈\n\n问题类型：质量差\n\n反馈内容：\n" f)))
              (begin
                (print "  类型: 其它")
                (send-to-feishu "📝 负向反馈 - 其它"
                                (str "用户提交负向反馈\n\n问题类型：其它\n\n反馈内容：\n" f)))))
          (print "✓ 完成"))))))

;; ============================================================
;; 测试执行
;; ============================================================
(print "")
(print "=== 测试开始 ===")
(print "")

;; 测试1：质量差反馈
(print ">>> 测试1：质量差反馈")
(process "收到货后发现包装破了，东西也摔坏了")

;; 测试2：物流慢反馈
(print "")
(print ">>> 测试2：物流慢反馈")
(process "等了一周才收到货，物流太慢了")

;; 测试3：正向反馈
(print "")
(print ">>> 测试3：正向反馈")
(process "产品非常好，用起来很顺手，客服态度也很棒")

(print "")
(print "========================================")
(print "Demo 完成")
(print "========================================")