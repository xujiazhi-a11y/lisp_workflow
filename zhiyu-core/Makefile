CC = cc
CFLAGS = -std=c11 -Wall -Wextra -O2 -Iinclude
SRC = src/value.c src/symbol.c src/parser.c src/env.c src/cn.c \
      src/builtins.c src/eval.c src/vm.c src/macro.c src/json.c src/text.c \
      src/host.c src/server.c src/main.c
OBJ = $(SRC:.c=.o)
BIN = zhiyu

.PHONY: all clean test test-m2 test-m3 test-m4

all: $(BIN)

$(BIN): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ)

src/%.o: src/%.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJ) $(BIN)

test: $(BIN)
	@echo "=== m1-05 算术【】 ==="
	./$(BIN) eval '【+ 1 【* 2 3】】'
	@echo "=== m1-06 中文【】 ==="
	./$(BIN) eval '【定义 x 1】 【如果 【> x 0】 "ok" "no"】'
	@echo "=== 你好世界【】 ==="
	./$(BIN) run '演示Demo/你好世界.lisp' --base-dir ../py/examples

test-m2: $(BIN)
	@echo "=== m2 文章生成_函数式 ==="
	./$(BIN) run '演示Demo/文章生成_函数式.lisp' --base-dir ../py/examples
	@echo "=== m2 工作流组合_pipeline ==="
	./$(BIN) run '演示Demo/工作流组合_pipeline.lisp' --base-dir ../py/examples

test-m3: $(BIN)
	@echo "=== m3 飞书反馈分类（C + mock FFI）==="
	./$(BIN) run '演示Demo/飞书反馈分类.lisp' --base-dir ../py/examples
	@echo "=== m3 种子工具 load-only ==="
	./$(BIN) eval '(load "工具库/种子工具.lisp")' --base-dir ../py/examples
	@echo "=== m3 AI视频创作 子模块 load-only ==="
	./$(BIN) eval '【定义 用户输入数据 【字典 "参考图" "x.jpg" "故事" "小猫" "段数" 1 "角色" "猫"】】【引入 "examples/AI视频创作/输入读取.lisp"】【引入 "examples/AI视频创作/辅助函数.lisp"】【引入 "examples/AI视频创作/交互选帧.lisp"】【引入 "examples/AI视频创作/单段处理.lisp"】' --base-dir ../py
	@echo "=== m3 Python 宿主桥接 ==="
	cd ../py && python3 -m workflow.zhiyu_runner --test-m3 --zhiyu ../zhiyu-core/$(BIN)

test-m4: $(BIN)
	@echo "=== m4 HR-2 函数重定义 ==="
	./$(BIN) eval '(define (f) 1) (f)'
	./$(BIN) eval '(define (f) 1) (define (f) 2) (f)'
	@echo "=== m4 HR-4 闭包隔离 ==="
	./$(BIN) eval '(define (f) 1) (let ((saved f)) (begin (define (f) 2) (list (saved) (f))))'
	@echo "=== m4 HR-3 load :reload ==="
	@echo '(define hr-v 42)' > /tmp/zhiyu_hr_test.lisp
	./$(BIN) eval '(load "/tmp/zhiyu_hr_test.lisp" :reload #t) hr-v'
	@echo "=== m4 Python server reload ==="
	cd ../py && python3 -m workflow.zhiyu_runner --test-m4 --zhiyu ../zhiyu-core/$(BIN)
