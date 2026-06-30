#include "zhiyu/internal.h"
#include "zhiyu/host.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static double to_num(ZyValue *v) {
    if (!v) return 0;
    if (v->type == ZY_INT) return (double)v->as.i;
    if (v->type == ZY_FLOAT) return v->as.f;
    return 0;
}

static const char *dict_key_cstr(ZyValue *k) {
    if (!k) return "";
    if (k->type == ZY_STR) return k->as.str ? k->as.str : "";
    return zy_sym_cstr(k);
}

static int dict_key_eq(ZyValue *a, const char *key) {
    if (!a || !key) return 0;
    if (a->type == ZY_STR && a->as.str) return strcmp(a->as.str, key) == 0;
    if (a->type == ZY_SYM) return strcmp(zy_sym_cstr(a), key) == 0;
    return 0;
}

static ZyValue *dict_get(ZyValue *d, const char *key) {
    if (!d || d->type != ZY_DICT || !d->as.dict) return zy_nil();
    for (size_t i = 0; i < d->as.dict->count; i++) {
        if (dict_key_eq(d->as.dict->keys[i], key))
            return d->as.dict->vals[i];
    }
    return zy_nil();
}

static void dict_put(ZyValue *d, const char *key, ZyValue *val) {
    if (!d || d->type != ZY_DICT || !d->as.dict) return;
    for (size_t i = 0; i < d->as.dict->count; i++) {
        if (dict_key_eq(d->as.dict->keys[i], key)) {
            zy_release(d->as.dict->vals[i]);
            d->as.dict->vals[i] = val;
            return;
        }
    }
    size_t n = d->as.dict->count + 1;
    d->as.dict->keys = realloc(d->as.dict->keys, n * sizeof(ZyValue *));
    d->as.dict->vals = realloc(d->as.dict->vals, n * sizeof(ZyValue *));
    d->as.dict->keys[d->as.dict->count] = zy_str_copy(key);
    d->as.dict->vals[d->as.dict->count] = val;
    d->as.dict->count = n;
}

static ZyValue *native_add(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    double sum = 0;
    int any_float = 0;
    for (int i = 0; i < argc; i++) {
        if (argv[i]->type == ZY_FLOAT) any_float = 1;
        sum += to_num(argv[i]);
    }
    if (!any_float) {
        for (int i = 0; i < argc; i++)
            if (argv[i]->type != ZY_INT) any_float = 1;
    }
    return any_float ? zy_float(sum) : zy_int((long long)sum);
}

static ZyValue *native_sub(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc == 0) return zy_int(0);
    double r = to_num(argv[0]);
    if (argc == 1) return zy_float(-r);
    for (int i = 1; i < argc; i++) r -= to_num(argv[i]);
    return zy_float(r);
}

static ZyValue *native_mul(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    double p = 1;
    for (int i = 0; i < argc; i++) p *= to_num(argv[i]);
    return zy_float(p);
}

static ZyValue *native_div(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc == 0) return zy_int(1);
    double r = to_num(argv[0]);
    if (argc == 1) return zy_float(1.0 / r);
    for (int i = 1; i < argc; i++) r /= to_num(argv[i]);
    return zy_float(r);
}

static ZyValue *native_print(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)env;
    char *buf = NULL;
    size_t len = 0, cap = 0;
    for (int i = 0; i < argc; i++) {
        if (i) {
            if (len + 2 > cap) { cap = (cap + 16) * 2; buf = realloc(buf, cap); }
            buf[len++] = ' ';
            buf[len] = '\0';
        }
        char *part = (argv[i]->type == ZY_STR) ? strdup(argv[i]->as.str) : zy_to_string(argv[i]);
        size_t pl = strlen(part);
        if (len + pl + 1 > cap) { cap = (cap + pl + 32) * 2; buf = realloc(buf, cap); }
        memcpy(buf + len, part, pl);
        len += pl;
        buf[len] = '\0';
        free(part);
    }
    const char *text = buf ? buf : "";
    if (vm->host && vm->host->print_fn) {
        vm->host->print_fn(vm->host->userdata, 0, text);
        free(buf);
        return zy_nil();
    }
    fputs(text, stdout);
    putchar('\n');
    fflush(stdout);
    free(buf);
    return zy_nil();
}

static ZyValue *native_str(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    char *buf = NULL;
    size_t len = 0, cap = 0;
    for (int i = 0; i < argc; i++) {
        char *part = (argv[i]->type == ZY_STR) ? strdup(argv[i]->as.str) : zy_to_string(argv[i]);
        size_t pl = strlen(part);
        if (len + pl + 1 > cap) {
            cap = (cap + pl + 32) * 2;
            buf = realloc(buf, cap);
        }
        memcpy(buf + len, part, pl);
        len += pl;
        buf[len] = '\0';
        free(part);
    }
    ZyValue *v = zy_str_copy(buf ? buf : "");
    free(buf);
    return v;
}

static ZyValue *native_str_concat(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    return native_str(vm, env, argc, argv);
}

static ZyValue *native_str_join(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    if (argc < 2) return zy_str_copy("");
    const char *sep = zy_value_to_cstr(argv[0]);
    ZyValue *lst = argv[1];
    if (!lst || lst->type != ZY_LIST) return zy_str_copy("");
    char *buf = NULL;
    size_t len = 0, cap = 0;
    for (size_t i = 0; i < lst->as.list.count; i++) {
        if (i) {
            size_t sl = strlen(sep);
            if (len + sl + 1 > cap) { cap = (cap + sl + 32) * 2; buf = realloc(buf, cap); }
            memcpy(buf + len, sep, sl);
            len += sl;
            buf[len] = '\0';
        }
        char *part = zy_to_string(lst->as.list.items[i]);
        size_t pl = strlen(part);
        if (len + pl + 1 > cap) { cap = (cap + pl + 32) * 2; buf = realloc(buf, cap); }
        memcpy(buf + len, part, pl);
        len += pl;
        buf[len] = '\0';
        free(part);
    }
    ZyValue *r = zy_str_copy(buf ? buf : "");
    free(buf);
    return r;
}

static ZyValue *native_list(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    ZyValue **items = malloc((size_t)argc * sizeof(ZyValue *));
    for (int i = 0; i < argc; i++) items[i] = zy_value_clone(argv[i]);
    ZyValue *r = zy_list((size_t)argc, items);
    free(items);
    return r;
}

static ZyValue *native_car(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1 || argv[0]->type != ZY_LIST || argv[0]->as.list.count == 0)
        return zy_nil();
    return zy_value_clone(argv[0]->as.list.items[0]);
}

static ZyValue *native_cdr(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1 || argv[0]->type != ZY_LIST || argv[0]->as.list.count == 0)
        return zy_list(0, NULL);
    size_t n = argv[0]->as.list.count - 1;
    ZyValue **items = malloc(n * sizeof(ZyValue *));
    for (size_t i = 0; i < n; i++)
        items[i] = zy_value_clone(argv[0]->as.list.items[i + 1]);
    ZyValue *r = zy_list(n, items);
    free(items);
    return r;
}

static ZyValue *native_nth(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)env;
    if (argc < 2 || argv[0]->type != ZY_INT || argv[1]->type != ZY_LIST)
        return zy_nil();
    long long idx = argv[0]->as.i;
    if (idx < 0 || (size_t)idx >= argv[1]->as.list.count) {
        snprintf(vm->last_error, sizeof vm->last_error, "索引越界: %lld", idx);
        return zy_nil();
    }
    return zy_value_clone(argv[1]->as.list.items[(size_t)idx]);
}

static ZyValue *native_cons(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_list(0, NULL);
    ZyValue *a = argv[0];
    ZyValue *b = argv[1];
    if (b->type == ZY_LIST) {
        ZyValue **items = malloc((b->as.list.count + 1) * sizeof(ZyValue *));
        items[0] = a;
        for (size_t i = 0; i < b->as.list.count; i++)
            items[i + 1] = b->as.list.items[i];
        ZyValue *r = zy_list(b->as.list.count + 1, items);
        free(items);
        return r;
    }
    ZyValue *pair[] = { a, b };
    return zy_list(2, pair);
}

static ZyValue *native_nullp(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_bool(true);
    ZyValue *v = argv[0];
    if (!v || v->type == ZY_NIL) return zy_bool(true);
    if (v->type == ZY_LIST && v->as.list.count == 0) return zy_bool(true);
    return zy_bool(false);
}

static ZyValue *native_pairp(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1 || !argv[0] || argv[0]->type != ZY_LIST) return zy_bool(false);
    return zy_bool(argv[0]->as.list.count == 2);
}

static ZyValue *native_eq(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(true);
    ZyValue *a = argv[0], *b = argv[1];
    if (a->type != b->type) return zy_bool(false);
    switch (a->type) {
    case ZY_NIL: return zy_bool(true);
    case ZY_BOOL: return zy_bool(a->as.b == b->as.b);
    case ZY_INT: return zy_bool(a->as.i == b->as.i);
    case ZY_FLOAT: return zy_bool(a->as.f == b->as.f);
    case ZY_STR: return zy_bool(strcmp(a->as.str, b->as.str) == 0);
    case ZY_SYM: return zy_bool(a == b);
    default: return zy_bool(false);
    }
}

static ZyValue *native_gt(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(false);
    return zy_bool(to_num(argv[0]) > to_num(argv[1]));
}

static ZyValue *native_lt(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(false);
    return zy_bool(to_num(argv[0]) < to_num(argv[1]));
}

static ZyValue *native_length(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_int(0);
    if (argv[0]->type == ZY_LIST) return zy_int((long long)argv[0]->as.list.count);
    if (argv[0]->type == ZY_STR) return zy_int((long long)strlen(argv[0]->as.str));
    return zy_int(0);
}

static ZyValue *native_append(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_list(0, NULL);
    size_t total = 0;
    for (int i = 0; i < argc; i++) {
        if (argv[i]->type == ZY_LIST) total += argv[i]->as.list.count;
        else total += 1;
    }
    ZyValue **items = malloc(total * sizeof(ZyValue *));
    size_t idx = 0;
    for (int i = 0; i < argc; i++) {
        if (argv[i]->type == ZY_LIST) {
            for (size_t j = 0; j < argv[i]->as.list.count; j++)
                items[idx++] = zy_value_clone(argv[i]->as.list.items[j]);
        } else {
            items[idx++] = zy_value_clone(argv[i]);
        }
    }
    ZyValue *r = zy_list(total, items);
    free(items);
    return r;
}

static ZyValue *native_format(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("");
    const char *tmpl = zy_value_to_cstr(argv[0]);
    char *result = strdup(tmpl ? tmpl : "");
    if (strstr(result, "{{") && argc >= 3) {
        for (int i = 1; i + 1 < argc; i += 2) {
            const char *key = zy_value_to_cstr(argv[i]);
            char *val = zy_to_string(argv[i + 1]);
            char needle[256];
            snprintf(needle, sizeof needle, "{{%s}}", key);
            char *pos = strstr(result, needle);
            if (pos) {
                size_t pre = (size_t)(pos - result);
                size_t post = strlen(pos + strlen(needle));
                char *n = malloc(pre + strlen(val) + post + 1);
                memcpy(n, result, pre);
                memcpy(n + pre, val, strlen(val));
                memcpy(n + pre + strlen(val), pos + strlen(needle), post + 1);
                free(result);
                result = n;
            }
            free(val);
        }
    }
    ZyValue *r = zy_str_copy(result);
    free(result);
    return r;
}

static ZyValue *native_read_file(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)env;
    if (argc < 1) return zy_str_copy("");
    const char *path = zy_value_to_cstr(argv[0]);
    char full[4096];
    if (path[0] == '/' || (strlen(path) > 1 && path[1] == ':'))
        snprintf(full, sizeof full, "%s", path);
    else if (vm->base_dir)
        snprintf(full, sizeof full, "%s/%s", vm->base_dir, path);
    else
        snprintf(full, sizeof full, "%s", path);
    FILE *f = fopen(full, "rb");
    if (!f) {
        snprintf(vm->last_error, sizeof vm->last_error, "文件不存在：%s", path);
        return zy_nil();
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc((size_t)sz + 1);
    fread(buf, 1, (size_t)sz, f);
    buf[sz] = '\0';
    fclose(f);
    ZyValue *r = zy_str_copy(buf);
    free(buf);
    return r;
}

static ZyValue *native_dict(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    size_t n = (size_t)argc / 2;
    ZyValue **keys = malloc(n * sizeof(ZyValue *));
    ZyValue **vals = malloc(n * sizeof(ZyValue *));
    for (size_t i = 0; i < n; i++) {
        keys[i] = zy_str_copy(zy_value_to_cstr(argv[i * 2]));
        vals[i] = zy_value_clone(argv[i * 2 + 1]);
    }
    ZyValue *r = zy_dict(n, keys, vals);
    free(keys);
    free(vals);
    return r;
}

static ZyValue *native_get(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_nil();
    ZyValue *v = dict_get(argv[0], zy_value_to_cstr(argv[1]));
    return zy_value_clone(v);
}

static ZyValue *native_put(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 3) return argv[0];
    dict_put(argv[0], zy_value_to_cstr(argv[1]), zy_value_clone(argv[2]));
    return argv[0];
}

static ZyValue *native_parse_json(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)env;
    if (argc < 1) return zy_nil();
    char err[128] = {0};
    ZyValue *v = zy_json_parse(zy_value_to_cstr(argv[0]), err, sizeof err);
    if (err[0]) {
        snprintf(vm->last_error, sizeof vm->last_error, "JSON 解析失败：%s", err);
        return zy_nil();
    }
    return v;
}

static ZyValue *native_to_json(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("null");
    char *s = zy_json_stringify(argv[0]);
    ZyValue *r = zy_str_copy(s);
    free(s);
    return r;
}

static ZyValue *native_extract_json(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_nil();
    ZyValue *def = argc >= 2 ? argv[1] : zy_nil();
    return zy_json_extract(zy_value_to_cstr(argv[0]), def);
}

static ZyValue *native_remove_think(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("");
    char *s = zy_remove_think(zy_value_to_cstr(argv[0]));
    ZyValue *r = zy_str_copy(s);
    free(s);
    return r;
}

static ZyValue *native_regex_match(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_nil();
    char *m = zy_regex_match(zy_value_to_cstr(argv[0]), zy_value_to_cstr(argv[1]));
    if (!m) return zy_nil();
    ZyValue *r = zy_str_copy(m);
    free(m);
    return r;
}

static ZyValue *native_regex_replace(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 3) return zy_value_clone(argv[argc - 1]);
    char *s = zy_regex_replace(zy_value_to_cstr(argv[0]), zy_value_to_cstr(argv[1]),
                               zy_value_to_cstr(argv[2]));
    ZyValue *r = zy_str_copy(s);
    free(s);
    return r;
}

static ZyValue *native_strip(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("");
    char *s = zy_strip(zy_value_to_cstr(argv[0]));
    ZyValue *r = zy_str_copy(s);
    free(s);
    return r;
}

static ZyValue *native_not(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_bool(true);
    return zy_bool(!zy_truthy(argv[0]));
}

static ZyValue *native_gte(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(false);
    return zy_bool(to_num(argv[0]) >= to_num(argv[1]));
}

static ZyValue *native_lte(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(false);
    return zy_bool(to_num(argv[0]) <= to_num(argv[1]));
}

static ZyValue *native_str_trim(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("");
    const char *s = zy_value_to_cstr(argv[0]);
    while (*s && (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r')) s++;
    const char *end = s + strlen(s);
    while (end > s && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\n' || end[-1] == '\r'))
        end--;
    size_t n = (size_t)(end - s);
    char *out = malloc(n + 1);
    memcpy(out, s, n);
    out[n] = '\0';
    ZyValue *r = zy_str_copy(out);
    free(out);
    return r;
}

static ZyValue *native_str_contains(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(false);
    const char *sub = zy_value_to_cstr(argv[0]);
    const char *s = zy_value_to_cstr(argv[1]);
    return zy_bool(strstr(s, sub) != NULL);
}

static ZyValue *native_str_starts(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_bool(false);
    const char *pre = zy_value_to_cstr(argv[0]);
    const char *s = zy_value_to_cstr(argv[1]);
    size_t pl = strlen(pre);
    return zy_bool(strncmp(s, pre, pl) == 0);
}

static ZyValue *native_str_upper(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("");
    const char *s = zy_value_to_cstr(argv[0]);
    char *out = strdup(s);
    for (char *p = out; *p; p++)
        if (*p >= 'a' && *p <= 'z') *p = (char)(*p - 'a' + 'A');
    ZyValue *r = zy_str_copy(out);
    free(out);
    return r;
}

static ZyValue *native_str_lower(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1) return zy_str_copy("");
    const char *s = zy_value_to_cstr(argv[0]);
    char *out = strdup(s);
    for (char *p = out; *p; p++)
        if (*p >= 'A' && *p <= 'Z') *p = (char)(*p - 'A' + 'a');
    ZyValue *r = zy_str_copy(out);
    free(out);
    return r;
}

static ZyValue *native_str_split(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2) return zy_list(0, NULL);
    const char *sep = zy_value_to_cstr(argv[0]);
    const char *s = zy_value_to_cstr(argv[1]);
    if (!sep[0]) {
        size_t n = strlen(s);
        ZyValue **items = malloc(n * sizeof(ZyValue *));
        for (size_t i = 0; i < n; i++) {
            char ch[2] = { s[i], '\0' };
            items[i] = zy_str_copy(ch);
        }
        ZyValue *r = zy_list(n, items);
        free(items);
        return r;
    }
    size_t seplen = strlen(sep);
    ZyValue **items = NULL;
    size_t count = 0, cap = 0;
    const char *p = s;
    while (*p) {
        const char *found = strstr(p, sep);
        size_t len = found ? (size_t)(found - p) : strlen(p);
        char *part = malloc(len + 1);
        memcpy(part, p, len);
        part[len] = '\0';
        if (count >= cap) {
            cap = cap ? cap * 2 : 4;
            items = realloc(items, cap * sizeof(ZyValue *));
        }
        items[count++] = zy_str_copy(part);
        free(part);
        if (!found) break;
        p = found + seplen;
    }
    if (count == 0 && *s == '\0')
        items = NULL;
    ZyValue *r = zy_list(count, items);
    free(items);
    return r;
}

static ZyValue *native_keys(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 1 || argv[0]->type != ZY_DICT || !argv[0]->as.dict)
        return zy_list(0, NULL);
    size_t n = argv[0]->as.dict->count;
    ZyValue **items = malloc(n * sizeof(ZyValue *));
    for (size_t i = 0; i < n; i++) {
        const char *k = zy_value_to_cstr(argv[0]->as.dict->keys[i]);
        items[i] = zy_str_copy(k);
    }
    ZyValue *r = zy_list(n, items);
    free(items);
    return r;
}

static ZyValue *native_take(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)vm; (void)env;
    if (argc < 2 || argv[1]->type != ZY_LIST) return zy_list(0, NULL);
    long long n = (argc > 0 && argv[0]->type == ZY_INT) ? argv[0]->as.i : 0;
    if (n < 0) n = 0;
    size_t count = argv[1]->as.list.count;
    if ((size_t)n > count) n = (long long)count;
    ZyValue **items = malloc((size_t)n * sizeof(ZyValue *));
    for (long long i = 0; i < n; i++)
        items[i] = zy_value_clone(argv[1]->as.list.items[i]);
    ZyValue *r = zy_list((size_t)n, items);
    free(items);
    return r;
}

static ZyValue *native_sort(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    if (argc < 2 || argv[1]->type != ZY_LIST) return zy_list(0, NULL);
    size_t n = argv[1]->as.list.count;
    if (n == 0) return zy_list(0, NULL);
    ZyValue **items = malloc(n * sizeof(ZyValue *));
    for (size_t i = 0; i < n; i++)
        items[i] = zy_value_clone(argv[1]->as.list.items[i]);
    for (size_t i = 0; i + 1 < n; i++) {
        for (size_t j = 0; j + 1 < n - i; j++) {
            ZyValue *args[] = { items[j], items[j + 1] };
            ZyValue *r = zy_apply(vm, argv[0], 2, args, env);
            if (to_num(r) > 0) {
                ZyValue *tmp = items[j];
                items[j] = items[j + 1];
                items[j + 1] = tmp;
            }
        }
    }
    ZyValue *r = zy_list(n, items);
    free(items);
    return r;
}

static void reg_native(ZyEnv *env, const char *name, ZyNativeFn fn) {
    zy_env_define(env, zy_intern_symbol(name), zy_native(fn));
}

void zy_register_builtins(ZyEnv *env) {
    reg_native(env, "+", native_add);
    reg_native(env, "-", native_sub);
    reg_native(env, "*", native_mul);
    reg_native(env, "/", native_div);
    reg_native(env, "print", native_print);
    reg_native(env, "println", native_print);
    reg_native(env, "str", native_str);
    reg_native(env, "str-concat", native_str_concat);
    reg_native(env, "str-join", native_str_join);
    reg_native(env, "list", native_list);
    reg_native(env, "cons", native_cons);
    reg_native(env, "car", native_car);
    reg_native(env, "cdr", native_cdr);
    reg_native(env, "nth", native_nth);
    reg_native(env, "first", native_car);
    reg_native(env, "rest", native_cdr);
    reg_native(env, "null?", native_nullp);
    reg_native(env, "pair?", native_pairp);
    reg_native(env, "=", native_eq);
    reg_native(env, "equal?", native_eq);
    reg_native(env, ">", native_gt);
    reg_native(env, "<", native_lt);
    reg_native(env, ">=", native_gte);
    reg_native(env, "<=", native_lte);
    reg_native(env, "not", native_not);
    reg_native(env, "str-trim", native_str_trim);
    reg_native(env, "str-contains?", native_str_contains);
    reg_native(env, "str-starts?", native_str_starts);
    reg_native(env, "str-upper", native_str_upper);
    reg_native(env, "str-lower", native_str_lower);
    reg_native(env, "str-split", native_str_split);
    reg_native(env, "keys", native_keys);
    reg_native(env, "take", native_take);
    reg_native(env, "sort", native_sort);
    reg_native(env, "length", native_length);
    reg_native(env, "append", native_append);
    reg_native(env, "format", native_format);
    reg_native(env, "read-file", native_read_file);
    reg_native(env, "dict", native_dict);
    reg_native(env, "get", native_get);
    reg_native(env, "put", native_put);
    reg_native(env, "parse-json", native_parse_json);
    reg_native(env, "to-json", native_to_json);
    reg_native(env, "extract-json", native_extract_json);
    reg_native(env, "remove-think", native_remove_think);
    reg_native(env, "regex-match", native_regex_match);
    reg_native(env, "regex-replace", native_regex_replace);
    reg_native(env, "strip", native_strip);
}

static ZyValue *apply_proc(ZyVM *vm, ZyProcedure *proc, int argc, ZyValue **argv) {
    if ((int)proc->param_count != argc && proc->param_count != 1) {
        snprintf(vm->last_error, sizeof vm->last_error,
                 "形参个数(%zu)和实参个数(%d)不匹配", proc->param_count, argc);
        return zy_nil();
    }
    ZyEnv *call_env = zy_env_new(proc->closure);
    if (proc->param_count == 1 && argc != 1) {
        ZyValue **items = malloc((size_t)argc * sizeof(ZyValue *));
        for (int i = 0; i < argc; i++) items[i] = zy_value_clone(argv[i]);
        ZyValue *rest = zy_list((size_t)argc, items);
        free(items);
        zy_env_define(call_env, proc->params[0], rest);
    } else {
        for (size_t i = 0; i < proc->param_count; i++)
            zy_env_define(call_env, proc->params[i], zy_value_clone(argv[i]));
    }
    ZyValue *r = zy_eval(vm, proc->body, call_env);
    zy_env_free(call_env);
    return r;
}

ZyValue *zy_apply(ZyVM *vm, ZyValue *fn, int argc, ZyValue **argv, ZyEnv *env) {
    if (!fn) return zy_nil();
    fn = zy_resolve_value(fn);
    if (!fn) return zy_nil();
    if (fn->type == ZY_NATIVE) return fn->as.native(vm, env, argc, argv);
    if (fn->type == ZY_PROC) return apply_proc(vm, fn->as.proc, argc, argv);
    snprintf(vm->last_error, sizeof vm->last_error, "值不可调用");
    return zy_nil();
}
