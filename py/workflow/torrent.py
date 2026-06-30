"""
种子搜索模块 - 从多个 BT 种子站搜索磁力链接

策略：国际站为主、DHT 为辅（保障迅雷可下载）
- 第一梯队: apibay.org (TPB JSON)、dmhy.org (動漫花園)
- 第二梯队: btsow (DHT 补充)
- 第三梯队: skrbtmv/skrbtla (Playwright，仅第一梯队 < 3 条时启用)

设计原则: 与 Lisp 解释器完全解耦, 仅通过注册函数暴露能力
"""

import re
import json
import os
import time
import threading
import base64
import http.cookiejar
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_SEARCH_TIMEOUT = 8
_PLAYWRIGHT_TIMEOUT = 25

# 公共 tracker 列表，用于构建磁力链接（http 优先，国内可连接）
_TRACKERS = [
    "http://tracker.openbittorrent.com:80/announce",
    "http://p4p.arenabg.com:1337/announce",
    "http://open.acgnxtracker.com:80/announce",
    "http://tracker.bt-hash.com:80/announce",
    "http://t.nyaatracker.com:80/announce",
]

_DMHY_BASE = "https://dmhy.org"
_DMHY_DETAIL_WORKERS = 4
_SKRBT_FALLBACK_THRESHOLD = 3
_SEEDERS_AVAILABLE_MIN = 5
_SKRBT_SOURCES = frozenset({"skrbtmv", "skrbtla"})
_CHAT_API_URL = "http://127.0.0.1:8080/api/chat"

_SOURCE_LABELS = {
    "apibay": "TPB",
    "dmhy": "花园",
    "btsow": "DHT",
    "skrbtmv": "DHT",
    "skrbtla": "DHT",
    "torrentdownload": "TD",
}

_api_key_provider = None
_progress_callback = None
_cancel_check = lambda: False


def set_cancel_check(fn):
    """由 workflow_server 注入，终止执行时停止搜索子任务"""
    global _cancel_check
    _cancel_check = fn


def cancel_search_activity():
    """停止搜索心跳等后台活动"""
    active = _SearchHeartbeat.active
    if active:
        active._stop.set()
        if active._thread:
            active._thread.join(timeout=1)
        if _SearchHeartbeat.active is active:
            _SearchHeartbeat.active = None


def _is_cancelled():
    try:
        return bool(_cancel_check())
    except Exception:
        return False

_SOURCE_DISPLAY = {
    "apibay": "TPB",
    "dmhy": "花园动漫",
    "btsow": "DHT 索引",
    "skrbtmv": "深度 DHT",
    "skrbtla": "深度 DHT",
}


def set_api_key_provider(fn):
    """由 workflow_server 注入，供 LLM 翻译关键词时使用"""
    global _api_key_provider
    _api_key_provider = fn


def set_progress_callback(fn):
    """由 workflow_server 注入，搜索过程中向前端推送进度"""
    global _progress_callback
    _progress_callback = fn


def _emit_progress(message, percent=0, eta=None):
    if _is_cancelled():
        return
    cb = _progress_callback
    if not cb:
        return
    payload = {
        "message": message,
        "percent": min(100, max(0, int(percent))),
    }
    if eta is not None:
        payload["eta"] = max(0, int(eta))
    active = _SearchHeartbeat.active
    if active:
        active.note(message, percent, eta)
    cb(payload)


class _SearchHeartbeat:
    """搜索期间每 2 秒推送心跳，避免长时间无反馈"""
    active = None

    def __init__(self, message, percent=15, eta=45):
        self.message = message
        self.percent = percent
        self.eta = eta
        self._started_at = time.time()
        self._stop = threading.Event()
        self._thread = None

    def note(self, message, percent=None, eta=None):
        self.message = message
        if percent is not None:
            self.percent = percent
        if eta is not None:
            self.eta = eta

    def __enter__(self):
        _SearchHeartbeat.active = self
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if _SearchHeartbeat.active is self:
            _SearchHeartbeat.active = None

    def start(self):
        cb = _progress_callback
        if cb:
            cb({
                "message": self.message,
                "percent": self.percent,
                "eta": self.eta,
                "elapsed": 0,
            })
        self._thread = threading.Thread(target=self._tick, daemon=True)
        self._thread.start()

    def _tick(self):
        cb = _progress_callback
        if not cb:
            return
        while not self._stop.wait(2.0):
            if _is_cancelled():
                break
            elapsed = int(time.time() - self._started_at)
            remaining = max(0, self.eta - elapsed)
            pct = min(92, self.percent + elapsed // 3)
            cb({
                "message": self.message,
                "percent": pct,
                "eta": remaining,
                "elapsed": elapsed,
            })


def _resolve_api_key():
    if _api_key_provider:
        key = (_api_key_provider() or "").strip()
        if key:
            return key
    return (
        os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()

_PRIVATE_TLD = r"(?:com|net|org|cc|tv|me|info|co)"
_PRIVATE_DOMAIN_RE = re.compile(
    rf"(?:www\.)?[A-Za-z][A-Za-z0-9-]{{1,30}}\.{_PRIVATE_TLD}\b",
    re.I,
)

_SKRBT_DETAIL_WORKERS = 3

# 国内 DHT 聚合站（SkrBT 系，结构相同，需 Playwright 提交搜索表单）
_CN_DHT_SITES = [
    {"source": "skrbtmv", "base": "https://skrbtmv.top"},
    {"source": "skrbtla", "base": "https://skrbtla.top"},
]

# BTSOW 镜像（国内常见，HTML 列表 + 详情页 magnet）
_BTSOW_MIRRORS = [
    "https://btsow.motorcycles",
    "https://btsow.pics",
    "https://bt1.btsow.me",
    "https://btsow.icu",
]

# 常见中文片名 → 英文搜索词（无 API Key 时的兜底）
_CN_EN_MAP = {
    "你的名字": "kimi no na wa Your Name",
    "天气之子": "tenki no ko Weathering With You",
    "铃芽之旅": "suzume no tojimari",
    "鬼灭之刃": "kimetsu no yaiba demon slayer",
    "进击的巨人": "shingeki no kyojin attack on titan",
    "葬送的芙莉莲": "frieren sousou no frieren",
    "即刻上场": "Ji Ke Shang Chang",
    "绝命毒师": "Breaking Bad",
    "权力的游戏": "Game of Thrones",
    "复仇者联盟": "Avengers",
    "流浪地球": "The Wandering Earth",
    "狂飙": "The Knockout",
    "三体": "Three Body Problem",
    "庆余年": "Joy of Life",
    "琅琊榜": "Nirvana in Fire",
    "甄嬛传": "Empresses in the Palace",
    "肖申克的救赎": "Shawshank Redemption",
    "阿凡达": "Avatar",
    "星际穿越": "Interstellar",
    "盗梦空间": "Inception",
    "让子弹飞": "Let the Bullets Fly",
}

_GARBAGE_MARKERS = (
    "[MOCK", "收到提示词", "你是一个", "请直接输出", "{{关键词}}",
    "requirement", "DeepSeek", "API Key", "提示词",
)

_INFOHASH_RE = re.compile(r"^[A-Fa-f0-9]{40}$")


def _is_valid_info_hash(info_hash):
    """infohash 必须是 40 位十六进制字符串"""
    return bool(info_hash) and len(info_hash) == 40 and bool(_INFOHASH_RE.match(info_hash))


def _is_valid_magnet(magnet):
    """验证磁力链接格式及 infohash 有效性"""
    if not magnet or not str(magnet).lower().startswith("magnet:?"):
        return False
    return _is_valid_info_hash(_parse_magnet_hash(magnet))


def _enrich_magnet_if_needed(magnet, fallback_title=""):
    """
    保留详情页原始 btih/dn，若无 tracker 则追加国内可用 tracker 列表。
    已有 tr= 参数的 magnet 原样返回。
    """
    if not _is_valid_magnet(magnet):
        return ""
    if re.search(r"&tr=", magnet, re.I):
        return magnet
    ih = _parse_magnet_hash(magnet)
    dn_m = re.search(r"&dn=([^&]+)", magnet, re.I)
    if dn_m:
        tr_params = "&".join(f"tr={urllib.parse.quote(t, safe='')}" for t in _TRACKERS)
        return f"magnet:?xt=urn:btih:{ih.upper()}&dn={dn_m.group(1)}&{tr_params}"
    return _build_magnet(ih, fallback_title)


def _sanitize_dn(name):
    """清洗 magnet dn 显示名，去除私站水印与非法字符"""
    if not name:
        return ""
    name = re.sub(
        rf'[\[【][^\]】]*?\.{_PRIVATE_TLD}[^\]】]*[\]】]',
        '', name, flags=re.I,
    )
    name = re.sub(r'[\[【\(][^\]】\)]*?www\.[^\]】\)]+[\]】\)]', '', name, flags=re.I)
    name = re.sub(r'[\uFFE0-\uFFEF]', '', name)
    name = re.sub(r'[\x00-\x1F\x7F]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def _extract_dn_text(title, magnet):
    """从 magnet dn 参数或标题取显示名"""
    if magnet:
        dn_m = re.search(r"&dn=([^&]+)", magnet, re.I)
        if dn_m:
            return urllib.parse.unquote(dn_m.group(1))
    return title or ""


def _has_private_site_watermark(text):
    """检测 dn/标题中的私站域名水印（如 www.PTHDTV.com、HDSky.com）"""
    if not text:
        return False
    if re.search(
        rf'[\[【\(][^\]】\)]*?\.{_PRIVATE_TLD}[^\]】\)]*[\]】\)]',
        text, re.I,
    ):
        return True
    if re.search(
        rf'[\[【][^\]】]*?(?:www\.)?[A-Za-z0-9][\w-]*\.{_PRIVATE_TLD}[^\]】]*[\]】]',
        text, re.I,
    ):
        return True
    return bool(_PRIVATE_DOMAIN_RE.search(text))


def _clean_title(title):
    """去除私站域名水印，避免迅雷拒绝下载"""
    if not title:
        return ""
    t = re.sub(r'[\[【\(][^\]】\)]*?www\.[^\]】\)]+[\]】\)]', '', title)
    t = re.sub(r'[\[【][^\]】]*?\.(?:com|net|org|cc|tv|me)[^\]】]*[\]】]', '', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^[\]】\)]+', '', t).strip()
    t = re.sub(r'[\[【\(]+$', '', t).strip()
    return t


def _build_magnet(info_hash, name=""):
    """根据 info_hash 构建带 tracker 的磁力链接"""
    if not _is_valid_info_hash(info_hash):
        return ""
    ih = info_hash.upper()
    dn_name = _sanitize_dn(name)
    dn = urllib.parse.quote(dn_name, safe="") if dn_name else ""
    tr_params = "&".join(f"tr={urllib.parse.quote(t, safe='')}" for t in _TRACKERS)
    magnet = f"magnet:?xt=urn:btih:{ih}"
    if dn:
        magnet += f"&dn={dn}"
    magnet += f"&{tr_params}" if tr_params else ""
    return magnet


def _http_get(url, timeout=_SEARCH_TIMEOUT, referer=None, log_tag="", cookie_jar=None):
    """带 UA 的 HTTP GET"""
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    if cookie_jar is None:
        cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        if log_tag:
            print(f"[torrent/{log_tag}] OK len={len(body)} url={url[:100]}")
        return body
    except Exception as e:
        if log_tag:
            print(f"[torrent/{log_tag}] ERR {type(e).__name__}: {e} url={url[:100]}")
        return ""


def _format_size(size_bytes):
    """将字节数或纯数字字符串格式化为人类可读大小（如 1.4 GB、720 MB）"""
    if isinstance(size_bytes, str):
        s = size_bytes.strip()
        if not s or s == "未知":
            return "未知"
        # 已是带单位的可读格式
        if re.search(r"[KMGTPEZY]", s, re.I) and re.search(r"B\b", s, re.I):
            return s
        if re.fullmatch(r"\d+", s):
            size_bytes = int(s)
        elif re.fullmatch(r"[\d.]+", s):
            size_bytes = int(float(s))
        else:
            return s
    try:
        size_bytes = int(size_bytes)
    except (ValueError, TypeError):
        return "未知"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        mb = size_bytes / 1024 ** 2
        return f"{mb:.0f} MB" if mb >= 10 else f"{mb:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"


def _parse_magnet_hash(magnet):
    m = re.search(r"btih:([A-Fa-f0-9]{40})", magnet, re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"btih:([A-Za-z0-9]{32})", magnet, re.I)
    if m:
        import binascii
        try:
            return binascii.hexlify(base64.b32decode(m.group(1).upper())).decode().upper()
        except Exception:
            pass
    return ""


def _decode_skrbt_hash(encoded_hash):
    info_hash = ""
    try:
        padding = "=" * (4 - len(encoded_hash) % 4) if len(encoded_hash) % 4 else ""
        info_hash = base64.urlsafe_b64decode(encoded_hash + padding).hex().upper()
    except Exception:
        info_hash = ""
    prefix = encoded_hash[:12] if len(encoded_hash) >= 12 else encoded_hash
    valid = info_hash if _is_valid_info_hash(info_hash) else ""
    print(f"[torrent/skrbt] hash decode: {prefix}... → {valid or 'INVALID'}")
    return valid


def _parse_quality_tier(title):
    """从标题解析画质等级：4K/UHD/2160p=4，1080p/BluRay/BDRip=3，720p/HD=2"""
    t = (title or "").upper()
    if any(k in t for k in ("4K", "2160P", "UHD")):
        return 4
    if any(k in t for k in ("1080P", "BLURAY", "BDRIP")):
        return 3
    if any(k in t for k in ("720P", "HD")):
        return 2
    return 1


def _result(title, info_hash, size, seeds, leechers, source, date="", magnet=None, seeds_unknown=False):
    clean = _clean_title(title)
    ih = (info_hash or "").upper()
    if magnet and _is_valid_magnet(magnet):
        mag = _enrich_magnet_if_needed(magnet, clean)
        if not _is_valid_info_hash(ih):
            ih = _parse_magnet_hash(magnet)
    elif _is_valid_info_hash(ih):
        mag = _build_magnet(ih, clean)
    else:
        mag = ""
    if seeds_unknown:
        seed_n = None
    else:
        try:
            seed_n = int(seeds) if seeds not in (None, "") else 0
        except (ValueError, TypeError):
            seed_n = 0
    return {
        "title": clean or title.strip(),
        "hash": ih,
        "magnet": mag,
        "size": _format_size(size),
        "seeds": seed_n,
        "seeders": seed_n,
        "quality_tier": _parse_quality_tier(clean or title),
        "leechers": int(leechers) if leechers else 0,
        "date": date,
        "source": source,
        "source_label": _SOURCE_LABELS.get(source, source),
        "_seeders_known": not seeds_unknown,
    }


def _result_rank(r):
    tier = r.get("quality_tier", 1)
    if r.get("_seeders_known", True) and r.get("seeders") is not None:
        return (tier, r.get("seeders", 0))
    return (tier, -1)


def _is_available(r):
    """做种 >= 5 视为迅雷大概率可下载"""
    seeders = r.get("seeders")
    if seeders is None:
        return False
    return seeders >= _SEEDERS_AVAILABLE_MIN


def _sort_key(r):
    tier = r.get("quality_tier", 1)
    available_bucket = 0 if _is_available(r) else 1
    if r.get("_seeders_known", True) and r.get("seeders") is not None:
        return (available_bucket, -tier, 0, -r.get("seeders", 0))
    return (available_bucket, -tier, 1, 0)


def _merge_dedupe_sort(results):
    """infohash 去重，过滤私站水印/零做种 skrbt，按可用性+画质+做种排序"""
    seen = {}
    for r in results:
        if "quality_tier" not in r:
            r["quality_tier"] = _parse_quality_tier(r.get("title", ""))
        h = r.get("hash") or _parse_magnet_hash(r.get("magnet", ""))
        if not h:
            continue
        r["hash"] = h
        src = r.get("source", "")
        if src in _SKRBT_SOURCES and r.get("seeders") == 0:
            continue
        if r.get("_seeders_known", True) and r.get("seeders") == 0:
            continue
        dn_text = _extract_dn_text(r.get("title", ""), r.get("magnet", ""))
        if _has_private_site_watermark(dn_text) or _has_private_site_watermark(r.get("title", "")):
            continue
        if h not in seen or _result_rank(r) > _result_rank(seen[h]):
            seen[h] = r
    merged = list(seen.values())
    merged.sort(key=_sort_key)
    for r in merged:
        r.pop("_seeders_known", None)
    return merged


def _timed_search(search_fn, source_name, *args, timeout=_SEARCH_TIMEOUT, **kwargs):
    enc_kw = args[0] if args else ""
    if isinstance(enc_kw, str) and re.search(r"[\u4e00-\u9fff]", enc_kw):
        print(f"[torrent] {source_name} keyword={enc_kw!r} encoded={urllib.parse.quote(enc_kw)}")
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(search_fn, *args, **kwargs)
        try:
            results = fut.result(timeout=timeout)
            print(f"[torrent] {source_name} -> {len(results)} results")
            return results
        except Exception as e:
            print(f"[torrent] {source_name} -> TIMEOUT/ERR {type(e).__name__}: {e}")
            return []


def _count_unique_results(results):
    seen = set()
    for r in results:
        h = r.get("hash") or _parse_magnet_hash(r.get("magnet", ""))
        if h:
            seen.add(h)
    return len(seen)


def _translate_search_keyword(keyword):
    """将影视作品名翻译为英文搜索词，直接调用 LLM（避免 HTTP 回环阻塞）"""
    prompt = (
        "将以下影视作品名翻译为最常用的英文搜索关键词，"
        f"只返回英文关键词，不加任何解释：{keyword}"
    )
    _emit_progress("正在翻译搜索关键词…", 6, 15)
    api_key = _resolve_api_key()
    if api_key:
        try:
            from workflow.llm import call_llm
            raw = call_llm(
                prompt,
                config={"api_key": api_key, "temperature": 0.1, "max_tokens": 64},
            )
            en = raw.strip().split("\n")[0].strip().strip("\"'")
            if en and not _is_garbage_keyword(en):
                print(f"[torrent] call_llm 翻译: {keyword!r} -> {en!r}")
                _emit_progress(f"翻译完成: {en}", 12, 35)
                return en
        except Exception as e:
            print(f"[torrent] call_llm 翻译失败: {type(e).__name__}: {e}")
    guess = torrent_guess_en(keyword)
    if guess:
        print(f"[torrent] 内置词典: {keyword!r} -> {guess!r}")
        _emit_progress(f"使用内置词典: {guess}", 12, 35)
    return guess


def _search_keyword_tiered(kw, progress_base=18):
    """按梯队搜索：apibay+dmhy → btsow → skrbt（第一梯队 < 3 条时）"""
    if _is_cancelled():
        return []
    results = []

    _emit_progress("正在搜索 TPB / 花园动漫…", progress_base, eta=28)
    tier1 = []
    tier1_done = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(_timed_search, _search_apibay, f"apibay:{kw}", kw, 30, timeout=20): "apibay",
            ex.submit(_timed_search, _search_dmhy, f"dmhy:{kw}", kw, 20, timeout=25): "dmhy",
        }
        for fut in as_completed(futures):
            if _is_cancelled():
                for pending in futures:
                    pending.cancel()
                break
            src = futures[fut]
            tier1_done += 1
            try:
                tier1.extend(fut.result())
            except Exception:
                pass
            label = _SOURCE_DISPLAY.get(src, src)
            _emit_progress(
                f"{label} 已完成 ({tier1_done}/2)",
                progress_base + tier1_done * 12,
                eta=max(5, 24 - tier1_done * 8),
            )
    results.extend(tier1)

    if _is_cancelled():
        return results

    tier1_count = _count_unique_results(_merge_dedupe_sort(list(tier1)))
    print(f"[torrent] tier1(apibay+dmhy)={tier1_count} unique")

    _emit_progress("正在搜索 DHT 索引站…", progress_base + 30, eta=18)
    if _is_cancelled():
        return results
    tier2 = _timed_search(_search_btsow, f"btsow:{kw}", kw, 20, timeout=15)
    results.extend(tier2)
    _emit_progress("DHT 索引搜索完成", progress_base + 45, eta=12)

    if _is_cancelled():
        return results

    if tier1_count < _SKRBT_FALLBACK_THRESHOLD:
        print(f"[torrent] tier1={tier1_count} < {_SKRBT_FALLBACK_THRESHOLD}，启用 skrbt Playwright")
        _emit_progress("结果较少，深度 DHT 搜索中（约 20 秒）…", progress_base + 52, eta=22)
        tier3 = []
        tier3_done = 0
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = [
                ex.submit(_timed_search, _search_skrbtmv, f"skrbtmv:{kw}", kw, 20, timeout=_PLAYWRIGHT_TIMEOUT),
                ex.submit(_timed_search, _search_skrbtla, f"skrbtla:{kw}", kw, 20, timeout=_PLAYWRIGHT_TIMEOUT),
            ]
            for fut in as_completed(futs):
                if _is_cancelled():
                    for pending in futs:
                        pending.cancel()
                    break
                tier3_done += 1
                try:
                    tier3.extend(fut.result())
                except Exception:
                    pass
                _emit_progress(
                    f"深度 DHT 搜索 ({tier3_done}/2)",
                    progress_base + 52 + tier3_done * 10,
                    eta=max(5, 20 - tier3_done * 8),
                )
        results.extend(tier3)
    else:
        print(f"[torrent] tier1={tier1_count} >= {_SKRBT_FALLBACK_THRESHOLD}，跳过 skrbt")

    _emit_progress("正在整理搜索结果…", progress_base + 72, eta=3)
    return results


def _is_garbage_keyword(kw):
    if not kw or len(kw) > 150:
        return True
    return any(m in kw for m in _GARBAGE_MARKERS)


def _sanitize_keywords(keyword):
    if "|" in keyword:
        parts = [p.strip() for p in keyword.split("|") if p.strip()]
    else:
        parts = [keyword.strip()] if keyword.strip() else []

    clean = [p for p in parts if not _is_garbage_keyword(p)]
    expanded = list(clean)
    for p in clean:
        if re.search(r"[\u4e00-\u9fff]", p):
            if p in _CN_EN_MAP:
                expanded.append(_CN_EN_MAP[p])
            compact = p.replace(" ", "")
            if compact in _CN_EN_MAP and _CN_EN_MAP[compact] not in expanded:
                expanded.append(_CN_EN_MAP[compact])

    seen = set()
    out = []
    for p in expanded:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _parse_magnets_from_html(html, source, limit=25):
    results = []
    seen = set()
    for m in re.finditer(
        r'magnet:\?xt=urn:btih:([A-Fa-f0-9]{40})[^"\'\s<>]*',
        html, re.I
    ):
        ih = m.group(1).upper()
        if ih in seen:
            continue
        seen.add(ih)
        start = max(0, m.start() - 300)
        ctx = html[start:m.start()]
        title_m = re.search(r'>([^<]{4,200})</a>\s*$', ctx)
        title = title_m.group(1).strip() if title_m else f"种子 {ih[:8]}"
        title = re.sub(r"<[^>]+>", "", title).strip()
        results.append(_result(title, ih, "未知", None, 0, source, seeds_unknown=True))
        if len(results) >= limit:
            break
    return results


# ============================================================
# 搜索源: SkrBT 系（skrbtmv / skrbtla）— Playwright 表单搜索
# ============================================================

def _fetch_skrbt_detail_magnets_playwright(page, base, detail_paths):
    """在 Playwright 会话内 fetch 详情页（携带 cookie），并发 3"""
    results = {}
    base = base.rstrip("/")
    for i in range(0, len(detail_paths), _SKRBT_DETAIL_WORKERS):
        batch = detail_paths[i:i + _SKRBT_DETAIL_WORKERS]
        try:
            batch_results = page.evaluate(
                """async ({baseUrl, paths}) => {
                    const re = /magnet:\\?xt=urn:btih:[A-Fa-f0-9]{40}[^"'\\s<]*/i;
                    const out = {};
                    await Promise.all(paths.map(async (path) => {
                        try {
                            const ctrl = new AbortController();
                            const timer = setTimeout(() => ctrl.abort(), 5000);
                            const r = await fetch(baseUrl + path, {
                                credentials: 'include',
                                signal: ctrl.signal,
                            });
                            clearTimeout(timer);
                            const t = await r.text();
                            const m = t.match(re);
                            out[path] = m ? m[0] : '';
                        } catch (e) {
                            out[path] = '';
                        }
                    }));
                    return out;
                }""",
                {"baseUrl": base, "paths": batch},
            )
        except Exception as e:
            print(f"[torrent/skrbt] detail batch ERR {type(e).__name__}: {e}")
            batch_results = {p: "" for p in batch}
        for path in batch:
            magnet = batch_results.get(path, "")
            if magnet and _is_valid_magnet(magnet):
                print(f"[torrent/skrbt] detail magnet OK: {path[:40]}...")
                results[path] = magnet
            else:
                print(f"[torrent/skrbt] detail magnet MISS: {path[:40]}...")
                results[path] = ""
    return results


def _parse_skrbt_html(html, base, source, limit=20, detail_magnets=None):
    """
    解析 SkrBT 搜索结果页 HTML。
    优先使用详情页抓取的完整 magnet，失败时 fallback 到 infohash 解码。
    """
    detail_magnets = detail_magnets or {}
    results = []
    seen = set()
    items = re.findall(
        r'<a class="rrt common-link" href="(/detail/[A-F0-9]+/[A-Za-z0-9_-]+)"[^>]*>\s*(.*?)\s*</a>',
        html, re.DOTALL
    )
    sizes = re.findall(r"文件大小:.*?<span[^>]*>([^<]+)</span>", html)
    seeders_list = re.findall(r"(?:做种|热度|seeders?)[:：\s]*(\d+)", html, re.I)

    pending = []
    for i, (detail_path, raw_title) in enumerate(items[:limit]):
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        if not title:
            continue
        encoded_hash = detail_path.rsplit("/", 1)[-1]
        pending.append({
            "detail_path": detail_path,
            "encoded_hash": encoded_hash,
            "title": title,
            "size": sizes[i].strip() if i < len(sizes) else "未知",
            "seeds": seeders_list[i] if i < len(seeders_list) else None,
        })

    for p in pending:
        magnet = detail_magnets.get(p["detail_path"], "")
        if magnet and _is_valid_magnet(magnet):
            ih = _parse_magnet_hash(magnet)
            if not ih or ih in seen:
                continue
            seen.add(ih)
            results.append(_result(
                p["title"], ih, p["size"],
                p["seeds"], 0, source,
                magnet=magnet,
                seeds_unknown=p["seeds"] is None,
            ))
            continue

        info_hash = _decode_skrbt_hash(p["encoded_hash"])
        if not info_hash or not _is_valid_info_hash(info_hash) or info_hash in seen:
            continue
        seen.add(info_hash)
        results.append(_result(
            p["title"], info_hash, p["size"],
            p["seeds"], 0, source,
            seeds_unknown=p["seeds"] is None,
        ))

    if len(results) < 3:
        fallback = _parse_magnets_from_html(html, source, limit)
        for r in fallback:
            h = r.get("hash")
            if h and h not in seen:
                seen.add(h)
                results.append(r)
            if len(results) >= limit:
                break
    return results


def _playwright_skrbt_search(base, source, keyword, limit=20):
    """
    SkrBT 站点 JS 渲染：直接 GET /search?keyword= 只返回首页，
    必须通过首页表单提交 keyword 才能拿到结果页。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"[torrent/{source}] playwright 未安装，跳过")
        return []

    import time
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(user_agent=_UA, locale="zh-CN")
            page = context.new_page()
            page.add_init_script(
                'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            )

            enc = urllib.parse.quote(keyword)
            search_url = f"{base}/search?keyword={enc}"
            print(f"[torrent/{source}] GET {search_url}")
            page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(2)
            html = page.content()

            if html.count("/detail/") < 2:
                print(f"[torrent/{source}] 直接 URL 无结果，改用表单搜索")
                page.goto(f"{base}/", timeout=20000, wait_until="domcontentloaded")
                time.sleep(1)
                inp = page.query_selector('input[name="keyword"]')
                if not inp:
                    browser.close()
                    return []
                page.fill('input[name="keyword"]', keyword)
                btn = page.query_selector("button.search-btn")
                if btn:
                    btn.click()
                else:
                    page.keyboard.press("Enter")
                time.sleep(5)
                html = page.content()

            print(f"[torrent/{source}] HTML len={len(html)} detail_links={html.count('/detail/')}")
            if html.count("/detail/") < 1:
                browser.close()
                return []
            detail_paths = list(dict.fromkeys(
                re.findall(r'href="(/detail/[A-F0-9]+/[A-Za-z0-9_-]+)"', html)
            ))[:limit]
            detail_magnets = _fetch_skrbt_detail_magnets_playwright(page, base, detail_paths)
            browser.close()
            return _parse_skrbt_html(html, base, source, limit, detail_magnets)
    except Exception as e:
        print(f"[torrent/{source}] playwright ERR {type(e).__name__}: {e}")
        return []


def _search_skrbtmv(keyword, limit=20):
    return _playwright_skrbt_search("https://skrbtmv.top", "skrbtmv", keyword, limit)


def _search_skrbtla(keyword, limit=20):
    return _playwright_skrbt_search("https://skrbtla.top", "skrbtla", keyword, limit)


def _search_cn_dht(keyword, limit=20):
    """并发搜索所有国内 DHT 聚合站"""
    all_results = []
    with ThreadPoolExecutor(max_workers=len(_CN_DHT_SITES)) as ex:
        futs = {
            ex.submit(_playwright_skrbt_search, s["base"], s["source"], keyword, limit): s["source"]
            for s in _CN_DHT_SITES
        }
        for fut in as_completed(futs):
            try:
                all_results.extend(fut.result(timeout=_SEARCH_TIMEOUT))
            except Exception:
                pass
    return all_results[:limit]


# ============================================================
# 搜索源: dmhy.org（動漫花園）
# ============================================================

def _parse_dmhy_list(html, limit=20):
    """解析 dmhy 列表页：.topic-title a 或 td.title a"""
    items = []
    for row in html.split('<tr class="">')[1:]:
        title_m = re.search(
            r'(?:class="topic-title"|class="title")[^>]*>.*?'
            r'<a\s+href="(/topics/view/[^"]+)"[^>]*>(.*?)</a>',
            row, re.DOTALL | re.I,
        )
        if not title_m:
            title_m = re.search(
                r'<td class="title">\s*<a href="(/topics/view/[^"]+)"[^>]*>(.*?)</a>',
                row, re.DOTALL | re.I,
            )
        if not title_m:
            continue
        detail_path, raw_title = title_m.groups()
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        if not title:
            continue
        size_m = re.search(r'>([\d.]+\s*[KMGTP]?B)<', row, re.I)
        size = size_m.group(1).strip() if size_m else "未知"
        mag_m = re.search(r'data-magnet="(magnet:[^"]+)"', row, re.I)
        list_magnet = mag_m.group(1) if mag_m else ""
        items.append({
            "detail_path": detail_path,
            "title": title,
            "size": size,
            "list_magnet": list_magnet,
        })
        if len(items) >= limit:
            break
    return items


def _fetch_dmhy_detail(detail_path):
    """抓取 dmhy 详情页 magnet 与 seeders"""
    url = detail_path if detail_path.startswith("http") else f"{_DMHY_BASE}{detail_path}"
    html = _http_get(url, referer=_DMHY_BASE, log_tag="dmhy/detail", timeout=10)
    if not html:
        return "", None

    magnet = ""
    for pat in (
        r'id="magnet2"\s+href="(magnet:[^"]+)"',
        r'data-magnet="(magnet:[^"]+)"',
        r'id="a_magnet"\s+href="(magnet:[^"]+)"',
        r'class="magnet"[^>]+href="(magnet:[^"]+)"',
    ):
        m = re.search(pat, html, re.I)
        if m and _parse_magnet_hash(m.group(1)):
            magnet = m.group(1)
            break

    seeds = None
    for pat in (
        r'做种[：:\s]*(\d+)',
        r'(\d+)\s*做种',
        r'seeders?[：:\s]*(\d+)',
        r'已连接[^<]{0,20}(\d+)',
    ):
        sm = re.search(pat, html, re.I)
        if sm:
            try:
                seeds = int(sm.group(1))
                break
            except ValueError:
                pass
    return magnet, seeds


def _search_dmhy(keyword, limit=20):
    enc = urllib.parse.quote(keyword)
    url = f"{_DMHY_BASE}/topics/list?keyword={enc}"
    html = _http_get(url, referer=_DMHY_BASE, log_tag="dmhy")
    if not html:
        return []

    items = _parse_dmhy_list(html, limit)
    if not items:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=_DMHY_DETAIL_WORKERS) as ex:
        futs = {ex.submit(_fetch_dmhy_detail, it["detail_path"]): it for it in items}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                detail_magnet, seeds = fut.result(timeout=12)
            except Exception:
                detail_magnet, seeds = "", None
            magnet = detail_magnet or it.get("list_magnet", "")
            ih = _parse_magnet_hash(magnet)
            if not ih:
                continue
            seeds_unknown = seeds is None
            seed_val = seeds if seeds is not None else 0
            results.append(_result(
                it["title"], ih, it["size"],
                seed_val, 0, "dmhy",
                magnet=magnet if _is_valid_magnet(magnet) else None,
                seeds_unknown=seeds_unknown,
            ))
    return results[:limit]


# ============================================================
# 搜索源: BTSOW 镜像（HTML）
# ============================================================

def _search_btsow(keyword, limit=20):
    enc = urllib.parse.quote(keyword)
    for mirror in _BTSOW_MIRRORS:
        url = f"{mirror}/search/{enc}/1/0.html"
        html = _http_get(url, referer=mirror, log_tag=f"btsow")
        if not html or len(html) < 3000:
            continue

        results = []
        items = re.findall(
            r'<a[^>]+href="(/magnet/[^"]+)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        for href, raw_title in items[:limit]:
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            if not title or len(title) < 2:
                continue
            detail_url = mirror + href if href.startswith("/") else href
            detail_html = _http_get(detail_url, referer=url, log_tag="btsow/detail")
            magnet_m = re.search(r'(magnet:\?[^"\']+)', detail_html or html)
            if not magnet_m:
                continue
            ih = _parse_magnet_hash(magnet_m.group(1))
            if not ih:
                continue
            results.append(_result(title, ih, "未知", None, 0, "btsow", magnet=magnet_m.group(1), seeds_unknown=True))
            if len(results) >= limit:
                break

        if not results:
            results = _parse_magnets_from_html(html, "btsow", limit)
        if results:
            return results
    return []


# ============================================================
# 搜索源: torrentdownload.info（英文补充）
# ============================================================

def _search_torrentdownload(keyword, limit=20):
    url = f"https://www.torrentdownload.info/search?q={urllib.parse.quote(keyword)}"
    html = _http_get(url, log_tag="torrentdownload")
    if not html:
        return []

    pattern = (
        r'<td class="tdleft"><div class="tt-name">'
        r'<a href="/([a-fA-F0-9]+)/[^"]*"[^>]*>(.*?)</a>'
        r'.*?</td>'
        r'<td class="tdnormal">([^<]*)</td>'
        r'<td class="tdnormal">([^<]*)</td>'
        r'<td class="tdseed">([^<]*)</td>'
        r'<td class="tdleech">([^<]*)</td>'
    )
    rows = re.findall(pattern, html, re.DOTALL)
    results = []
    for row in rows[:limit]:
        info_hash, raw_title, date, size, seeds, leechers = row
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        try:
            seed_count = int(seeds.replace(",", ""))
        except ValueError:
            seed_count = 0
        try:
            leech_count = int(leechers.replace(",", ""))
        except ValueError:
            leech_count = 0
        results.append(_result(title, info_hash, size.strip(), seed_count, leech_count, "torrentdownload", date.strip()))
    return results


# ============================================================
# 搜索源: apibay.org（TPB JSON API，第一梯队）
# ============================================================

def _search_apibay_raw(keyword, limit=30, relevance_filter=True):
    url = f"https://apibay.org/q.php?q={urllib.parse.quote(keyword)}&cat="
    raw = _http_get(url, log_tag="apibay")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []
    if not data or (len(data) == 1 and data[0].get("name") == "No results returned"):
        return []

    if relevance_filter:
        query_words = [w for w in keyword.lower().split() if len(w) > 2]
        if query_words:
            top_titles = " ".join(item.get("name", "").lower() for item in data[:5])
            if not any(w in top_titles for w in query_words):
                print(f"[torrent/apibay] relevance filter rejected keyword={keyword!r}")
                return []

    results = []
    for item in data[:limit]:
        name = item.get("name", "")
        info_hash = item.get("info_hash", "")
        if not info_hash:
            continue
        results.append(_result(
            name, info_hash, _format_size(item.get("size", 0)),
            item.get("seeders", 0), item.get("leechers", 0), "apibay"
        ))
    return results


def _search_apibay(keyword, limit=30):
    """TPB 搜索：中文先 LLM 英译，原词 + 英文词各搜一次后合并"""
    is_cjk = bool(re.search(r"[\u4e00-\u9fff]", keyword))
    search_terms = [keyword]
    if is_cjk:
        en = _translate_search_keyword(keyword)
        if en and en.strip().lower() != keyword.strip().lower():
            search_terms.append(en.strip())

    seen = {}
    for term in search_terms:
        is_term_cjk = bool(re.search(r"[\u4e00-\u9fff]", term))
        batch = _search_apibay_raw(term, limit, relevance_filter=not is_term_cjk)
        if is_term_cjk:
            batch = [r for r in batch if term in (r.get("title") or "")]
        for r in batch:
            h = r.get("hash")
            if not h:
                continue
            if h not in seen or _result_rank(r) > _result_rank(seen[h]):
                seen[h] = r
    return list(seen.values())[:limit]


# ============================================================
# 聚合搜索
# ============================================================

def search_torrents(keyword):
    """
    按梯队搜索多个站点，返回合并结果列表。
    keyword 可以是单个字符串或用 | 分隔的多个关键词。
    """
    if _is_cancelled():
        return []
    keywords = _sanitize_keywords(keyword)
    if not keywords:
        return []

    hb = _SearchHeartbeat("正在并发搜索种子站…", 15, 45)
    with hb:
        all_results = []
        total = len(keywords)
        for idx, kw in enumerate(keywords):
            if _is_cancelled():
                break
            if total > 1:
                _emit_progress(
                    f"搜索关键词 ({idx + 1}/{total}): {kw}",
                    15 + idx * 60 // total,
                    35,
                )
            base = 18 + idx * 70 // max(total, 1)
            all_results.extend(_search_keyword_tiered(kw, progress_base=base))
        _emit_progress("搜索完成，正在筛选结果…", 94, 2)
        return _merge_dedupe_sort(all_results)


def torrent_guess_en(keyword):
    kw = keyword.strip()
    if kw in _CN_EN_MAP:
        return _CN_EN_MAP[kw]
    compact = kw.replace(" ", "")
    if compact in _CN_EN_MAP:
        return _CN_EN_MAP[compact]
    return ""


def build_search_term(keyword, llm_english=""):
    kw = (keyword or "").strip()
    parts = [kw] if kw else []
    en = (llm_english or "").strip()
    if en and not _is_garbage_keyword(en):
        en = en.split("\n")[0].strip()
        if en and en.lower() not in {p.lower() for p in parts}:
            parts.append(en)
            print(f"  英文关键词: {en}")
            _emit_progress(f"已获取英文关键词: {en}", 12, eta=38)
    else:
        guess = torrent_guess_en(kw)
        if guess and guess.lower() not in {p.lower() for p in parts}:
            parts.append(guess)
            print(f"  使用内置词典: {guess}")
            _emit_progress(f"使用内置词典: {guess}", 12, eta=38)
        elif len(parts) == 1:
            print("  未获取英文关键词，仅使用中文搜索")
            _emit_progress("未获取英文关键词，仅使用中文搜索", 12, eta=38)
    return "|".join(parts)


def torrent_search(keyword):
    """搜索种子 - 返回原始结果列表"""
    return search_torrents(keyword)
