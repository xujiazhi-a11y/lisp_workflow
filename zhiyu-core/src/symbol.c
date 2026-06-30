#include "zhiyu/types.h"
#include <stdlib.h>
#include <string.h>

#define SYM_BUCKETS 1024

typedef struct SymEntry {
    char *name;
    ZyValue *val;
    struct SymEntry *next;
} SymEntry;

static SymEntry *buckets[SYM_BUCKETS];

static unsigned hash_str(const char *s) {
    unsigned h = 5381;
    for (; *s; s++) h = ((h << 5) + h) + (unsigned char)*s;
    return h % SYM_BUCKETS;
}

ZyValue *zy_intern_symbol(const char *name) {
    if (!name) name = "";
    unsigned h = hash_str(name);
    for (SymEntry *e = buckets[h]; e; e = e->next) {
        if (strcmp(e->name, name) == 0)
            return e->val;
    }
    SymEntry *ent = malloc(sizeof(SymEntry));
    ZyValue *v = calloc(1, sizeof(ZyValue));
    if (!ent || !v) {
        free(ent);
        free(v);
        return NULL;
    }
    ent->name = strdup(name);
    v->type = ZY_SYM;
    v->as.str = ent->name;
    ent->val = v;
    ent->next = buckets[h];
    buckets[h] = ent;
    return v;
}
