#include "zhiyu/internal.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *p;
    char *err;
    size_t errcap;
} JsonCtx;

static void jerr(JsonCtx *c, const char *msg) {
    if (c->err && c->errcap > 0 && c->err[0] == '\0')
        snprintf(c->err, c->errcap, "%s", msg);
}

static void skip_ws(JsonCtx *c) {
    while (*c->p && isspace((unsigned char)*c->p)) c->p++;
}

static ZyValue *parse_value(JsonCtx *c);

static char *parse_string_raw(JsonCtx *c) {
    if (*c->p != '"') { jerr(c, "JSON 需要字符串"); return NULL; }
    c->p++;
    size_t cap = 64, len = 0;
    char *buf = malloc(cap);
    while (*c->p && *c->p != '"') {
        char ch = *c->p++;
        if (ch == '\\') {
            ch = *c->p ? *c->p++ : '\0';
            if (ch == 'n') ch = '\n';
            else if (ch == 't') ch = '\t';
            else if (ch == 'r') ch = '\r';
        }
        if (len + 2 > cap) { cap *= 2; buf = realloc(buf, cap); }
        buf[len++] = ch;
    }
    if (*c->p == '"') c->p++;
    buf[len] = '\0';
    return buf;
}

static ZyValue *parse_string(JsonCtx *c) {
    char *s = parse_string_raw(c);
    if (!s) return zy_nil();
    ZyValue *v = zy_str_copy(s);
    free(s);
    return v;
}

static ZyValue *parse_number(JsonCtx *c) {
    char *end;
    if (*c->p == '-' || isdigit((unsigned char)*c->p)) {
        long long i = strtoll(c->p, &end, 10);
        if (end > c->p) {
            if (*end == '.' || *end == 'e' || *end == 'E') {
                double f = strtod(c->p, &end);
                c->p = end;
                return zy_float(f);
            }
            c->p = end;
            return zy_int(i);
        }
    }
    jerr(c, "JSON 数字无效");
    return zy_nil();
}

static ZyValue *parse_array(JsonCtx *c) {
    if (*c->p != '[') return zy_nil();
    c->p++;
    skip_ws(c);
    ZyValue **items = NULL;
    size_t count = 0, cap = 0;
    if (*c->p == ']') { c->p++; return zy_list(0, NULL); }
    for (;;) {
        ZyValue *v = parse_value(c);
        if (count >= cap) {
            cap = cap ? cap * 2 : 4;
            items = realloc(items, cap * sizeof(ZyValue *));
        }
        items[count++] = v;
        skip_ws(c);
        if (*c->p == ']') { c->p++; break; }
        if (*c->p != ',') { jerr(c, "JSON 数组格式错误"); break; }
        c->p++;
        skip_ws(c);
    }
    ZyValue *r = zy_list(count, items);
    free(items);
    return r;
}

static ZyValue *parse_object(JsonCtx *c) {
    if (*c->p != '{') return zy_nil();
    c->p++;
    skip_ws(c);
    ZyValue **keys = NULL, **vals = NULL;
    size_t count = 0, cap = 0;
    if (*c->p == '}') { c->p++; return zy_dict(0, NULL, NULL); }
    for (;;) {
        skip_ws(c);
        char *k = parse_string_raw(c);
        if (!k) break;
        ZyValue *key = zy_str_copy(k);
        free(k);
        skip_ws(c);
        if (*c->p != ':') { jerr(c, "JSON 对象需要冒号"); zy_release(key); break; }
        c->p++;
        skip_ws(c);
        ZyValue *val = parse_value(c);
        if (count >= cap) {
            cap = cap ? cap * 2 : 4;
            keys = realloc(keys, cap * sizeof(ZyValue *));
            vals = realloc(vals, cap * sizeof(ZyValue *));
        }
        keys[count] = key;
        vals[count] = val;
        count++;
        skip_ws(c);
        if (*c->p == '}') { c->p++; break; }
        if (*c->p != ',') { jerr(c, "JSON 对象格式错误"); break; }
        c->p++;
    }
    ZyValue *r = zy_dict(count, keys, vals);
    free(keys);
    free(vals);
    return r;
}

static ZyValue *parse_value(JsonCtx *c) {
    skip_ws(c);
    if (*c->p == '"') return parse_string(c);
    if (*c->p == '[') return parse_array(c);
    if (*c->p == '{') return parse_object(c);
    if (strncmp(c->p, "true", 4) == 0) { c->p += 4; return zy_bool(true); }
    if (strncmp(c->p, "false", 5) == 0) { c->p += 5; return zy_bool(false); }
    if (strncmp(c->p, "null", 4) == 0) { c->p += 4; return zy_nil(); }
    return parse_number(c);
}

ZyValue *zy_json_parse(const char *text, char *err, size_t errcap) {
    if (!text) return zy_nil();
    JsonCtx ctx = { text, err, errcap };
    ZyValue *v = parse_value(&ctx);
    skip_ws(&ctx);
    if (ctx.err && ctx.err[0]) return zy_nil();
    return v;
}

static void append_str(char **buf, size_t *len, size_t *cap, const char *s) {
    size_t sl = strlen(s);
    if (*len + sl + 1 > *cap) {
        *cap = (*cap + sl + 64) * 2;
        *buf = realloc(*buf, *cap);
    }
    memcpy(*buf + *len, s, sl);
    *len += sl;
    (*buf)[*len] = '\0';
}

static void escape_str(char **buf, size_t *len, size_t *cap, const char *s) {
    append_str(buf, len, cap, "\"");
    for (const char *p = s; *p; p++) {
        if (*p == '"' || *p == '\\') {
            char tmp[3] = { '\\', *p, '\0' };
            append_str(buf, len, cap, tmp);
        } else if (*p == '\n') append_str(buf, len, cap, "\\n");
        else {
            char tmp[2] = { *p, '\0' };
            append_str(buf, len, cap, tmp);
        }
    }
    append_str(buf, len, cap, "\"");
}

static void stringify_val(ZyValue *v, char **buf, size_t *len, size_t *cap);

static void stringify_dict(struct ZyDict *d, char **buf, size_t *len, size_t *cap) {
    append_str(buf, len, cap, "{");
    for (size_t i = 0; i < d->count; i++) {
        if (i) append_str(buf, len, cap, ",");
        const char *k = zy_value_to_cstr(d->keys[i]);
        escape_str(buf, len, cap, k);
        append_str(buf, len, cap, ":");
        stringify_val(d->vals[i], buf, len, cap);
    }
    append_str(buf, len, cap, "}");
}

static void stringify_val(ZyValue *v, char **buf, size_t *len, size_t *cap) {
    if (!v || v->type == ZY_NIL) { append_str(buf, len, cap, "null"); return; }
    switch (v->type) {
    case ZY_BOOL:
        append_str(buf, len, cap, v->as.b ? "true" : "false");
        break;
    case ZY_INT: {
        char tmp[32];
        snprintf(tmp, sizeof tmp, "%lld", v->as.i);
        append_str(buf, len, cap, tmp);
        break;
    }
    case ZY_FLOAT: {
        char tmp[32];
        snprintf(tmp, sizeof tmp, "%g", v->as.f);
        append_str(buf, len, cap, tmp);
        break;
    }
    case ZY_STR:
        escape_str(buf, len, cap, v->as.str ? v->as.str : "");
        break;
    case ZY_LIST:
        append_str(buf, len, cap, "[");
        for (size_t i = 0; i < v->as.list.count; i++) {
            if (i) append_str(buf, len, cap, ",");
            stringify_val(v->as.list.items[i], buf, len, cap);
        }
        append_str(buf, len, cap, "]");
        break;
    case ZY_DICT:
        if (v->as.dict) stringify_dict(v->as.dict, buf, len, cap);
        else append_str(buf, len, cap, "{}");
        break;
    default: {
        char *s = zy_to_string(v);
        escape_str(buf, len, cap, s);
        free(s);
        break;
    }
    }
}

char *zy_json_stringify(ZyValue *v) {
    char *buf = NULL;
    size_t len = 0, cap = 0;
    stringify_val(v, &buf, &len, &cap);
    return buf ? buf : strdup("null");
}

static const char *find_json_start(const char *text) {
    for (const char *p = text; *p; p++) {
        if (*p == '[' || *p == '{') return p;
    }
    return NULL;
}

static int match_bracket(const char *start) {
    char open = start[0];
    char close = open == '[' ? ']' : '}';
    int depth = 0;
    int in_str = 0;
    for (const char *p = start; *p; p++) {
        if (*p == '"' && (p == start || p[-1] != '\\')) in_str = !in_str;
        if (in_str) continue;
        if (*p == open) depth++;
        else if (*p == close) {
            depth--;
            if (depth == 0) return (int)(p - start + 1);
        }
    }
    return -1;
}

ZyValue *zy_json_extract(const char *text, ZyValue *default_val) {
    if (!text) return default_val ? zy_value_clone(default_val) : zy_nil();
    const char *start = find_json_start(text);
    if (!start) return default_val ? zy_value_clone(default_val) : zy_nil();
    int len = match_bracket(start);
    if (len <= 0) return default_val ? zy_value_clone(default_val) : zy_nil();
    char *slice = malloc((size_t)len + 1);
    memcpy(slice, start, (size_t)len);
    slice[len] = '\0';
    char err[128] = {0};
    ZyValue *v = zy_json_parse(slice, err, sizeof err);
    free(slice);
    if (err[0] || !v) return default_val ? zy_value_clone(default_val) : zy_nil();
    return v;
}
