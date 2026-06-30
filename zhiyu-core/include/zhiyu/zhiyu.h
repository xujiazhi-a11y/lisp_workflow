#ifndef ZHIYU_H
#define ZHIYU_H

#include "types.h"

typedef struct {
    char *message;
    int line;
} ZyError;

struct ZyHostCallbacks;

struct ZyVM {
    ZyEnv *global;
    char *base_dir;
    int last_error_line;
    char last_error[512];
    struct ZyMacro *macros;
    size_t macro_count;
    size_t macro_cap;
    char **loaded_paths;
    size_t loaded_count;
    size_t loaded_cap;
    struct ZyHostCallbacks *host;
};

ZyVM *zy_vm_new(void);
void zy_vm_free(ZyVM *vm);

ZyValue *zy_eval_string(ZyVM *vm, const char *code);
ZyValue *zy_run_file(ZyVM *vm, const char *path);
void zy_set_base_dir(ZyVM *vm, const char *dir);
void zy_reset_load_cache(ZyVM *vm);

ZyValue *zy_nil(void);
ZyValue *zy_bool(bool v);
ZyValue *zy_int(long long v);
ZyValue *zy_float(double v);
ZyValue *zy_str_copy(const char *s);
ZyValue *zy_list(size_t n, ZyValue **items);
ZyValue *zy_dict(size_t n, ZyValue **keys, ZyValue **vals);
ZyValue *zy_slot(ZyValue *val);
ZyValue *zy_slot_get(ZyValue *slot);
void zy_slot_set(ZyValue *slot, ZyValue *val);
ZyValue *zy_resolve_value(ZyValue *v);
ZyValue *zy_retain(ZyValue *v);
void zy_release(ZyValue *v);

const char *zy_sym_cstr(ZyValue *sym);
const char *zy_value_to_cstr(ZyValue *v);
char *zy_to_string(ZyValue *v);
void zy_print_value(ZyValue *v);

#endif
