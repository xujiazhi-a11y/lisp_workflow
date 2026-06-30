#ifndef ZHIYU_TYPES_H
#define ZHIYU_TYPES_H

#include <stdbool.h>
#include <stddef.h>

typedef struct ZyEnv ZyEnv;
typedef struct ZyValue ZyValue;
typedef struct ZyProcedure ZyProcedure;
typedef struct ZyMacro ZyMacro;
typedef struct ZyVM ZyVM;

typedef enum {
    ZY_NIL,
    ZY_BOOL,
    ZY_INT,
    ZY_FLOAT,
    ZY_STR,
    ZY_SYM,
    ZY_LIST,
    ZY_DICT,
    ZY_NATIVE,
    ZY_PROC,
    ZY_SLOT
} ZyType;

typedef ZyValue *(*ZyNativeFn)(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv);

struct ZyDict {
    ZyValue **keys;
    ZyValue **vals;
    size_t count;
};

struct ZyValue {
    ZyType type;
    union {
        bool b;
        long long i;
        double f;
        char *str;
        struct {
            ZyValue **items;
            size_t count;
        } list;
        struct ZyDict *dict;
        ZyNativeFn native;
        ZyProcedure *proc;
        struct ZySlot *slot;
    } as;
};

struct ZyProcedure {
    ZyValue **params;
    size_t param_count;
    ZyValue *body;
    ZyEnv *closure;
};

struct ZySlot {
    ZyValue *value;
};

struct ZyMacro {
    ZyValue *name;
    ZyValue **params;
    size_t param_count;
    ZyValue *tmpl;
    int rest_param;
};

#endif
