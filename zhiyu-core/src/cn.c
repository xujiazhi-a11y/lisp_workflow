#include "zhiyu/internal.h"
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *cn;
    const char *en;
} CnAlias;

static const CnAlias CN_ALIASES[] = {
    {"打印", "print"}, {"输出", "print"}, {"显示", "print"}, {"换行", "println"},
    {"格式化", "format"}, {"文本拼接", "str-concat"}, {"文本连接", "str-join"},
    {"文本裁剪", "str-trim"}, {"文本包含", "str-contains?"}, {"文本开头", "str-starts?"},
    {"文本结尾", "str-ends?"}, {"文本替换", "str-replace"}, {"文本分割", "str-split"},
    {"转文本", "str"},
    {"序列", "list"}, {"长度", "length"}, {"合并", "append"}, {"追加", "append"},
    {"反转", "reverse"}, {"前项", "car"}, {"前头的项", "car"}, {"第一项", "car"},
    {"后项", "cdr"}, {"后面的项", "cdr"}, {"序对", "cons"}, {"取项", "nth"},
    {"遍历", "each"}, {"批处理", "map"}, {"映射", "map"}, {"归约", "reduce"},
    {"顺序执行", "reduce"}, {"筛选", "filter"}, {"过滤", "filter"},
    {"为空?", "null?"}, {"到空值了?", "null?"},
    {"是列表?", "list?"}, {"是数字?", "number?"}, {"是文本?", "string?"},
    {"是质数?", "prime?"}, {"整除?", "divides?"}, {"偶数?", "even?"},
    {"与", "and"}, {"或", "or"}, {"非", "not"}, {"不", "not"},
    {"取余", "mod"}, {"取余数", "mod"},
    {"加", "+"}, {"减", "-"}, {"乘", "*"}, {"除", "/"},
    {"平方", "square"}, {"开方", "sqrt"}, {"幂", "expt"},
    {"取最小值", "min"}, {"取最大值", "max"}, {"取平均", "average"},
    {"读文件", "read-file"}, {"写文件", "write-file"},
    {"解析JSON", "parse-json"}, {"转JSON", "to-json"}, {"提取JSON", "extract-json"},
    {"去除思考", "remove-think"}, {"正则匹配", "regex-match"}, {"正则替换", "regex-replace"},
    {"去空白", "strip"},
    {"调用模型", "call-llm"},
    {"AI文本", "ai-text"}, {"AI图像", "ai-image"}, {"AI视频", "ai-video"},
    {"成对?", "pair?"}, {"是序对?", "pair?"},
    {"字典", "dict"}, {"取值", "get"}, {"赋值", "put"},
    {"键集", "keys"}, {"值集", "values"},
    {"排序", "sort"}, {"包含?", "member?"}, {"转数字", "to-number"},
    {"大写", "str-upper"}, {"小写", "str-lower"}, {"取前", "take"},
    {"发送飞书", "send-to-feishu"},     {"搜索种子", "torrent-search"},
    {"构建搜索词", "build-search-term"},
    {"发送搜索进度", "search-progress"}, {"发送种子结果", "emit-torrent-results"},
    {"发送推荐", "emit-recommendations"}, {"读取历史", "load-history"},
    {"保存历史", "save-history"}, {"输入", "input"}, {"用户输入", "user-input"},
    {"选择", "interact"},
    {"交互", "interact"},
    {"浏览器启动", "browser-start"}, {"浏览器打开", "browser-open"},
    {"浏览器关闭", "browser-close"}, {"页面查找", "page-find"},
    {"页面查找所有", "page-find-all"},
    {"元素填写", "elem-fill"}, {"元素点击", "elem-click"},
    {"页面执行", "page-exec"}, {"页面截图", "page-screenshot"},
    {"等待登录跳转", "page-wait-login"}, {"Excel读取", "excel-read"},
    {"格式化日期", "format-date"}, {"扫描页面元素", "page-scan"},
    {"点击元素", "page-click"}, {"点击文本", "page-click-text"},
    {"等待元素出现", "page-wait-selector"}, {"勾选", "page-check"},
    {"勾选文本", "page-click-checkbox"},
    {"等待秒数", "wait-seconds"},
    {NULL, NULL}
};

static const char *SPECIAL_FORMS[] = {
    "define", "定义",
    "lambda", "道", "规定",
    "if", "如果",
    "cond", "情况符合",
    "begin", "开始",
    "quote", "引",
    "set!", "！", "赋",
    "let", "令", "命",
    "and", "与",
    "or", "或",
    "load", "引入",
    "defmacro", "定义宏",
    "macroexpand", "宏展开",
    "pipe",
    "->",
    "map", "映射", "批处理",
    "reduce", "归约", "顺序执行",
    "filter", "过滤", "筛选",
    "each", "遍历",
    NULL
};

const char *zy_cn_resolve(const char *name) {
    for (int i = 0; CN_ALIASES[i].cn; i++)
        if (strcmp(CN_ALIASES[i].cn, name) == 0)
            return CN_ALIASES[i].en;
    return NULL;
}

const char *zy_special_form_key(const char *op) {
    for (int i = 0; SPECIAL_FORMS[i]; i++)
        if (strcmp(SPECIAL_FORMS[i], op) == 0)
            return SPECIAL_FORMS[i];
    return NULL;
}

static int sf_is(const char *op, const char *a, const char *b, const char *c) {
    if (strcmp(op, a) == 0) return 1;
    if (b && strcmp(op, b) == 0) return 1;
    if (c && strcmp(op, c) == 0) return 1;
    return 0;
}

int zy_sf_define(const char *op) { return sf_is(op, "define", "定义", NULL); }
int zy_sf_lambda(const char *op) { return sf_is(op, "lambda", "道", "规定"); }
int zy_sf_if(const char *op) { return sf_is(op, "if", "如果", NULL); }
int zy_sf_cond(const char *op) { return sf_is(op, "cond", "情况符合", NULL); }
int zy_sf_begin(const char *op) { return sf_is(op, "begin", "开始", NULL); }
int zy_sf_quote(const char *op) { return sf_is(op, "quote", "引", NULL); }
int zy_sf_set(const char *op) { return sf_is(op, "set!", "！", "赋"); }
int zy_sf_let(const char *op) { return sf_is(op, "let", "令", "命"); }
int zy_sf_and(const char *op) { return sf_is(op, "and", "与", NULL); }
int zy_sf_or(const char *op) { return sf_is(op, "or", "或", NULL); }
int zy_sf_load(const char *op) { return sf_is(op, "load", "引入", NULL); }
int zy_sf_defmacro(const char *op) { return sf_is(op, "defmacro", "定义宏", NULL); }
int zy_sf_macroexpand(const char *op) { return sf_is(op, "macroexpand", "宏展开", NULL); }
int zy_sf_pipe(const char *op) { return strcmp(op, "pipe") == 0; }
int zy_sf_arrow(const char *op) { return strcmp(op, "->") == 0; }
int zy_sf_map(const char *op) { return sf_is(op, "map", "映射", "批处理"); }
int zy_sf_reduce(const char *op) { return sf_is(op, "reduce", "归约", "顺序执行"); }
int zy_sf_filter(const char *op) { return sf_is(op, "filter", "过滤", "筛选"); }
int zy_sf_each(const char *op) { return sf_is(op, "each", "遍历", NULL); }
