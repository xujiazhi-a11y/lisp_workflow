#include "zhiyu/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int sym_eq(ZyValue *a, ZyValue *b) {
    if (!a || !b) return 0;
    if (a == b) return 1;
    if (a->type == ZY_SYM && b->type == ZY_SYM)
        return strcmp(zy_sym_cstr(a), zy_sym_cstr(b)) == 0;
    return 0;
}

void zy_macro_register(ZyVM *vm, ZyValue *name, ZyValue *params, ZyValue *tmpl) {
    if (!vm || !name) return;
    for (size_t i = 0; i < vm->macro_count; i++) {
        if (sym_eq(vm->macros[i].name, name)) {
            vm->macros[i].params = NULL;
            vm->macros[i].param_count = 0;
            vm->macros[i].tmpl = zy_value_clone(tmpl);
            vm->macros[i].rest_param = (params->type == ZY_SYM);
            if (params->type == ZY_LIST) {
                vm->macros[i].param_count = params->as.list.count;
                vm->macros[i].params = params->as.list.items;
            } else if (params->type == ZY_SYM) {
                vm->macros[i].param_count = 1;
                vm->macros[i].params = &params;
            }
            return;
        }
    }
    if (vm->macro_count >= vm->macro_cap) {
        vm->macro_cap = vm->macro_cap ? vm->macro_cap * 2 : 8;
        vm->macros = realloc(vm->macros, vm->macro_cap * sizeof(struct ZyMacro));
    }
    struct ZyMacro *m = &vm->macros[vm->macro_count++];
    m->name = name;
    m->tmpl = zy_value_clone(tmpl);
    m->rest_param = (params->type == ZY_SYM);
    m->params = NULL;
    m->param_count = 0;
    if (params->type == ZY_LIST) {
        m->param_count = params->as.list.count;
        m->params = params->as.list.items;
    } else if (params->type == ZY_SYM) {
        m->param_count = 1;
        m->params = &params;
    }
}

ZyMacro *zy_macro_lookup(ZyVM *vm, ZyValue *name) {
    if (!vm || !name || name->type != ZY_SYM) return NULL;
    for (size_t i = 0; i < vm->macro_count; i++) {
        if (sym_eq(vm->macros[i].name, name))
            return &vm->macros[i];
    }
    const char *cn = zy_cn_resolve(zy_sym_cstr(name));
    if (cn) {
        ZyValue *en = zy_intern_symbol(cn);
        for (size_t i = 0; i < vm->macro_count; i++) {
            if (sym_eq(vm->macros[i].name, en))
                return &vm->macros[i];
        }
    }
    return NULL;
}

static ZyValue *substitute(ZyMacro *macro, ZyValue **bindings, size_t bind_count,
                           ZyValue *expr) {
    if (!expr) return zy_nil();
    if (expr->type == ZY_SYM) {
        for (size_t i = 0; i < bind_count; i++) {
            if (sym_eq(macro->params[i], expr))
                return bindings[i];
        }
        return expr;
    }
    if (expr->type == ZY_LIST) {
        ZyValue **items = malloc(expr->as.list.count * sizeof(ZyValue *));
        for (size_t i = 0; i < expr->as.list.count; i++)
            items[i] = substitute(macro, bindings, bind_count, expr->as.list.items[i]);
        ZyValue *r = zy_list(expr->as.list.count, items);
        free(items);
        return r;
    }
    return expr;
}

ZyValue *zy_macro_expand(ZyVM *vm, ZyMacro *macro, ZyValue **args, size_t argc) {
    (void)vm;
    ZyValue **bindings = calloc(macro->param_count ? macro->param_count : 1, sizeof(ZyValue *));
    if (macro->rest_param) {
        bindings[0] = zy_list(argc, args);
    } else {
        for (size_t i = 0; i < macro->param_count && i < argc; i++)
            bindings[i] = args[i];
    }
    ZyValue *r = substitute(macro, bindings, macro->param_count, macro->tmpl);
    free(bindings);
    return r;
}

static int path_loaded(ZyVM *vm, const char *path) {
    for (size_t i = 0; i < vm->loaded_count; i++)
        if (strcmp(vm->loaded_paths[i], path) == 0) return 1;
    return 0;
}

static void mark_loaded(ZyVM *vm, const char *path) {
    if (path_loaded(vm, path)) return;
    if (vm->loaded_count >= vm->loaded_cap) {
        vm->loaded_cap = vm->loaded_cap ? vm->loaded_cap * 2 : 8;
        vm->loaded_paths = realloc(vm->loaded_paths, vm->loaded_cap * sizeof(char *));
    }
    vm->loaded_paths[vm->loaded_count++] = strdup(path);
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

void zy_unmark_loaded(ZyVM *vm, const char *full_path) {
    if (!vm || !full_path) return;
    for (size_t i = 0; i < vm->loaded_count; i++) {
        if (strcmp(vm->loaded_paths[i], full_path) == 0) {
            free(vm->loaded_paths[i]);
            for (size_t j = i + 1; j < vm->loaded_count; j++)
                vm->loaded_paths[j - 1] = vm->loaded_paths[j];
            vm->loaded_count--;
            return;
        }
    }
}

static void resolve_full_path(ZyVM *vm, const char *path, char *full, size_t cap) {
    if (path[0] == '/' || (strlen(path) > 1 && path[1] == ':'))
        snprintf(full, cap, "%s", path);
    else if (vm->base_dir)
        snprintf(full, cap, "%s/%s", vm->base_dir, path);
    else
        snprintf(full, cap, "%s", path);
}

int zy_load_file(ZyVM *vm, const char *path, ZyEnv *env, int reload) {
    if (!vm || !path) return -1;
    char full[4096];
    resolve_full_path(vm, path, full, sizeof full);

    if (reload)
        zy_unmark_loaded(vm, full);

    if (path_loaded(vm, full)) return 0;

    char *code = read_file_all(full);
    if (!code) {
        snprintf(vm->last_error, sizeof vm->last_error, "文件不存在：%s", path);
        return -1;
    }
    mark_loaded(vm, full);
    char err[256] = {0};
    ZyValue *prog = zy_parse_all(code, err, sizeof err);
    free(code);
    if (!prog) {
        snprintf(vm->last_error, sizeof vm->last_error, "%s", err[0] ? err : "解析失败");
        return -1;
    }
    zy_eval_program(vm, prog, env);
    zy_release(prog);
    return vm->last_error[0] ? -1 : 0;
}
