#include "zhiyu/internal.h"
#include <regex.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

char *zy_strip(const char *text) {
    if (!text) return strdup("");
    while (*text && isspace((unsigned char)*text)) text++;
    const char *end = text + strlen(text);
    while (end > text && isspace((unsigned char)end[-1])) end--;
    size_t n = (size_t)(end - text);
    char *r = malloc(n + 1);
    memcpy(r, text, n);
    r[n] = '\0';
    return r;
}

char *zy_remove_think(const char *text) {
    if (!text) return strdup("");
    const char *tags[] = {"think", "thinking", "thought", NULL};
    char *work = strdup(text);
    for (int t = 0; tags[t]; t++) {
        char open[64], close[64];
        snprintf(open, sizeof open, "<%s", tags[t]);
        snprintf(close, sizeof close, "</%s", tags[t]);
        for (;;) {
            char *start = strstr(work, open);
            if (!start) break;
            char *tag_end = strchr(start, '>');
            if (!tag_end) break;
            char close_tag[64];
            snprintf(close_tag, sizeof close_tag, "</%s>", tags[t]);
            char *end = strstr(tag_end + 1, close_tag);
            if (!end) break;
            end += strlen(close_tag);
            size_t prefix = (size_t)(start - work);
            size_t suffix = strlen(end);
            char *n = malloc(prefix + suffix + 1);
            memcpy(n, work, prefix);
            memcpy(n + prefix, end, suffix + 1);
            free(work);
            work = n;
        }
    }
    char *trimmed = zy_strip(work);
    free(work);
    return trimmed;
}

char *zy_regex_match(const char *pattern, const char *text) {
    if (!pattern || !text) return NULL;
    regex_t re;
    if (regcomp(&re, pattern, REG_EXTENDED | REG_NOSUB) != 0) return NULL;
    if (regexec(&re, text, 0, NULL, 0) != 0) {
        regfree(&re);
        return NULL;
    }
    regfree(&re);
    regmatch_t m;
    regex_t re2;
    if (regcomp(&re2, pattern, REG_EXTENDED) != 0) return strdup("");
    if (regexec(&re2, text, 1, &m, 0) != 0) {
        regfree(&re2);
        return strdup("");
    }
    size_t n = (size_t)(m.rm_eo - m.rm_so);
    char *r = malloc(n + 1);
    memcpy(r, text + m.rm_so, n);
    r[n] = '\0';
    regfree(&re2);
    return r;
}

char *zy_regex_replace(const char *pattern, const char *repl, const char *text) {
    if (!pattern || !text) return strdup("");
    regex_t re;
    if (regcomp(&re, pattern, REG_EXTENDED) != 0)
        return strdup(text);
    regmatch_t m;
    if (regexec(&re, text, 1, &m, 0) != 0) {
        regfree(&re);
        return strdup(text);
    }
    size_t pre = (size_t)m.rm_so;
    size_t post = strlen(text + m.rm_eo);
    size_t rl = repl ? strlen(repl) : 0;
    char *out = malloc(pre + rl + post + 1);
    memcpy(out, text, pre);
    if (repl) memcpy(out + pre, repl, rl);
    memcpy(out + pre + rl, text + m.rm_eo, post + 1);
    regfree(&re);
    return out;
}
