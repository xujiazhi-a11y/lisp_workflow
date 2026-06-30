#include "zhiyu/internal.h"
#include "zhiyu/host.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void usage(const char *prog) {
    fprintf(stderr, "智语 Lisp (zhiyu-core)\n");
    fprintf(stderr, "用法:\n");
    fprintf(stderr, "  %s run <file.lisp> [--base-dir DIR]\n", prog);
    fprintf(stderr, "  %s eval \"(+ 1 2)\"\n", prog);
    fprintf(stderr, "  %s repl\n", prog);
    fprintf(stderr, "  %s server [--base-dir DIR]\n", prog);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    ZyVM *vm = zy_vm_new();
    if (!vm) return 1;

    const char *base_dir = NULL;
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--base-dir") == 0 && i + 1 < argc) {
            base_dir = argv[++i];
        }
    }
    if (base_dir) zy_set_base_dir(vm, base_dir);

    if (strcmp(argv[1], "run") == 0) {
        if (argc < 3) { usage(argv[0]); return 1; }
        ZyValue *r = zy_run_file(vm, argv[2]);
        if (vm->last_error[0]) {
            fprintf(stderr, "错误：%s\n", vm->last_error);
            zy_vm_free(vm);
            return 1;
        }
        if (r && r->type != ZY_NIL) {
            if (r->type == ZY_STR)
                puts(r->as.str);
            else
                zy_print_value(r);
            putchar('\n');
        }
        zy_release(r);
    } else if (strcmp(argv[1], "eval") == 0) {
        if (argc < 3) { usage(argv[0]); return 1; }
        ZyValue *r = zy_eval_string(vm, argv[2]);
        if (vm->last_error[0]) {
            fprintf(stderr, "错误：%s\n", vm->last_error);
            zy_vm_free(vm);
            return 1;
        }
        zy_print_value(r);
        putchar('\n');
        zy_release(r);
    } else if (strcmp(argv[1], "repl") == 0) {
        char line[4096];
        fputs("zhiyu> ", stdout);
        while (fgets(line, sizeof line, stdin)) {
            if (strcmp(line, "exit\n") == 0 || strcmp(line, "quit\n") == 0) break;
            vm->last_error[0] = '\0';
            ZyValue *r = zy_eval_string(vm, line);
            if (vm->last_error[0])
                fprintf(stderr, "错误：%s\n", vm->last_error);
            else if (r && r->type != ZY_NIL) {
                zy_print_value(r);
                putchar('\n');
            }
            zy_release(r);
            fputs("zhiyu> ", stdout);
        }
    } else if (strcmp(argv[1], "server") == 0) {
        zy_host_stdio_run(vm);
    } else {
        usage(argv[0]);
        zy_vm_free(vm);
        return 1;
    }

    zy_vm_free(vm);
    return 0;
}
