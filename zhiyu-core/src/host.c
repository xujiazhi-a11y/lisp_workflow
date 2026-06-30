#include "zhiyu/host.h"
#include "zhiyu/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static ZyValue *call_llm_mock(int argc, ZyValue **argv) {
    const char *prompt = argc > 0 ? zy_value_to_cstr(argv[0]) : "";
    char *resp;
    if (strstr(prompt, "撰写正文") || strstr(prompt, "撰写本章节") ||
        strstr(prompt, "只输出正文") || strstr(prompt, "扩写")) {
        resp = strdup("这是模拟生成的章节正文内容，阐述本章核心观点与案例。");
    } else if (strstr(prompt, "情感") || strstr(prompt, "positive") || strstr(prompt, "negative") ||
               strstr(prompt, "正向") || strstr(prompt, "负向")) {
        if (strstr(prompt, "非常好") || strstr(prompt, "顺手") || strstr(prompt, "很棒"))
            resp = strdup("positive");
        else
            resp = strdup("negative");
    } else if (strstr(prompt, "分类") || strstr(prompt, "问题类型") || strstr(prompt, "物流") ||
               strstr(prompt, "质量")) {
        if (strstr(prompt, "包装") || strstr(prompt, "摔坏") || strstr(prompt, "损坏"))
            resp = strdup("质量差");
        else if (strstr(prompt, "一周") || strstr(prompt, "物流太慢") || strstr(prompt, "物流"))
            resp = strdup("物流慢");
        else
            resp = strdup("其它");
    } else if (strstr(prompt, "chapter") || strstr(prompt, "subchapter") ||
               strstr(prompt, "输出示例")) {
        resp = strdup("[{\"chapter\":\"得失的故事\",\"subchapter\":[\"1.1 概述\",\"1.2 案例\"]},{\"chapter\":\"困境的故事\",\"subchapter\":[\"2.1 概述\",\"2.2 案例\"]},{\"chapter\":\"选择的故事\",\"subchapter\":[\"3.1 概述\",\"3.2 案例\"]}]");
    } else if (strstr(prompt, "大纲") || strstr(prompt, "翻译")) {
        resp = strdup("测试片名|Test Movie");
    } else {
        resp = strdup("[\"第一章：Lisp简介\",\"第二章：函数定义\",\"第三章：宏\"]");
    }
    ZyValue *r = zy_str_copy(resp);
    free(resp);
    return r;
}

void zy_vm_set_host(ZyVM *vm, ZyHostCallbacks *host) {
    if (!vm) return;
    vm->host = host;
}

ZyHostCallbacks *zy_vm_host(ZyVM *vm) {
    return vm ? vm->host : NULL;
}

char *zy_values_to_json_array(int argc, ZyValue **argv) {
    ZyValue **items = NULL;
    if (argc > 0) {
        items = malloc((size_t)argc * sizeof(ZyValue *));
        for (int i = 0; i < argc; i++)
            items[i] = zy_value_clone(argv[i]);
    }
    ZyValue *lst = zy_list((size_t)argc, items);
    free(items);
    char *json = zy_json_stringify(lst);
    zy_release(lst);
    return json;
}

ZyValue *zy_value_from_json(const char *json) {
    if (!json) return zy_nil();
    char err[128] = {0};
    ZyValue *v = zy_json_parse(json, err, sizeof err);
    if (err[0] || !v) return zy_nil();
    return v;
}

ZyValue *zy_host_ffi_call(ZyVM *vm, const char *name, int argc, ZyValue **argv) {
    if (!vm || !name) return zy_nil();
    if (vm->host && vm->host->ffi_fn) {
        char *args_json = zy_values_to_json_array(argc, argv);
        char *result_json = vm->host->ffi_fn(vm->host->userdata, name, args_json);
        free(args_json);
        if (!result_json) return zy_nil();
        ZyValue *v = zy_value_from_json(result_json);
        free(result_json);
        return v ? v : zy_nil();
    }
    if (strcmp(name, "call-llm") == 0 || strcmp(name, "llm") == 0)
        return call_llm_mock(argc, argv);
    if (strcmp(name, "input") == 0 || strcmp(name, "user-input") == 0)
        return zy_str_copy("");
    if (strcmp(name, "send-to-feishu") == 0)
        return zy_str_copy("飞书消息发送成功（离线模式）");
    snprintf(vm->last_error, sizeof vm->last_error,
             "宿主 FFI 未连接：%s", name);
    return zy_nil();
}

static ZyValue *native_host_input(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)env;
    const char *prompt = argc > 0 ? zy_value_to_cstr(argv[0]) : "";
    if (vm->host && vm->host->input_fn) {
        char *r = vm->host->input_fn(vm->host->userdata, prompt);
        ZyValue *v = zy_str_copy(r ? r : "");
        free(r);
        return v;
    }
    return zy_str_copy("");
}

static ZyValue *native_host_interact(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) {
    (void)env;
    const char *prompt = argc > 0 ? zy_value_to_cstr(argv[0]) : "";
    char *options_json = NULL;
    if (argc >= 2) {
        options_json = zy_json_stringify(argv[1]);
    } else {
        options_json = strdup("[]");
    }
    if (vm->host && vm->host->interact_fn) {
        char *r = vm->host->interact_fn(vm->host->userdata, prompt, options_json);
        free(options_json);
        ZyValue *v = zy_str_copy(r ? r : "");
        free(r);
        return v;
    }
    free(options_json);
    return zy_str_copy("");
}

#define FFI_NATIVE(nm, id) \
    static ZyValue *ffi_##id(ZyVM *vm, ZyEnv *env, int argc, ZyValue **argv) { \
        (void)env; \
        return zy_host_ffi_call(vm, nm, argc, argv); \
    }

FFI_NATIVE("call-llm", call_llm)
FFI_NATIVE("llm", llm)
FFI_NATIVE("ai-text", ai_text)
FFI_NATIVE("ai-image", ai_image)
FFI_NATIVE("ai-video", ai_video)
FFI_NATIVE("video-concat", video_concat)
FFI_NATIVE("slideshow-video", slideshow_video)
FFI_NATIVE("torrent-search", torrent_search)
FFI_NATIVE("torrent-guess-en", torrent_guess_en)
FFI_NATIVE("build-search-term", build_search_term)
FFI_NATIVE("search-progress", search_progress)
FFI_NATIVE("emit-torrent-results", emit_torrent_results)
FFI_NATIVE("emit-recommendations", emit_recommendations)
FFI_NATIVE("load-history", load_history)
FFI_NATIVE("save-history", save_history)
FFI_NATIVE("wait-seconds", wait_seconds)
FFI_NATIVE("send-to-feishu", send_to_feishu)
FFI_NATIVE("browser-start", browser_start)
FFI_NATIVE("browser-open", browser_open)
FFI_NATIVE("browser-close", browser_close)
FFI_NATIVE("page-find", page_find)
FFI_NATIVE("page-find-all", page_find_all)
FFI_NATIVE("elem-fill", elem_fill)
FFI_NATIVE("elem-click", elem_click)
FFI_NATIVE("page-exec", page_exec)
FFI_NATIVE("page-screenshot", page_screenshot)
FFI_NATIVE("page-scan", page_scan)
FFI_NATIVE("page-wait-login", page_wait_login)
FFI_NATIVE("page-click", page_click)
FFI_NATIVE("page-click-text", page_click_text)
FFI_NATIVE("page-wait-selector", page_wait_selector)
FFI_NATIVE("page-check", page_check)
FFI_NATIVE("page-click-checkbox", page_click_checkbox)
FFI_NATIVE("user-input", user_input)
FFI_NATIVE("excel-read", excel_read)
FFI_NATIVE("format-date", format_date)

#undef FFI_NATIVE

static void reg_native(ZyEnv *env, const char *name, ZyNativeFn fn) {
    zy_env_define(env, zy_intern_symbol(name), zy_native(fn));
}

void zy_register_tier2_builtins(ZyEnv *env) {
    reg_native(env, "input", native_host_input);
    reg_native(env, "user-input", native_host_input);
    reg_native(env, "interact", native_host_interact);
    reg_native(env, "call-llm", ffi_call_llm);
    reg_native(env, "llm", ffi_llm);
    reg_native(env, "ai-text", ffi_ai_text);
    reg_native(env, "ai-image", ffi_ai_image);
    reg_native(env, "ai-video", ffi_ai_video);
    reg_native(env, "video-concat", ffi_video_concat);
    reg_native(env, "slideshow-video", ffi_slideshow_video);
    reg_native(env, "torrent-search", ffi_torrent_search);
    reg_native(env, "torrent-guess-en", ffi_torrent_guess_en);
    reg_native(env, "build-search-term", ffi_build_search_term);
    reg_native(env, "search-progress", ffi_search_progress);
    reg_native(env, "emit-torrent-results", ffi_emit_torrent_results);
    reg_native(env, "emit-recommendations", ffi_emit_recommendations);
    reg_native(env, "load-history", ffi_load_history);
    reg_native(env, "save-history", ffi_save_history);
    reg_native(env, "wait-seconds", ffi_wait_seconds);
    reg_native(env, "send-to-feishu", ffi_send_to_feishu);
    reg_native(env, "browser-start", ffi_browser_start);
    reg_native(env, "browser-open", ffi_browser_open);
    reg_native(env, "browser-close", ffi_browser_close);
    reg_native(env, "page-find", ffi_page_find);
    reg_native(env, "page-find-all", ffi_page_find_all);
    reg_native(env, "elem-fill", ffi_elem_fill);
    reg_native(env, "elem-click", ffi_elem_click);
    reg_native(env, "page-exec", ffi_page_exec);
    reg_native(env, "page-screenshot", ffi_page_screenshot);
    reg_native(env, "page-scan", ffi_page_scan);
    reg_native(env, "page-wait-login", ffi_page_wait_login);
    reg_native(env, "page-click", ffi_page_click);
    reg_native(env, "page-click-text", ffi_page_click_text);
    reg_native(env, "page-wait-selector", ffi_page_wait_selector);
    reg_native(env, "page-check", ffi_page_check);
    reg_native(env, "page-click-checkbox", ffi_page_click_checkbox);
    reg_native(env, "excel-read", ffi_excel_read);
    reg_native(env, "format-date", ffi_format_date);
}
