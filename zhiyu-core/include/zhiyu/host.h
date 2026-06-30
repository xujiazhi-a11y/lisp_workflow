#ifndef ZHIYU_HOST_H
#define ZHIYU_HOST_H

#include "types.h"

typedef struct ZyHostCallbacks ZyHostCallbacks;

struct ZyHostCallbacks {
    void *userdata;
    void (*print_fn)(void *userdata, int markdown, const char *text);
    char *(*input_fn)(void *userdata, const char *prompt);
    char *(*interact_fn)(void *userdata, const char *prompt, const char *options_json);
    char *(*ffi_fn)(void *userdata, const char *name, const char *args_json);
    int (*stopped_fn)(void *userdata);
};

void zy_vm_set_host(ZyVM *vm, ZyHostCallbacks *host);
ZyHostCallbacks *zy_vm_host(ZyVM *vm);

ZyValue *zy_host_ffi_call(ZyVM *vm, const char *name, int argc, ZyValue **argv);
char *zy_values_to_json_array(int argc, ZyValue **argv);
ZyValue *zy_value_from_json(const char *json);

void zy_register_tier2_builtins(ZyEnv *env);
int zy_host_stdio_run(ZyVM *vm);

#endif
