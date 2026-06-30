#include "zhiyu/internal.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *src;
    size_t pos;
    size_t len;
    char err[256];
} Lexer;

static int lex_peek(Lexer *lx) {
    if (lx->pos >= lx->len) return 0;
    return (unsigned char)lx->src[lx->pos];
}

static int lex_next(Lexer *lx) {
    if (lx->pos >= lx->len) return 0;
    return (unsigned char)lx->src[lx->pos++];
}

static void lex_skip_ws(Lexer *lx) {
    for (;;) {
        while (lx->pos < lx->len && isspace(lex_peek(lx))) lex_next(lx);
        /* ; or fullwidth ； U+FF1B */
        if (lex_peek(lx) == ';') {
            while (lx->pos < lx->len && lex_peek(lx) != '\n') lex_next(lx);
            continue;
        }
        if (lx->pos + 2 < lx->len && (unsigned char)lx->src[lx->pos] == 0xef &&
            (unsigned char)lx->src[lx->pos + 1] == 0xbc &&
            (unsigned char)lx->src[lx->pos + 2] == 0x9b) {
            lx->pos += 3;
            while (lx->pos < lx->len && lex_peek(lx) != '\n') lex_next(lx);
            continue;
        }
        break;
    }
}

static char *buf_append(char *buf, size_t *len, size_t *cap, char c) {
    if (*len + 2 > *cap) {
        *cap = (*cap + 64) * 2;
        buf = realloc(buf, *cap);
    }
    buf[(*len)++] = c;
    buf[*len] = '\0';
    return buf;
}

static ZyValue *lex_string(Lexer *lx) {
    lex_next(lx);
    char *buf = NULL;
    size_t len = 0, cap = 0;
    for (;;) {
        int c = lex_next(lx);
        if (c == 0) {
            snprintf(lx->err, sizeof lx->err, "字符串未闭合");
            free(buf);
            return NULL;
        }
        if (c == '"') break;
        if (c == '\\') {
            c = lex_next(lx);
            if (c == 'n') c = '\n';
            else if (c == 't') c = '\t';
            else if (c == 'r') c = '\r';
        }
        buf = buf_append(buf, &len, &cap, (char)c);
    }
    ZyValue *v = zy_str_copy(buf ? buf : "");
    free(buf);
    return v;
}

static int is_utf8_bracket_open(Lexer *lx) {
    if (lx->pos + 2 >= lx->len) return 0;
    unsigned char *p = (unsigned char *)(lx->src + lx->pos);
    /* （ U+FF08 */ if (p[0] == 0xef && p[1] == 0xbc && p[2] == 0x88) return 1;
    /* 【 U+3010 */ if (p[0] == 0xe3 && p[1] == 0x80 && p[2] == 0x90) return 1;
    return 0;
}

static int is_utf8_bracket_close(Lexer *lx) {
    if (lx->pos + 2 >= lx->len) return 0;
    unsigned char *p = (unsigned char *)(lx->src + lx->pos);
    /* ） U+FF09 */ if (p[0] == 0xef && p[1] == 0xbc && p[2] == 0x89) return 1;
    /* 】 U+3011 */ if (p[0] == 0xe3 && p[1] == 0x80 && p[2] == 0x91) return 1;
    return 0;
}

static void lex_skip_utf8_bracket_open(Lexer *lx) {
    unsigned char *p = (unsigned char *)(lx->src + lx->pos);
    if (p[0] == 0xef) lx->pos += 3;
    else lx->pos += 3;
}

static char *lex_ident(Lexer *lx) {
    size_t start = lx->pos;
    while (lx->pos < lx->len) {
        unsigned char c = (unsigned char)lex_peek(lx);
        if (c == '(' || c == ')' || c == '[' || c == ']' || c == '"' || isspace(c) || c == ';')
            break;
        if (is_utf8_bracket_open(lx) || is_utf8_bracket_close(lx)) break;
        lex_next(lx);
    }
    size_t n = lx->pos - start;
    char *s = malloc(n + 1);
    memcpy(s, lx->src + start, n);
    s[n] = '\0';
    return s;
}

static ZyValue *parse_list(Lexer *lx);

static ZyValue *parse_expr(Lexer *lx) {
    lex_skip_ws(lx);
    if (lx->pos >= lx->len) return NULL;

    unsigned char c = (unsigned char)lex_peek(lx);
    if (c == '(' || c == '[') {
        lex_next(lx);
        return parse_list(lx);
    }
    if (is_utf8_bracket_open(lx)) {
        lex_skip_utf8_bracket_open(lx);
        return parse_list(lx);
    }
    if (c == '"') return lex_string(lx);

    if (c == ')' || c == ']' || is_utf8_bracket_close(lx)) {
        snprintf(lx->err, sizeof lx->err, "多余的 )");
        return NULL;
    }

    char *tok = lex_ident(lx);
    if (!tok) return zy_nil();

    if (strcmp(tok, "#t") == 0 || strcmp(tok, "#true") == 0 || strcmp(tok, "#真") == 0) {
        free(tok);
        return zy_bool(true);
    }
    if (strcmp(tok, "#f") == 0 || strcmp(tok, "#false") == 0 || strcmp(tok, "#假") == 0) {
        free(tok);
        return zy_bool(false);
    }
    char *end;
    long long iv = strtoll(tok, &end, 10);
    if (*end == '\0') { free(tok); return zy_int(iv); }
    double dv = strtod(tok, &end);
    if (*end == '\0') { free(tok); return zy_float(dv); }

    ZyValue *sym = zy_intern_symbol(tok);
    free(tok);
    return sym;
}

static ZyValue *parse_list(Lexer *lx) {
    ZyValue **items = NULL;
    size_t n = 0, cap = 0;

    for (;;) {
        lex_skip_ws(lx);
        if (lx->pos >= lx->len) {
            snprintf(lx->err, sizeof lx->err, "程序异常终止");
            goto fail;
        }
        if (lex_peek(lx) == ')' || lex_peek(lx) == ']') {
            lex_next(lx);
            break;
        }
        if (is_utf8_bracket_close(lx)) {
            lex_skip_utf8_bracket_open(lx);
            break;
        }

        ZyValue *item = parse_expr(lx);
        if (!item || (lx->err[0] && item == NULL)) {
            if (lx->err[0]) goto fail;
        }
        if (n + 1 >= cap) {
            cap = cap ? cap * 2 : 8;
            items = realloc(items, cap * sizeof(ZyValue *));
        }
        items[n++] = item;
    }

    ZyValue *list = zy_list(n, items);
    free(items);
    return list;

fail:
    for (size_t i = 0; i < n; i++) zy_release(items[i]);
    free(items);
    return NULL;
}

ZyValue *zy_parse_all(const char *code, char *errbuf, size_t errcap) {
    Lexer lx = { .src = code, .len = strlen(code) };
    ZyValue **forms = NULL;
    size_t nf = 0, cap = 0;

    for (;;) {
        lex_skip_ws(&lx);
        if (lx.pos >= lx.len) break;

        ZyValue *form = parse_expr(&lx);
        if (!form) {
            if (lx.err[0] && errbuf)
                snprintf(errbuf, errcap, "%s", lx.err);
            for (size_t i = 0; i < nf; i++) zy_release(forms[i]);
            free(forms);
            return NULL;
        }
        if (nf + 1 >= cap) {
            cap = cap ? cap * 2 : 4;
            forms = realloc(forms, cap * sizeof(ZyValue *));
        }
        forms[nf++] = form;
    }

    ZyValue *prog = zy_list(nf, forms);
    free(forms);
    return prog;
}
