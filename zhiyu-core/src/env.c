#include "zhiyu/internal.h"
#include <stdlib.h>
#include <string.h>

ZyEnv *zy_env_new(ZyEnv *outer) {
    ZyEnv *e = calloc(1, sizeof(ZyEnv));
    if (e) e->outer = outer;
    return e;
}

void zy_env_free(ZyEnv *env) {
    if (!env) return;
    for (size_t i = 0; i < env->count; i++)
        zy_release(env->vals[i]);
    free(env->keys);
    free(env->vals);
    free(env);
}

static int key_eq(ZyValue *a, ZyValue *b) {
    return a && b && a->type == ZY_SYM && b->type == ZY_SYM &&
           strcmp(zy_sym_cstr(a), zy_sym_cstr(b)) == 0;
}

void zy_env_define(ZyEnv *env, ZyValue *key, ZyValue *val) {
    for (size_t i = 0; i < env->count; i++) {
        if (key_eq(env->keys[i], key)) {
            zy_release(env->vals[i]);
            env->vals[i] = val;
            return;
        }
    }
    size_t n = env->count + 1;
    env->keys = realloc(env->keys, n * sizeof(ZyValue *));
    env->vals = realloc(env->vals, n * sizeof(ZyValue *));
    env->keys[env->count] = key;
    env->vals[env->count] = val;
    env->count = n;
}

ZyEnv *zy_env_find_binding_env(ZyEnv *env, ZyValue *key, int *found) {
    for (ZyEnv *e = env; e; e = e->outer) {
        for (size_t i = 0; i < e->count; i++) {
            if (key_eq(e->keys[i], key)) {
                if (found) *found = 1;
                return e;
            }
        }
    }
    if (found) *found = 0;
    return NULL;
}

ZyValue *zy_env_get(ZyEnv *env, ZyValue *key, int *ok) {
    int f = 0;
    ZyEnv *e = zy_env_find_binding_env(env, key, &f);
    if (!f) {
        if (ok) *ok = 0;
        return zy_nil();
    }
    for (size_t i = 0; i < e->count; i++) {
        if (key_eq(e->keys[i], key)) {
            if (ok) *ok = 1;
            return e->vals[i];
        }
    }
    if (ok) *ok = 0;
    return zy_nil();
}
