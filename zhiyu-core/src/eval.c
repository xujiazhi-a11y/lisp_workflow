#include "zhiyu/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

ZyValue *zy_apply(ZyVM *vm, ZyValue *fn, int argc, ZyValue **argv, ZyEnv *env);

static const char *sym_op(ZyValue *v) {
    if (!v || v->type != ZY_SYM) return "";
    return zy_sym_cstr(v);
}

static ZyValue *lookup(ZyVM *vm, ZyValue *sym, ZyEnv *env) {
    if (zy_is_keyword_sym(sym)) return sym;

    int ok = 0;
    ZyValue *v = zy_env_get(env, sym, &ok);
    if (ok) {
        v = zy_resolve_value(v);
        if (v->type == ZY_PROC || v->type == ZY_NATIVE || v->type == ZY_SYM)
            return v;
        return zy_value_clone(v);
    }

    const char *cn = zy_cn_resolve(zy_sym_cstr(sym));
    if (cn) {
        v = zy_env_get(env, zy_intern_symbol(cn), &ok);
        if (ok) {
            v = zy_resolve_value(v);
            if (v->type == ZY_PROC || v->type == ZY_NATIVE || v->type == ZY_SYM)
                return v;
            return zy_value_clone(v);
        }
    }

    snprintf(vm->last_error, sizeof vm->last_error, "未定义的符号: %s", zy_sym_cstr(sym));
    return zy_nil();
}

static int is_global_env(ZyEnv *env) {
    return env && !env->outer;
}

static void define_global_function(ZyEnv *env, ZyValue *fname, ZyValue *proc) {
    int ok = 0;
    ZyValue *existing = zy_env_get(env, fname, &ok);
    if (ok && existing && existing->type == ZY_SLOT) {
        zy_slot_set(existing, proc);
        return;
    }
    zy_env_define(env, fname, zy_slot(proc));
}

static ZyValue *eval_list(ZyVM *vm, ZyValue *exp, ZyEnv *env);

static ZyValue *make_lambda(ZyVM *vm, ZyValue *params, ZyValue *body, ZyEnv *env) {
    (void)vm;
    ZyProcedure *p = calloc(1, sizeof(ZyProcedure));
    if (!p) return zy_nil();

    if (params->type == ZY_LIST) {
        p->param_count = params->as.list.count;
        p->params = calloc(p->param_count, sizeof(ZyValue *));
        for (size_t i = 0; i < p->param_count; i++)
            p->params[i] = params->as.list.items[i];
    } else if (params->type == ZY_SYM) {
        p->param_count = 1;
        p->params = calloc(1, sizeof(ZyValue *));
        p->params[0] = params;
    }

    p->body = zy_value_clone(body);
    p->closure = env;
    return zy_procedure(p);
}

static ZyValue *thread_form(ZyVM *vm, ZyValue *result, ZyValue *form, ZyEnv *env) {
    if (form->type == ZY_LIST && form->as.list.count > 0) {
        ZyValue *fop = form->as.list.items[0];
        if (fop->type == ZY_SYM && zy_sf_lambda(zy_sym_cstr(fop))) {
            ZyValue *fn = zy_eval(vm, form, env);
            if (vm->last_error[0]) return zy_nil();
            ZyValue *argv[] = { result };
            return zy_apply(vm, fn, 1, argv, env);
        }
        ZyValue *fn = zy_eval(vm, fop, env);
        if (vm->last_error[0]) return zy_nil();
        int argc = (int)form->as.list.count - 1;
        ZyValue **argv = malloc((size_t)(argc + 1) * sizeof(ZyValue *));
        argv[0] = result;
        for (int i = 0; i < argc; i++) {
            argv[i + 1] = zy_eval(vm, form->as.list.items[i + 1], env);
            if (vm->last_error[0]) { free(argv); return zy_nil(); }
        }
        ZyValue *r = zy_apply(vm, fn, argc + 1, argv, env);
        for (int i = 1; i <= argc; i++) zy_release(argv[i]);
        free(argv);
        return r;
    }
    ZyValue *fn = zy_eval(vm, form, env);
    if (vm->last_error[0]) return zy_nil();
    ZyValue *argv[] = { result };
    return zy_apply(vm, fn, 1, argv, env);
}

ZyValue *zy_eval(ZyVM *vm, ZyValue *exp, ZyEnv *env) {
    if (!exp || exp->type == ZY_NIL) return zy_nil();

    if (exp->type == ZY_SYM) return lookup(vm, exp, env);

    if (exp->type == ZY_INT) return zy_int(exp->as.i);
    if (exp->type == ZY_FLOAT) return zy_float(exp->as.f);
    if (exp->type == ZY_STR) return zy_str_copy(exp->as.str);
    if (exp->type == ZY_BOOL) return zy_bool(exp->as.b);
    if (exp->type == ZY_NATIVE || exp->type == ZY_PROC) return exp;

    if (exp->type != ZY_LIST) return exp;

    if (exp->as.list.count == 0) return zy_nil();

    ZyValue *op = exp->as.list.items[0];
    const char *opn = sym_op(op);

    if (op->type == ZY_SYM) {
        ZyMacro *macro = zy_macro_lookup(vm, op);
        if (macro) {
            ZyValue **margs = exp->as.list.items + 1;
            size_t margc = exp->as.list.count - 1;
            ZyValue *expanded = zy_macro_expand(vm, macro, margs, margc);
            ZyValue *r = zy_eval(vm, expanded, env);
            zy_release(expanded);
            return r;
        }
    }

    if (zy_sf_quote(opn)) {
        if (exp->as.list.count < 2) return zy_nil();
        return exp->as.list.items[1];
    }

    if (zy_sf_if(opn)) {
        if (exp->as.list.count < 3) return zy_nil();
        ZyValue *test = zy_eval(vm, exp->as.list.items[1], env);
        if (vm->last_error[0]) return zy_nil();
        if (zy_truthy(test))
            return zy_eval(vm, exp->as.list.items[2], env);
        if (exp->as.list.count >= 4)
            return zy_eval(vm, exp->as.list.items[3], env);
        return zy_nil();
    }

    if (zy_sf_cond(opn)) {
        for (size_t i = 1; i < exp->as.list.count; i++) {
            ZyValue *clause = exp->as.list.items[i];
            if (clause->type != ZY_LIST || clause->as.list.count == 0) continue;
            const char *testn = sym_op(clause->as.list.items[0]);
            int else_br = strcmp(testn, "else") == 0 || strcmp(testn, "否则") == 0 ||
                          strcmp(testn, "其它情况") == 0;
            if (else_br || zy_truthy(zy_eval(vm, clause->as.list.items[0], env))) {
                if (clause->as.list.count == 2)
                    return zy_eval(vm, clause->as.list.items[1], env);
                ZyValue *items[32];
                size_t n = clause->as.list.count - 1;
                if (n > 32) n = 32;
                for (size_t j = 0; j < n; j++)
                    items[j] = clause->as.list.items[j + 1];
                ZyValue *begin = zy_intern_symbol("begin");
                ZyValue **full = malloc((n + 1) * sizeof(ZyValue *));
                full[0] = begin;
                memcpy(full + 1, items, n * sizeof(ZyValue *));
                ZyValue *form = zy_list(n + 1, full);
                ZyValue *r = zy_eval(vm, form, env);
                free(full);
                zy_release(form);
                return r;
            }
        }
        return zy_nil();
    }

    if (zy_sf_begin(opn)) {
        ZyValue *r = zy_nil();
        for (size_t i = 1; i < exp->as.list.count; i++) {
            r = zy_eval(vm, exp->as.list.items[i], env);
            if (vm->last_error[0]) return zy_nil();
        }
        return r;
    }

    if (zy_sf_define(opn)) {
        if (exp->as.list.count < 3) return zy_nil();
        ZyValue *name_form = exp->as.list.items[1];
        if (name_form->type == ZY_LIST && name_form->as.list.count > 0) {
            ZyValue *fname = name_form->as.list.items[0];
            ZyValue *params = zy_list(name_form->as.list.count - 1,
                                      name_form->as.list.items + 1);
            ZyValue *body_items[32];
            size_t bn = exp->as.list.count - 2;
            if (bn > 32) bn = 32;
            for (size_t i = 0; i < bn; i++)
                body_items[i] = exp->as.list.items[i + 2];
            ZyValue *body;
            if (bn == 1) {
                body = zy_value_clone(body_items[0]);
            } else {
                ZyValue *begin_sym = zy_intern_symbol("begin");
                ZyValue **items = malloc((bn + 1) * sizeof(ZyValue *));
                items[0] = begin_sym;
                for (size_t i = 0; i < bn; i++)
                    items[i + 1] = zy_value_clone(body_items[i]);
                body = zy_list(bn + 1, items);
                free(items);
            }
            ZyValue *lam_form_items[] = {
                zy_intern_symbol("lambda"), params, body
            };
            ZyValue *lam = zy_list(3, lam_form_items);
            ZyValue *proc = zy_eval(vm, lam, env);
            zy_release(lam);
            if (is_global_env(env))
                define_global_function(env, fname, proc);
            else
                zy_env_define(env, fname, proc);
            return zy_nil();
        }
        ZyValue *name = name_form;
        ZyValue *val;
        if (exp->as.list.count > 3) {
            ZyValue *items[64];
            size_t n = exp->as.list.count - 2;
            if (n > 64) n = 64;
            items[0] = zy_intern_symbol("begin");
            for (size_t i = 0; i < n; i++)
                items[i + 1] = exp->as.list.items[i + 2];
            ZyValue *form = zy_list(n + 1, items);
            val = zy_eval(vm, form, env);
            zy_release(form);
        } else {
            val = zy_eval(vm, exp->as.list.items[2], env);
        }
        zy_env_define(env, name, val);
        return zy_nil();
    }

    if (zy_sf_defmacro(opn)) {
        if (exp->as.list.count < 4) return zy_nil();
        ZyValue *name = exp->as.list.items[1];
        ZyValue *params = exp->as.list.items[2];
        ZyValue *tmpl;
        if (exp->as.list.count == 4)
            tmpl = exp->as.list.items[3];
        else {
            ZyValue *items[64];
            size_t n = exp->as.list.count - 3;
            if (n > 64) n = 64;
            for (size_t i = 0; i < n; i++)
                items[i] = exp->as.list.items[i + 3];
            tmpl = zy_list(n, items);
        }
        zy_macro_register(vm, name, params, tmpl);
        return zy_nil();
    }

    if (zy_sf_macroexpand(opn)) {
        if (exp->as.list.count < 2) return zy_nil();
        ZyMacro *macro = zy_macro_lookup(vm, exp->as.list.items[1]);
        if (!macro) {
            snprintf(vm->last_error, sizeof vm->last_error, "未定义的宏");
            return zy_nil();
        }
        return zy_value_clone(macro->tmpl);
    }

    if (zy_sf_load(opn)) {
        if (exp->as.list.count < 2) return zy_nil();
        int reload = 0;
        for (size_t i = 2; i + 1 < exp->as.list.count; i++) {
            ZyValue *k = exp->as.list.items[i];
            if (k->type == ZY_SYM && strcmp(zy_sym_cstr(k), ":reload") == 0) {
                reload = zy_truthy(exp->as.list.items[i + 1]);
                break;
            }
        }
        ZyValue *path_val = zy_eval(vm, exp->as.list.items[1], env);
        if (vm->last_error[0]) return zy_nil();
        const char *path = zy_value_to_cstr(path_val);
        zy_load_file(vm, path, env, reload);
        zy_release(path_val);
        return zy_nil();
    }

    if (zy_sf_lambda(opn)) {
        if (exp->as.list.count < 3) return zy_nil();
        ZyValue *params = exp->as.list.items[1];
        ZyValue *body;
        if (exp->as.list.count == 3) {
            body = exp->as.list.items[2];
        } else {
            ZyValue *begin_sym = zy_intern_symbol("begin");
            ZyValue *items[64];
            size_t n = exp->as.list.count - 2;
            if (n > 63) n = 63;
            items[0] = begin_sym;
            for (size_t i = 0; i < n; i++)
                items[i + 1] = exp->as.list.items[i + 2];
            body = zy_list(n + 1, items);
        }
        return make_lambda(vm, params, body, env);
    }

    if (zy_sf_set(opn)) {
        if (exp->as.list.count < 3) return zy_nil();
        ZyValue *var = exp->as.list.items[1];
        ZyValue *val = zy_eval(vm, exp->as.list.items[2], env);
        int found = 0;
        ZyEnv *bind = zy_env_find_binding_env(env, var, &found);
        if (!found) {
            snprintf(vm->last_error, sizeof vm->last_error, "未定义的符号: %s", zy_sym_cstr(var));
            zy_release(val);
            return zy_nil();
        }
        for (size_t i = 0; i < bind->count; i++) {
            if (bind->keys[i] == var || (bind->keys[i]->type == ZY_SYM && var->type == ZY_SYM &&
                strcmp(zy_sym_cstr(bind->keys[i]), zy_sym_cstr(var)) == 0)) {
                zy_release(bind->vals[i]);
                bind->vals[i] = val;
                break;
            }
        }
        return zy_nil();
    }

    if (zy_sf_let(opn)) {
        if (exp->as.list.count < 3) return zy_nil();
        ZyValue *bindings = exp->as.list.items[1];
        ZyEnv *new_env = zy_env_new(env);
        if (bindings->type == ZY_LIST) {
            for (size_t i = 0; i < bindings->as.list.count; i++) {
                ZyValue *b = bindings->as.list.items[i];
                if (b->type != ZY_LIST || b->as.list.count < 2) continue;
                ZyValue *val = zy_eval(vm, b->as.list.items[1], new_env);
                zy_env_define(new_env, b->as.list.items[0], val);
            }
        }
        ZyValue *r = zy_nil();
        for (size_t i = 2; i < exp->as.list.count; i++) {
            r = zy_eval(vm, exp->as.list.items[i], new_env);
            if (vm->last_error[0]) break;
        }
        zy_env_free(new_env);
        return r;
    }

    if (zy_sf_and(opn)) {
        ZyValue *v = zy_bool(true);
        for (size_t i = 1; i < exp->as.list.count; i++) {
            v = zy_eval(vm, exp->as.list.items[i], env);
            if (!zy_truthy(v)) return v;
        }
        return v;
    }

    if (zy_sf_or(opn)) {
        for (size_t i = 1; i < exp->as.list.count; i++) {
            ZyValue *v = zy_eval(vm, exp->as.list.items[i], env);
            if (zy_truthy(v)) return v;
        }
        return zy_bool(false);
    }

    if (zy_sf_pipe(opn)) {
        if (exp->as.list.count < 2) return zy_nil();
        ZyValue *init = exp->as.list.items[1];
        ZyValue *result = zy_eval(vm, init, env);
        for (size_t i = 2; i < exp->as.list.count; i++) {
            if (vm->last_error[0]) { zy_release(result); return zy_nil(); }
            ZyValue *fn = zy_eval(vm, exp->as.list.items[i], env);
            if (vm->last_error[0]) { zy_release(result); return zy_nil(); }
            ZyValue *argv[] = { result };
            ZyValue *next = zy_apply(vm, fn, 1, argv, env);
            zy_release(result);
            result = next;
        }
        return result;
    }

    if (zy_sf_arrow(opn)) {
        if (exp->as.list.count < 2) return zy_nil();
        ZyValue *result = zy_eval(vm, exp->as.list.items[1], env);
        for (size_t i = 2; i < exp->as.list.count; i++) {
            if (vm->last_error[0]) { zy_release(result); return zy_nil(); }
            ZyValue *next = thread_form(vm, result, exp->as.list.items[i], env);
            zy_release(result);
            result = next;
        }
        return result;
    }

    if (zy_sf_map(opn)) {
        if (exp->as.list.count < 3) return zy_list(0, NULL);
        ZyValue *fn = zy_eval(vm, exp->as.list.items[1], env);
        ZyValue *lst = zy_eval(vm, exp->as.list.items[2], env);
        if (vm->last_error[0] || !lst || lst->type != ZY_LIST) return zy_list(0, NULL);
        ZyValue **items = malloc(lst->as.list.count * sizeof(ZyValue *));
        for (size_t i = 0; i < lst->as.list.count; i++) {
            ZyValue *argv[] = { lst->as.list.items[i] };
            items[i] = zy_apply(vm, fn, 1, argv, env);
        }
        ZyValue *r = zy_list(lst->as.list.count, items);
        free(items);
        return r;
    }

    if (zy_sf_reduce(opn)) {
        if (exp->as.list.count < 4) return zy_nil();
        ZyValue *fn = zy_eval(vm, exp->as.list.items[1], env);
        ZyValue *acc = zy_eval(vm, exp->as.list.items[2], env);
        ZyValue *lst = zy_eval(vm, exp->as.list.items[3], env);
        if (vm->last_error[0] || !lst || lst->type != ZY_LIST) return acc;
        for (size_t i = 0; i < lst->as.list.count; i++) {
            ZyValue *argv[] = { acc, lst->as.list.items[i] };
            ZyValue *next = zy_apply(vm, fn, 2, argv, env);
            if (next != acc) zy_release(acc);
            acc = next;
            if (vm->last_error[0]) break;
        }
        return acc;
    }

    if (zy_sf_filter(opn)) {
        if (exp->as.list.count < 3) return zy_list(0, NULL);
        ZyValue *fn = zy_eval(vm, exp->as.list.items[1], env);
        ZyValue *lst = zy_eval(vm, exp->as.list.items[2], env);
        if (vm->last_error[0] || !lst || lst->type != ZY_LIST) return zy_list(0, NULL);
        ZyValue **items = malloc(lst->as.list.count * sizeof(ZyValue *));
        size_t n = 0;
        for (size_t i = 0; i < lst->as.list.count; i++) {
            ZyValue *argv[] = { lst->as.list.items[i] };
            ZyValue *keep = zy_apply(vm, fn, 1, argv, env);
            if (zy_truthy(keep)) items[n++] = lst->as.list.items[i];
        }
        ZyValue *r = zy_list(n, items);
        free(items);
        return r;
    }

    if (zy_sf_each(opn)) {
        if (exp->as.list.count < 3) return zy_nil();
        ZyValue *fn = zy_eval(vm, exp->as.list.items[1], env);
        ZyValue *lst = zy_eval(vm, exp->as.list.items[2], env);
        if (vm->last_error[0] || !lst || lst->type != ZY_LIST) return zy_nil();
        ZyValue *r = zy_nil();
        for (size_t i = 0; i < lst->as.list.count; i++) {
            ZyValue *argv[] = { lst->as.list.items[i] };
            r = zy_apply(vm, fn, 1, argv, env);
            if (vm->last_error[0]) break;
        }
        return r;
    }

    return eval_list(vm, exp, env);
}

static ZyValue *eval_list(ZyVM *vm, ZyValue *exp, ZyEnv *env) {
    ZyValue *fn_val = zy_eval(vm, exp->as.list.items[0], env);
    if (vm->last_error[0]) return zy_nil();

    if (fn_val->type == ZY_LIST && fn_val->as.list.count > 0) {
        ZyValue *op = fn_val->as.list.items[0];
        if (op->type == ZY_SYM && zy_sf_lambda(zy_sym_cstr(op)))
            fn_val = zy_eval(vm, fn_val, env);
    }

    int argc = (int)exp->as.list.count - 1;
    ZyValue **argv = NULL;
    if (argc > 0) {
        argv = malloc((size_t)argc * sizeof(ZyValue *));
        for (int i = 0; i < argc; i++) {
            argv[i] = zy_eval(vm, exp->as.list.items[i + 1], env);
            if (vm->last_error[0]) {
                free(argv);
                return zy_nil();
            }
        }
    }
    ZyValue *r = zy_apply(vm, fn_val, argc, argv, env);
    if (argv) {
        for (int i = 0; i < argc; i++) {
            if (argv[i] == r) continue;
            if (argv[i]->type == ZY_PROC || argv[i]->type == ZY_NATIVE ||
                argv[i]->type == ZY_SYM || argv[i]->type == ZY_SLOT)
                continue;
            zy_release(argv[i]);
        }
        free(argv);
    }
    return r;
}

ZyValue *zy_eval_program(ZyVM *vm, ZyValue *prog, ZyEnv *env) {
    if (!prog || prog->type != ZY_LIST) return zy_nil();
    ZyValue *r = zy_nil();
    vm->last_error[0] = '\0';
    for (size_t i = 0; i < prog->as.list.count; i++) {
        r = zy_eval(vm, prog->as.list.items[i], env);
        if (vm->last_error[0]) return zy_nil();
    }
    return r;
}
