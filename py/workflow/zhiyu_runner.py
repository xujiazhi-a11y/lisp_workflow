#!/usr/bin/env python3
"""Subprocess bridge: zhiyu-core server mode ↔ Python Tier 2 FFI."""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
from typing import List, Optional

from workflow.ffi_handlers import bind_session, dispatch_ffi_json
from workflow.user_errors import format_user_error


def find_zhiyu_binary(explicit: Optional[str] = None) -> str:
    if explicit and os.path.isfile(explicit):
        return os.path.abspath(explicit)
    env = os.environ.get("ZHIYU_BIN")
    if env and os.path.isfile(env):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, "..", "..", "zhiyu-core", "zhiyu")
    if os.path.isfile(candidate):
        return os.path.abspath(candidate)
    return "zhiyu"


def default_base_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "examples"))


def _read_line(stream) -> Optional[str]:
    line = stream.readline()
    if not line:
        return None
    return line.rstrip("\n")


def _send_cmd(proc, obj: dict) -> None:
    proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _handle_host_line(line: str, proc, session) -> bool:
    """Returns False if execution should stop."""
    if line == "__DONE__":
        session.output_queue.put("__DONE__")
        return False
    if line == "__STOPPED__":
        session.output_queue.put("__STOPPED__")
        return False
    if line.startswith("__ERROR__:"):
        session.output_queue.put(line)
        return False
    if line.startswith("__RESULT__:"):
        session.output_queue.put(line)
        return True
    if line.startswith("__TEXT__:") or line.startswith("__MD__:"):
        session.output_queue.put(line)
        return True
    if line.startswith("__PROGRESS__:") or line.startswith("__TORRENT__:"):
        session.output_queue.put(line)
        return True
    if line.startswith("__RECOMMEND__:"):
        session.output_queue.put(line)
        return True
    if line.startswith("__INPUT__:"):
        session.output_queue.put(line)
        while not session.stopped():
            try:
                val = session.input_queue.get(timeout=1.0)
                _send_cmd(proc, {"cmd": "input_resp", "value": val})
                return True
            except queue.Empty:
                continue
        return False
    if line.startswith("__INTERACT__:"):
        session.output_queue.put(line)
        while not session.stopped():
            try:
                val = session.input_queue.get(timeout=1.0)
                _send_cmd(proc, {"cmd": "interact_resp", "value": val})
                return True
            except queue.Empty:
                continue
        return False
    if line.startswith("__HOST_FFI__:"):
        payload = json.loads(line[len("__HOST_FFI__:"):])
        result_json = dispatch_ffi_json(
            payload["name"], json.dumps(payload.get("args", []), ensure_ascii=False), session
        )
        _send_cmd(proc, {"cmd": "ffi_resp", "id": payload["id"], "value": json.loads(result_json)})
        return True
    if line == "__PONG__":
        return True
    return True


def run_zhiyu_session(session, code: str, zhiyu_bin: Optional[str] = None, base_dir: Optional[str] = None):
    zhiyu = find_zhiyu_binary(zhiyu_bin)
    base = base_dir or default_base_dir()
    bind_session(session)

    proc = subprocess.Popen(
        [zhiyu, "server", "--base-dir", base],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    session.zhiyu_proc = proc

    try:
        _send_cmd(proc, {"cmd": "eval", "code": code})
        while True:
            if session.stopped():
                _send_cmd(proc, {"cmd": "stop"})
                session.output_queue.put("__STOPPED__")
                return
            line = _read_line(proc.stdout)
            if line is None:
                err = proc.stderr.read().strip()
                if err:
                    session.output_queue.put(f"__ERROR__:{err[:800]}")
                else:
                    session.output_queue.put("__ERROR__:zhiyu 子进程意外退出")
                break
            if not _handle_host_line(line, proc, session):
                break
    except Exception as e:
        if not session.stopped():
            session.output_queue.put(f"__ERROR__:{format_user_error(e)}")
    finally:
        session.zhiyu_proc = None
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def run_zhiyu_file(session, path: str, **kwargs):
    zhiyu = find_zhiyu_binary(kwargs.get("zhiyu_bin"))
    base = kwargs.get("base_dir") or default_base_dir()
    bind_session(session)
    proc = subprocess.Popen(
        [zhiyu, "server", "--base-dir", base],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    session.zhiyu_proc = proc
    try:
        _send_cmd(proc, {"cmd": "run", "path": path})
        while True:
            if session.stopped():
                _send_cmd(proc, {"cmd": "stop"})
                session.output_queue.put("__STOPPED__")
                return
            line = _read_line(proc.stdout)
            if line is None:
                err = proc.stderr.read().strip()
                if err:
                    session.output_queue.put(f"__ERROR__:{err[:800]}")
                else:
                    session.output_queue.put("__ERROR__:zhiyu 子进程意外退出")
                break
            if not _handle_host_line(line, proc, session):
                break
    except Exception as e:
        if not session.stopped():
            session.output_queue.put(f"__ERROR__:{format_user_error(e)}")
    finally:
        session.zhiyu_proc = None
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class _TestSession:
    def __init__(self, inputs: Optional[List[str]] = None):
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        for v in inputs or []:
            self.input_queue.put(v)
        self._stopped = False
        self.markdown = False
        self.client_id = "test"

    def stopped(self):
        return self._stopped

    def request_stop(self):
        self._stopped = True


def _collect_outputs(session: _TestSession) -> List[str]:
    out = []
    while True:
        try:
            item = session.output_queue.get(timeout=120)
        except queue.Empty:
            break
        out.append(item)
        if item in ("__DONE__", "__STOPPED__") or item.startswith("__ERROR__:"):
            break
    return out


def reload_zhiyu_file(session, rel_path: str, timeout: float = 5.0) -> bool:
    """Send reload to an active zhiyu server subprocess (M4 HR-5)."""
    proc = getattr(session, "zhiyu_proc", None)
    if not proc or proc.poll() is not None:
        return False
    _send_cmd(proc, {"cmd": "reload", "path": rel_path.replace("\\", "/")})
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = _read_line(proc.stdout)
        if line is None:
            return False
        if line == "__RELOADED__":
            return True
        if line.startswith("__ERROR__:"):
            return False
    return False


def run_test_m3(zhiyu_bin: Optional[str] = None) -> int:
    os.environ["ZHIYU_MOCK"] = "1"
    base = default_base_dir()

    # m3-04 飞书反馈分类
    feishu = os.path.join(base, "演示Demo", "飞书反馈分类.lisp")
    with open(feishu, "r", encoding="utf-8") as f:
        code = f.read()
    session = _TestSession()
    run_zhiyu_session(session, code, zhiyu_bin=zhiyu_bin)
    lines = _collect_outputs(session)
    if any(x.startswith("__ERROR__:") for x in lines):
        print("\n".join(lines), file=sys.stderr)
        return 1
    if "__DONE__" not in lines:
        print("飞书: missing __DONE__", file=sys.stderr)
        return 1
    print("=== m3 bridge 飞书反馈分类 OK ===")

    # m3-01 种子搜索（mock input + FFI）
    session2 = _TestSession(inputs=["流浪地球", "q"])
    run_zhiyu_file(session2, "种子搜索.lisp", zhiyu_bin=zhiyu_bin)
    lines2 = _collect_outputs(session2)
    if any(x.startswith("__ERROR__:") for x in lines2):
        print("\n".join(lines2), file=sys.stderr)
        return 1
    if "__DONE__" not in lines2:
        print("种子搜索: missing __DONE__", file=sys.stderr)
        return 1
    print("=== m3 bridge 种子搜索 OK ===")

    # m3-03 医疗备案填表（mock browser + input）
    session3 = _TestSession(inputs=[""])
    run_zhiyu_file(session3, "医疗备案填表.lisp", zhiyu_bin=zhiyu_bin)
    lines3 = _collect_outputs(session3)
    if any(x.startswith("__ERROR__:") for x in lines3):
        print("\n".join(lines3), file=sys.stderr)
        return 1
    if "__DONE__" not in lines3:
        print("医疗备案: missing __DONE__", file=sys.stderr)
        return 1
    if not any("流程执行完成" in x for x in lines3):
        print("医疗备案: expected completion banner", file=sys.stderr)
        return 1
    print("=== m3 bridge 医疗备案填表 OK ===")
    return 0


def run_test_m4(zhiyu_bin: Optional[str] = None) -> int:
    """HR-5 server reload via subprocess."""
    os.environ["ZHIYU_MOCK"] = "1"
    zhiyu = find_zhiyu_binary(zhiyu_bin)
    base = default_base_dir()
    mod = os.path.join(base, "演示Demo", "热更新_模块.lisp")
    with open(mod, "w", encoding="utf-8") as f:
        f.write('(define hr-v 1)\n')

    proc = subprocess.Popen(
        [zhiyu, "server", "--base-dir", base],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        _send_cmd(proc, {"cmd": "eval", "code": '(load "演示Demo/热更新_模块.lisp") hr-v'})
        v1 = None
        while True:
            line = _read_line(proc.stdout)
            if not line:
                return 1
            if line.startswith("__RESULT__:"):
                v1 = line.split(":", 1)[1]
            if line == "__DONE__":
                break
        if v1 != "1":
            print(f"reload step1 expected 1 got {v1}", file=sys.stderr)
            return 1

        with open(mod, "w", encoding="utf-8") as f:
            f.write('(define hr-v 2)\n')
        _send_cmd(proc, {"cmd": "reload", "path": "演示Demo/热更新_模块.lisp"})
        _read_line(proc.stdout)  # __RELOADED__
        _send_cmd(proc, {"cmd": "eval", "code": "hr-v"})
        v2 = None
        while True:
            line = _read_line(proc.stdout)
            if not line:
                return 1
            if line.startswith("__RESULT__:"):
                v2 = line.split(":", 1)[1]
            if line == "__DONE__":
                break
        if v2 != "2":
            print(f"reload step2 expected 2 got {v2}", file=sys.stderr)
            return 1

        # HR-4: captured proc keeps old behavior after redefine
        _send_cmd(proc, {"cmd": "eval", "code": '(define (f) 1) (let ((saved f)) (begin (define (f) 2) (list (saved) (f))))'})
        hr4 = None
        while True:
            line = _read_line(proc.stdout)
            if not line:
                return 1
            if line.startswith("__RESULT__:"):
                hr4 = line.split(":", 1)[1]
            if line == "__DONE__":
                break
        if hr4 != "(1 2)":
            print(f"HR-4 expected (1 2) got {hr4}", file=sys.stderr)
            return 1
        print("=== m4 HR-4 closure isolation OK ===")
        print("=== m4 server reload OK ===")
        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="zhiyu-core Python host bridge")
    parser.add_argument("--test-m3", action="store_true", help="run M3 bridge acceptance")
    parser.add_argument("--test-m4", action="store_true", help="run M4 hot reload acceptance")
    parser.add_argument("--zhiyu", default=None, help="path to zhiyu binary")
    args = parser.parse_args()
    if args.test_m3:
        sys.exit(run_test_m3(args.zhiyu))
    if args.test_m4:
        sys.exit(run_test_m4(args.zhiyu))
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
