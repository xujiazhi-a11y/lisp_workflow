#include "zhiyu/internal.h"
#include "zhiyu/host.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

ZyVM *zy_vm_new(void) {
    ZyVM *vm = calloc(1, sizeof(ZyVM));
    if (!vm) return NULL;
    vm->global = zy_env_new(NULL);
    zy_register_builtins(vm->global);
    zy_register_tier2_builtins(vm->global);
    return vm;
}

void zy_vm_free(ZyVM *vm) {
    if (!vm) return;
    zy_env_free(vm->global);
    free(vm->macros);
    for (size_t i = 0; i < vm->loaded_count; i++)
        free(vm->loaded_paths[i]);
    free(vm->loaded_paths);
    free(vm->base_dir);
    free(vm);
}

void zy_reset_load_cache(ZyVM *vm) {
    if (!vm) return;
    for (size_t i = 0; i < vm->loaded_count; i++)
        free(vm->loaded_paths[i]);
    free(vm->loaded_paths);
    vm->loaded_paths = NULL;
    vm->loaded_count = vm->loaded_cap = 0;
}

void zy_set_base_dir(ZyVM *vm, const char *dir) {
    if (!vm) return;
    free(vm->base_dir);
    vm->base_dir = dir ? strdup(dir) : NULL;
}

ZyValue *zy_eval_string(ZyVM *vm, const char *code) {
    if (!vm || !code) return zy_nil();
    vm->last_error[0] = '\0';
    char err[256] = {0};
    ZyValue *prog = zy_parse_all(code, err, sizeof err);
    if (!prog) {
        snprintf(vm->last_error, sizeof vm->last_error, "%s", err[0] ? err : "解析失败");
        return zy_nil();
    }
    ZyValue *r = zy_eval_program(vm, prog, vm->global);
    ZyValue *out = r ? zy_value_clone(r) : zy_nil();
    zy_release(prog);
    return out;
}

static char *read_file_all(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 0) { fclose(f); return NULL; }
    char *buf = malloc((size_t)sz + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t n = fread(buf, 1, (size_t)sz, f);
    buf[n] = '\0';
    fclose(f);
    return buf;
}

ZyValue *zy_run_file(ZyVM *vm, const char *path) {
    if (!vm || !path) return zy_nil();
    char full[4096];
    if (path[0] == '/' || (strlen(path) > 1 && path[1] == ':'))
        snprintf(full, sizeof full, "%s", path);
    else if (vm->base_dir)
        snprintf(full, sizeof full, "%s/%s", vm->base_dir, path);
    else
        snprintf(full, sizeof full, "%s", path);

    char *code = read_file_all(full);
    if (!code) {
        snprintf(vm->last_error, sizeof vm->last_error, "文件不存在：%s", path);
        return zy_nil();
    }
    ZyValue *r = zy_eval_string(vm, code);
    free(code);
    return r;
}
