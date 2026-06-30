"""Tier 2 FFI dispatch for zhiyu-core host bridge."""

from __future__ import annotations

import json
import os
import threading
from typing import Any, List, Optional

_tls = threading.local()


def bind_session(session) -> None:
    _tls.session = session
    try:
        import workflow_server as ws
        ws._exec_tls.session = session
        ws.update_llm_env()
    except Exception:
        pass


def get_session():
    return getattr(_tls, "session", None)


def _resolve_handler(name: str):
    from workflow_lisp import GLOBAL_ENV, to_symbol

    if name in GLOBAL_ENV:
        return GLOBAL_ENV[name]
    sym = to_symbol(name)
    if sym in GLOBAL_ENV:
        return GLOBAL_ENV[sym]

    try:
        import workflow_server as ws
        if name in ws.GLOBAL_ENV:
            return ws.GLOBAL_ENV[name]
        sym = to_symbol(name)
        if sym in ws.GLOBAL_ENV:
            return ws.GLOBAL_ENV[sym]
    except Exception:
        pass

    extra = _EXTRA_HANDLERS.get(name)
    if extra:
        return extra
    return None


def _py_to_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, (list, tuple)):
        return [_py_to_json(x) for x in val]
    if isinstance(val, dict):
        return {str(k): _py_to_json(v) for k, v in val.items()}
    return str(val)


def _json_to_py(val: Any) -> Any:
    return val


def dispatch_ffi(name: str, args: Optional[List[Any]] = None, session=None) -> Any:
    if session is not None:
        bind_session(session)
    if os.environ.get("ZHIYU_MOCK", "").lower() in ("1", "true", "yes"):
        mock = _MOCK_HANDLERS.get(name)
        if mock:
            return mock(*(args or []))
        return None
    handler = _resolve_handler(name)
    if handler is None:
        raise ValueError(f"未知 FFI 函数：{name}")
    args = [_json_to_py(a) for a in (args or [])]
    return handler(*args)


def dispatch_ffi_json(name: str, args_json: str, session=None) -> str:
    args = json.loads(args_json) if args_json else []
    if not isinstance(args, list):
        args = [args]
    result = dispatch_ffi(name, args, session=session)
    return json.dumps(_py_to_json(result), ensure_ascii=False)


def _wait_seconds(seconds, *_a, **_k):
    import time
    time.sleep(max(0, float(seconds)))
    return None


def _slideshow_video(*args, **kwargs):
    from workflow.ai_services import lisp_slideshow_video
    return lisp_slideshow_video(*args, **kwargs)


_EXTRA_HANDLERS = {
    "wait-seconds": _wait_seconds,
    "slideshow-video": _slideshow_video,
}


def _mock_call_llm(prompt, *_args, **_kwargs):
    p = str(prompt)
    if "请根据这些搜索记录" in p or "推荐 3 部" in p:
        return "电影A\n电影B\n电影C"
    if "英文搜索关键词" in p or "搜索助手" in p or "{{关键词}}" in p:
        return "The Wandering Earth"
    if "非常好" in p or "顺手" in p:
        return "positive"
    if "分类" in p or "问题类型" in p:
        if "包装" in p or "摔坏" in p:
            return "质量差"
        if "一周" in p or "物流" in p:
            return "物流慢"
        return "其它"
    if "情感" in p or "反馈" in p:
        return "negative" if ("包装" in p or "物流" in p or "一周" in p) else "positive"
    return "[mock llm]"


def _mock_feishu(*_args, **_kwargs):
    return "飞书消息发送成功（mock）"


def _mock_torrent_search(term, *_a, **_k):
    t = str(term)
    return [{
        "title": f"[Mock] {t}",
        "size": "1.2 GB",
        "seeds": 50,
        "hash": "DEADBEEF",
        "source": "apibay",
        "magnet": "magnet:?xt=urn:btih:deadbeef",
    }]


def _mock_build_search_term(cn, en, *_a, **_k):
    return f"{cn}|{en}"


def _mock_search_progress(*_a, **_k):
    return None


def _mock_emit_torrent_results(*_a, **_k):
    return None


def _mock_emit_recommendations(*_a, **_k):
    return None


def _mock_load_history(*_a, **_k):
    return []


def _mock_save_history(_history, *_a, **_k):
    return "ok"


def _mock_wait_seconds(*_a, **_k):
    return None


def _mock_user_input(*_a, **_k):
    return ""


def _mock_handle(kind: str, **extra):
    out = {"handle": f"mock-{kind}"}
    out.update(extra)
    return out


def _mock_browser_start(*_a, **_k):
    return _mock_handle("browser")


def _mock_browser_open(_browser, url, *_a, **_k):
    return _mock_handle("page", url=str(url))


def _mock_browser_close(*_a, **_k):
    return None


def _mock_page_find(_page, selector, *_a, **_k):
    return _mock_handle("elem", selector=str(selector))


def _mock_page_find_all(_page, selector, *_a, **_k):
    return [_mock_handle("elem", selector=str(selector), index=i) for i in range(2)]


def _mock_elem_noop(*_a, **_k):
    return None


def _mock_page_wait_login(*_a, **_k):
    return True


def _mock_page_screenshot(_page, path, *_a, **_k):
    return str(path)


def _mock_excel_read(_path, *_a, **_k):
    return [
        ["产品名称", "规格", "单位"],
        [["测试产品A", "10ml", "盒"], ["测试产品B", "20ml", "瓶"]],
    ]


_MOCK_HANDLERS = {
    "call-llm": _mock_call_llm,
    "llm": _mock_call_llm,
    "send-to-feishu": _mock_feishu,
    "torrent-search": _mock_torrent_search,
    "build-search-term": _mock_build_search_term,
    "search-progress": _mock_search_progress,
    "emit-torrent-results": _mock_emit_torrent_results,
    "emit-recommendations": _mock_emit_recommendations,
    "load-history": _mock_load_history,
    "save-history": _mock_save_history,
    "wait-seconds": _mock_wait_seconds,
    "user-input": _mock_user_input,
    "browser-start": _mock_browser_start,
    "browser-open": _mock_browser_open,
    "browser-close": _mock_browser_close,
    "page-find": _mock_page_find,
    "page-find-all": _mock_page_find_all,
    "elem-fill": _mock_elem_noop,
    "elem-click": _mock_elem_noop,
    "page-exec": _mock_elem_noop,
    "page-screenshot": _mock_page_screenshot,
    "page-wait-login": _mock_page_wait_login,
    "page-scan": _mock_elem_noop,
    "page-click": _mock_elem_noop,
    "page-click-text": _mock_elem_noop,
    "page-wait-selector": _mock_elem_noop,
    "page-check": _mock_elem_noop,
    "page-click-checkbox": _mock_elem_noop,
    "excel-read": _mock_excel_read,
    "format-date": lambda s, *_a, **_k: str(s),
}
