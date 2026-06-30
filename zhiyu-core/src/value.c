#include "zhiyu/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

void zy_release(ZyValue *v);

static ZyValue *slot_get_inner(ZyValue *slot) {
    if (!slot || slot->type != ZY_SLOT || !slot->as.slot) return NULL;
    return slot->as.slot->value;
}

static void free_value_inner(ZyValue *v) {
    if (!v) return;
    switch (v->type) {
    case ZY_STR:
        free(v->as.str);
        break;
    case ZY_LIST:
        for (size_t i = 0; i < v->as.list.count; i++)
            zy_release(v->as.list.items[i]);
        free(v->as.list.items);
        break;
    case ZY_DICT:
        if (v->as.dict) {
            for (size_t i = 0; i < v->as.dict->count; i++) {
                zy_release(v->as.dict->keys[i]);
                zy_release(v->as.dict->vals[i]);
            }
            free(v->as.dict->keys);
            free(v->as.dict->vals);
            free(v->as.dict);
        }
        break;
    case ZY_PROC:
        for (size_t i = 0; i < v->as.proc->param_count; i++)
            zy_release(v->as.proc->params[i]);
        free(v->as.proc->params);
        zy_release(v->as.proc->body);
        /* closure env owned by procedure lifetime */
        free(v->as.proc);
        break;
    case ZY_SLOT:
        if (v->as.slot) {
            zy_release(v->as.slot->value);
            free(v->as.slot);
        }
        break;
    default:
        break;
    }
    free(v);
}

static ZyValue *alloc_value(ZyType t) {
    ZyValue *v = calloc(1, sizeof(ZyValue));
    if (!v) return NULL;
    v->type = t;
    return v;
}

static ZyValue THE_NIL;
static ZyValue THE_TRUE;
static ZyValue THE_FALSE;
static int atoms_inited = 0;

static void init_atoms(void) {
    if (atoms_inited) return;
    THE_NIL.type = ZY_NIL;
    THE_TRUE.type = ZY_BOOL;
    THE_TRUE.as.b = true;
    THE_FALSE.type = ZY_BOOL;
    THE_FALSE.as.b = false;
    atoms_inited = 1;
}

ZyValue *zy_nil(void) {
    init_atoms();
    return &THE_NIL;
}

ZyValue *zy_bool(bool v) {
    init_atoms();
    return v ? &THE_TRUE : &THE_FALSE;
}

ZyValue *zy_int(long long v) {
    ZyValue *z = alloc_value(ZY_INT);
    if (z) z->as.i = v;
    return z;
}

ZyValue *zy_float(double v) {
    ZyValue *z = alloc_value(ZY_FLOAT);
    if (z) z->as.f = v;
    return z;
}

ZyValue *zy_str_copy(const char *s) {
    ZyValue *z = alloc_value(ZY_STR);
    if (!z) return NULL;
    z->as.str = s ? strdup(s) : strdup("");
    return z;
}

ZyValue *zy_list(size_t n, ZyValue **items) {
    ZyValue *z = alloc_value(ZY_LIST);
    if (!z) return NULL;
    z->as.list.count = n;
    z->as.list.items = calloc(n, sizeof(ZyValue *));
    if (!z->as.list.items) {
        free(z);
        return NULL;
    }
    for (size_t i = 0; i < n; i++)
        z->as.list.items[i] = items[i];
    return z;
}

ZyValue *zy_dict(size_t n, ZyValue **keys, ZyValue **vals) {
    ZyValue *z = alloc_value(ZY_DICT);
    if (!z) return NULL;
    z->as.dict = calloc(1, sizeof(struct ZyDict));
    if (!z->as.dict) { free(z); return NULL; }
    z->as.dict->count = n;
    if (n > 0) {
        z->as.dict->keys = calloc(n, sizeof(ZyValue *));
        z->as.dict->vals = calloc(n, sizeof(ZyValue *));
        for (size_t i = 0; i < n; i++) {
            z->as.dict->keys[i] = keys[i];
            z->as.dict->vals[i] = vals[i];
        }
    }
    return z;
}

ZyValue *zy_slot(ZyValue *val);

ZyValue *zy_value_clone(ZyValue *v) {
    if (!v || v->type == ZY_NIL) return zy_nil();
    if (v->type == ZY_SYM) return v;
    if (v->type == ZY_BOOL) return zy_bool(v->as.b);
    if (v->type == ZY_INT) return zy_int(v->as.i);
    if (v->type == ZY_FLOAT) return zy_float(v->as.f);
    if (v->type == ZY_STR) return zy_str_copy(v->as.str);
    if (v->type == ZY_NATIVE || v->type == ZY_PROC) return v;
    if (v->type == ZY_SLOT) {
        ZyValue *inner = slot_get_inner(v);
        return zy_slot(inner ? zy_value_clone(inner) : zy_nil());
    }
    if (v->type == ZY_LIST) {
        ZyValue **items = malloc(v->as.list.count * sizeof(ZyValue *));
        for (size_t i = 0; i < v->as.list.count; i++)
            items[i] = zy_value_clone(v->as.list.items[i]);
        ZyValue *r = zy_list(v->as.list.count, items);
        free(items);
        return r;
    }
    if (v->type == ZY_DICT && v->as.dict) {
        ZyValue **k = malloc(v->as.dict->count * sizeof(ZyValue *));
        ZyValue **val = malloc(v->as.dict->count * sizeof(ZyValue *));
        for (size_t i = 0; i < v->as.dict->count; i++) {
            k[i] = zy_value_clone(v->as.dict->keys[i]);
            val[i] = zy_value_clone(v->as.dict->vals[i]);
        }
        ZyValue *r = zy_dict(v->as.dict->count, k, val);
        free(k); free(val);
        return r;
    }
    return zy_nil();
}

const char *zy_sym_cstr(ZyValue *sym) {
    if (!sym || sym->type != ZY_SYM) return "";
    return sym->as.str ? sym->as.str : "";
}

const char *zy_value_to_cstr(ZyValue *v) {
    if (!v) return "";
    if (v->type == ZY_STR) return v->as.str ? v->as.str : "";
    if (v->type == ZY_SYM) return zy_sym_cstr(v);
    return "";
}

ZyValue *zy_retain(ZyValue *v) {
    (void)v;
    return v;
}

void zy_release(ZyValue *v) {
    if (!v || v == &THE_NIL || v == &THE_TRUE || v == &THE_FALSE) return;
    if (v->type == ZY_SYM || v->type == ZY_NATIVE || v->type == ZY_PROC) return;
    free_value_inner(v);
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

static void append_dict_str(char **buf, size_t *len, size_t *cap, ZyValue *v);
char *zy_to_string(ZyValue *v);

static void append_dict_val(char **buf, size_t *len, size_t *cap, ZyValue *v) {
    if (!v || v->type == ZY_NIL) {
        append_str(buf, len, cap, "()");
        return;
    }
    if (v->type == ZY_DICT && v->as.dict) {
        append_dict_str(buf, len, cap, v);
        return;
    }
    char *part = zy_to_string(v);
    append_str(buf, len, cap, part);
    free(part);
}

static void append_dict_str(char **buf, size_t *len, size_t *cap, ZyValue *v) {
    struct ZyDict *d = v->as.dict;
    append_str(buf, len, cap, "{");
    for (size_t i = 0; i < d->count; i++) {
        if (i) append_str(buf, len, cap, " ");
        const char *k = zy_value_to_cstr(d->keys[i]);
        append_str(buf, len, cap, "\"");
        append_str(buf, len, cap, k ? k : "");
        append_str(buf, len, cap, "\"");
        append_str(buf, len, cap, ":");
        append_dict_val(buf, len, cap, d->vals[i]);
    }
    append_str(buf, len, cap, "}");
}

char *zy_to_string(ZyValue *v) {
    char *buf = NULL;
    size_t len = 0, cap = 0;
    if (!v || v->type == ZY_NIL) {
        return strdup("()");
    }
    switch (v->type) {
    case ZY_BOOL:
        append_str(&buf, &len, &cap, v->as.b ? "#t" : "#f");
        break;
    case ZY_INT: {
        char tmp[32];
        snprintf(tmp, sizeof tmp, "%lld", v->as.i);
        append_str(&buf, &len, &cap, tmp);
        break;
    }
    case ZY_FLOAT: {
        char tmp[32];
        snprintf(tmp, sizeof tmp, "%g", v->as.f);
        append_str(&buf, &len, &cap, tmp);
        break;
    }
    case ZY_STR: {
        append_str(&buf, &len, &cap, "\"");
        append_str(&buf, &len, &cap, v->as.str ? v->as.str : "");
        append_str(&buf, &len, &cap, "\"");
        break;
    }
    case ZY_SYM:
        append_str(&buf, &len, &cap, zy_sym_cstr(v));
        break;
    case ZY_LIST:
        append_str(&buf, &len, &cap, "(");
        for (size_t i = 0; i < v->as.list.count; i++) {
            if (i) append_str(&buf, &len, &cap, " ");
            char *part = zy_to_string(v->as.list.items[i]);
            append_str(&buf, &len, &cap, part);
            free(part);
        }
        append_str(&buf, &len, &cap, ")");
        break;
    case ZY_DICT:
        if (v->as.dict) append_dict_str(&buf, &len, &cap, v);
        else append_str(&buf, &len, &cap, "{}");
        break;
    case ZY_NATIVE:
        append_str(&buf, &len, &cap, "#<native>");
        break;
    case ZY_PROC:
        append_str(&buf, &len, &cap, "#<procedure>");
        break;
    case ZY_SLOT:
        append_str(&buf, &len, &cap, "#<slot>");
        break;
    default:
        append_str(&buf, &len, &cap, "#<unknown>");
        break;
    }
    return buf ? buf : strdup("");
}

void zy_print_value(ZyValue *v) {
    char *s = zy_to_string(v);
    fputs(s, stdout);
    free(s);
}

/* forward for symbol intern */
ZyValue *zy_intern_symbol(const char *name);

ZyValue *zy_symbol(const char *name) {
    return zy_intern_symbol(name);
}

ZyValue *zy_native(ZyNativeFn fn) {
    ZyValue *z = alloc_value(ZY_NATIVE);
    if (z) z->as.native = fn;
    return z;
}

ZyValue *zy_procedure(ZyProcedure *proc) {
    ZyValue *z = alloc_value(ZY_PROC);
    if (z) z->as.proc = proc;
    return z;
}

ZyValue *zy_slot(ZyValue *val) {
    ZyValue *z = alloc_value(ZY_SLOT);
    if (!z) return NULL;
    z->as.slot = calloc(1, sizeof(struct ZySlot));
    if (!z->as.slot) {
        free(z);
        return NULL;
    }
    z->as.slot->value = val ? val : zy_nil();
    return z;
}

ZyValue *zy_slot_get(ZyValue *slot) {
    ZyValue *v = slot_get_inner(slot);
    return v ? v : zy_nil();
}

void zy_slot_set(ZyValue *slot, ZyValue *val) {
    if (!slot || slot->type != ZY_SLOT || !slot->as.slot) return;
    zy_release(slot->as.slot->value);
    slot->as.slot->value = val ? val : zy_nil();
}

ZyValue *zy_resolve_value(ZyValue *v) {
    if (v && v->type == ZY_SLOT) return zy_slot_get(v);
    return v;
}

int zy_truthy(ZyValue *v) {
    if (!v || v->type == ZY_NIL) return 0;
    if (v->type == ZY_BOOL) return v->as.b ? 1 : 0;
    return 1;
}

int zy_is_keyword_sym(ZyValue *v) {
    if (!v || v->type != ZY_SYM) return 0;
    const char *s = zy_sym_cstr(v);
    return s[0] == ':' && s[1] != '\0';
}

int zy_list_length(ZyValue *v) {
    if (!v || v->type != ZY_LIST) return 0;
    return (int)v->as.list.count;
}

ZyValue *zy_list_ref(ZyValue *v, size_t i) {
    if (!v || v->type != ZY_LIST || i >= v->as.list.count) return zy_nil();
    return v->as.list.items[i];
}
