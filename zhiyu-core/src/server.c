#include "zhiyu/host.h"
#include "zhiyu/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    ZyVM *vm;
    int stopped;
    int next_ffi_id;
} ServerCtx;

static void emit_escaped_line(const char *prefix, const char *text) {
    fputs(prefix, stdout);
    if (text) {
        for (const char *p = text; *p; p++) {
            if (*p == '\n')
                fputs("↎", stdout);
            else
                fputc(*p, stdout);
        }
    }
    fputc('\n', stdout);
    fflush(stdout);
}

static const char *dict_str(ZyValue *d, const char *key) {
    if (!d || d->type != ZY_DICT || !d->as.dict) return NULL;
    for (size_t i = 0; i < d->as.dict->count; i++) {
        ZyValue *k = d->as.dict->keys[i];
        const char *ks = zy_value_to_cstr(k);
        if (ks && strcmp(ks, key) == 0) {
            ZyValue *v = d->as.dict->vals[i];
            if (v && v->type == ZY_STR) return v->as.str;
            return zy_value_to_cstr(v);
        }
    }
    return NULL;
}

static ZyValue *dict_val(ZyValue *d, const char *key) {
    if (!d || d->type != ZY_DICT || !d->as.dict) return NULL;
    for (size_t i = 0; i < d->as.dict->count; i++) {
        ZyValue *k = d->as.dict->keys[i];
        const char *ks = zy_value_to_cstr(k);
        if (ks && strcmp(ks, key) == 0)
            return d->as.dict->vals[i];
    }
    return NULL;
}

static int ctx_stopped(void *userdata) {
    ServerCtx *ctx = userdata;
    return ctx && ctx->stopped;
}

static void ctx_print(void *userdata, int md, const char *text) {
    (void)userdata;
    emit_escaped_line(md ? "__MD__:" : "__TEXT__:", text);
}

static char *read_stdin_json_line(void) {
    char *line = NULL;
    size_t cap = 0;
    ssize_t n = getline(&line, &cap, stdin);
    if (n <= 0) {
        free(line);
        return NULL;
    }
    while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r'))
        line[--n] = '\0';
    return line;
}

static char *wait_host_response(const char *cmd, int id) {
    for (;;) {
        char *line = read_stdin_json_line();
        if (!line) return NULL;
        ZyValue *obj = zy_value_from_json(line);
        free(line);
        if (!obj || obj->type != ZY_DICT) {
            zy_release(obj);
            continue;
        }
        const char *c = dict_str(obj, "cmd");
        if (!c || strcmp(c, cmd) != 0) {
            if (c && strcmp(c, "stop") == 0) {
                zy_release(obj);
                return NULL;
            }
            zy_release(obj);
            continue;
        }
        if (id >= 0) {
            ZyValue *vid = dict_val(obj, "id");
            long long got = (vid && vid->type == ZY_INT) ? vid->as.i : -1;
            if (got != id) {
                zy_release(obj);
                continue;
            }
        }
        ZyValue *val = dict_val(obj, "value");
        char *result = val ? zy_json_stringify(val) : strdup("null");
        zy_release(obj);
        return result;
    }
}

static char *ctx_input(void *userdata, const char *prompt) {
    ServerCtx *ctx = userdata;
    if (ctx->stopped) return strdup("");
    emit_escaped_line("__INPUT__:", prompt ? prompt : "");
    char *resp = wait_host_response("input_resp", -1);
    if (!resp) {
        ctx->stopped = 1;
        return strdup("");
    }
    ZyValue *v = zy_value_from_json(resp);
    free(resp);
    char *out;
    if (v && v->type == ZY_STR)
        out = strdup(v->as.str ? v->as.str : "");
    else {
        char *s = v ? zy_to_string(v) : strdup("");
        out = s;
    }
    zy_release(v);
    return out;
}

static char *ctx_interact(void *userdata, const char *prompt, const char *options_json) {
    ServerCtx *ctx = userdata;
    if (ctx->stopped) return strdup("");
    ZyValue *opts = zy_value_from_json(options_json ? options_json : "[]");
    ZyValue *keys[] = { zy_str_copy("prompt"), zy_str_copy("options") };
    ZyValue *vals[] = { zy_str_copy(prompt ? prompt : ""), opts ? opts : zy_list(0, NULL) };
    ZyValue *dict = zy_dict(2, keys, vals);
    char *js = zy_json_stringify(dict);
    emit_escaped_line("__INTERACT__:", js);
    free(js);
    zy_release(dict);
    char *resp = wait_host_response("interact_resp", -1);
    if (!resp) {
        ctx->stopped = 1;
        return strdup("");
    }
    ZyValue *v = zy_value_from_json(resp);
    free(resp);
    char *out;
    if (v && v->type == ZY_STR)
        out = strdup(v->as.str ? v->as.str : "");
    else {
        char *s = v ? zy_to_string(v) : strdup("");
        out = s;
    }
    zy_release(v);
    return out;
}

static char *ctx_ffi(void *userdata, const char *name, const char *args_json) {
    ServerCtx *ctx = userdata;
    if (ctx->stopped) return NULL;
    int id = ctx->next_ffi_id++;
    char header[8192];
    snprintf(header, sizeof header, "{\"id\":%d,\"name\":\"%s\",\"args\":%s}",
             id, name ? name : "", args_json ? args_json : "[]");
    emit_escaped_line("__HOST_FFI__:", header);
    char *resp = wait_host_response("ffi_resp", id);
    if (!resp) {
        ctx->stopped = 1;
        return NULL;
    }
    return resp;
}

static void run_eval(ServerCtx *ctx, const char *code) {
    ZyVM *vm = ctx->vm;
    vm->last_error[0] = '\0';
    zy_reset_load_cache(vm);
    ZyValue *r = zy_eval_string(vm, code);
    if (vm->last_error[0]) {
        emit_escaped_line("__ERROR__:", vm->last_error);
        zy_release(r);
        return;
    }
    if (ctx->stopped) {
        fputs("__STOPPED__\n", stdout);
        fflush(stdout);
        zy_release(r);
        return;
    }
    if (r && r->type != ZY_NIL) {
        char *s = r->type == ZY_STR ? strdup(r->as.str) : zy_to_string(r);
        emit_escaped_line("__RESULT__:", s);
        free(s);
    }
    zy_release(r);
    fputs("__DONE__\n", stdout);
    fflush(stdout);
}

static void run_file(ServerCtx *ctx, const char *path) {
    ZyVM *vm = ctx->vm;
    vm->last_error[0] = '\0';
    zy_reset_load_cache(vm);
    ZyValue *r = zy_run_file(vm, path);
    if (vm->last_error[0]) {
        emit_escaped_line("__ERROR__:", vm->last_error);
        zy_release(r);
        return;
    }
    if (ctx->stopped) {
        fputs("__STOPPED__\n", stdout);
        fflush(stdout);
        zy_release(r);
        return;
    }
    if (r && r->type != ZY_NIL) {
        char *s = r->type == ZY_STR ? strdup(r->as.str) : zy_to_string(r);
        emit_escaped_line("__RESULT__:", s);
        free(s);
    }
    zy_release(r);
    fputs("__DONE__\n", stdout);
    fflush(stdout);
}

int zy_host_stdio_run(ZyVM *vm) {
    ServerCtx ctx = { .vm = vm, .stopped = 0, .next_ffi_id = 1 };
    ZyHostCallbacks host = {
        .userdata = &ctx,
        .print_fn = ctx_print,
        .input_fn = ctx_input,
        .interact_fn = ctx_interact,
        .ffi_fn = ctx_ffi,
        .stopped_fn = ctx_stopped,
    };
    zy_vm_set_host(vm, &host);

    for (;;) {
        char *line = read_stdin_json_line();
        if (!line) break;
        ZyValue *obj = zy_value_from_json(line);
        free(line);
        if (!obj || obj->type != ZY_DICT) {
            zy_release(obj);
            continue;
        }
        const char *cmd = dict_str(obj, "cmd");
        if (!cmd) {
            zy_release(obj);
            continue;
        }
        if (strcmp(cmd, "stop") == 0) {
            ctx.stopped = 1;
            zy_release(obj);
            fputs("__STOPPED__\n", stdout);
            fflush(stdout);
            break;
        }
        if (strcmp(cmd, "eval") == 0) {
            const char *code = dict_str(obj, "code");
            if (code) run_eval(&ctx, code);
        } else if (strcmp(cmd, "run") == 0) {
            const char *path = dict_str(obj, "path");
            if (path) run_file(&ctx, path);
        } else if (strcmp(cmd, "reload") == 0) {
            const char *path = dict_str(obj, "path");
            if (path) {
                vm->last_error[0] = '\0';
                zy_load_file(vm, path, vm->global, 1);
                if (vm->last_error[0])
                    emit_escaped_line("__ERROR__:", vm->last_error);
                else {
                    fputs("__RELOADED__\n", stdout);
                    fflush(stdout);
                }
            }
        } else if (strcmp(cmd, "ping") == 0) {
            fputs("__PONG__\n", stdout);
            fflush(stdout);
        }
        zy_release(obj);
    }
    zy_vm_set_host(vm, NULL);
    return 0;
}
