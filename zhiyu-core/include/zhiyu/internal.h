#ifndef ZHIYU_INTERNAL_H
#define ZHIYU_INTERNAL_H

#include "zhiyu.h"

ZyValue *zy_intern_symbol(const char *name);
ZyValue *zy_native(ZyNativeFn fn);
ZyValue *zy_procedure(ZyProcedure *proc);

int zy_truthy(ZyValue *v);
int zy_is_keyword_sym(ZyValue *v);

ZyValue *zy_parse_all(const char *code, char *errbuf, size_t errcap);
ZyValue *zy_value_clone(ZyValue *v);

struct ZyEnv {
    ZyValue **keys;
    ZyValue **vals;
    size_t count;
    ZyEnv *outer;
};

ZyEnv *zy_env_new(ZyEnv *outer);
void zy_env_free(ZyEnv *env);
void zy_env_define(ZyEnv *env, ZyValue *key, ZyValue *val);
ZyEnv *zy_env_find_binding_env(ZyEnv *env, ZyValue *key, int *found);
ZyValue *zy_env_get(ZyEnv *env, ZyValue *key, int *ok);

void zy_register_builtins(ZyEnv *env);
const char *zy_cn_resolve(const char *name);

int zy_sf_define(const char *op);
int zy_sf_lambda(const char *op);
int zy_sf_if(const char *op);
int zy_sf_cond(const char *op);
int zy_sf_begin(const char *op);
int zy_sf_quote(const char *op);
int zy_sf_set(const char *op);
int zy_sf_let(const char *op);
int zy_sf_and(const char *op);
int zy_sf_or(const char *op);
int zy_sf_load(const char *op);
int zy_sf_defmacro(const char *op);
int zy_sf_macroexpand(const char *op);
int zy_sf_pipe(const char *op);
int zy_sf_arrow(const char *op);
int zy_sf_map(const char *op);
int zy_sf_reduce(const char *op);
int zy_sf_filter(const char *op);
int zy_sf_each(const char *op);

ZyValue *zy_eval(ZyVM *vm, ZyValue *exp, ZyEnv *env);
ZyValue *zy_eval_program(ZyVM *vm, ZyValue *prog, ZyEnv *env);
ZyValue *zy_apply(ZyVM *vm, ZyValue *fn, int argc, ZyValue **argv, ZyEnv *env);

void zy_macro_register(ZyVM *vm, ZyValue *name, ZyValue *params, ZyValue *tmpl);
ZyMacro *zy_macro_lookup(ZyVM *vm, ZyValue *name);
ZyValue *zy_macro_expand(ZyVM *vm, ZyMacro *macro, ZyValue **args, size_t argc);

ZyValue *zy_slot(ZyValue *val);
ZyValue *zy_slot_get(ZyValue *slot);
void zy_slot_set(ZyValue *slot, ZyValue *val);
ZyValue *zy_resolve_value(ZyValue *v);

int zy_load_file(ZyVM *vm, const char *path, ZyEnv *env, int reload);
void zy_unmark_loaded(ZyVM *vm, const char *full_path);

/* json.c */
ZyValue *zy_json_parse(const char *text, char *err, size_t errcap);
char *zy_json_stringify(ZyValue *v);
ZyValue *zy_json_extract(const char *text, ZyValue *default_val);

/* text.c */
char *zy_remove_think(const char *text);
char *zy_regex_replace(const char *pattern, const char *repl, const char *text);
char *zy_regex_match(const char *pattern, const char *text);
char *zy_strip(const char *text);

#endif
