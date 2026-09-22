#!/usr/bin/env python3
"""JP-LLM-LINT API をラップする最小クライアント（標準ライブラリのみ）。

使い方:
  python rewrite.py < draft.txt            # 書き直した本文を標準出力へ（失敗時は原文をそのまま出力）
  python rewrite.py --file draft.txt --json  # API の応答 JSON をそのまま出力
  python rewrite.py --health                 # 稼働確認

環境変数:
  JPLLMLINT_URL      既定 http://hub:8765（Tailscale MagicDNS。IP 指定も可）
  JPLLMLINT_TIMEOUT  秒。既定 180

終了コード: 0 = 書き直し成功、2 = フォールバック（原文を出力）、3 = 接続失敗・エラー（原文を出力）
標準エラーに 1 行だけ状態を出す（本文は出さない）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://hub:8765"  # Tailscale MagicDNS 名。IP で指定するなら JPLLMLINT_URL=http://100.91.209.1:8765


def call(path: str, payload: dict | None, timeout: float) -> dict:
    base = os.environ.get("JPLLMLINT_URL", DEFAULT_URL).rstrip("/")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="入力ファイル（UTF-8）。省略時は標準入力")
    ap.add_argument("--json", action="store_true", help="API 応答の JSON をそのまま出力")
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("JPLLMLINT_TIMEOUT", "180")))
    a = ap.parse_args()
    for s in (sys.stdin, sys.stdout, sys.stderr):  # Windows の cp932 既定を避け、入出力とも UTF-8 に固定
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if a.health:
        try:
            print(json.dumps(call("/health", None, 10), ensure_ascii=False))
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"jp-llm-lint: health failed: {type(e).__name__}", file=sys.stderr)
            return 3
    text = open(a.file, encoding="utf-8").read() if a.file else sys.stdin.read()
    if not text.strip():
        return 0
    try:
        r = call("/rewrite", {"text": text}, a.timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        print(f"jp-llm-lint: unavailable ({type(e).__name__}); returning original", file=sys.stderr)
        sys.stdout.write(text)
        return 3
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0 if not r.get("fallback") else 2
    if r.get("fallback") or not r.get("changed"):
        reasons = ",".join((r.get("guard") or {}).get("reasons") or []) or "unchanged"
        print(f"jp-llm-lint: fallback ({reasons}); returning original", file=sys.stderr)
        sys.stdout.write(text)
        return 2
    print(f"jp-llm-lint: rewritten ({round(r.get('latency_ms', 0))} ms)", file=sys.stderr)
    sys.stdout.write(r["rewritten"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
