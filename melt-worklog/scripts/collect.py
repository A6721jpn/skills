"""Read-only, standard-library evidence collector. Remote code runs over SSH stdin."""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
from urllib.parse import unquote

JST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc


def timestamp(value):
    if value is None:
        return None
    try:
        if isinstance(value, (float, int)) or re.fullmatch(r"\d{10}(?:\.\d+)?", str(value)):
            n = float(value)
            return dt.datetime.fromtimestamp(n / 1000 if n > 1e12 else n, UTC)
        v = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def bounds(day):
    start = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(), JST)
    return start, start + dt.timedelta(days=1)


def clean(text):
    text = re.sub(r"data:[^\s;]+;base64,[A-Za-z0-9+/=]+", "[media omitted]", str(text))
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]+)\b", "[credential redacted]", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*[\"']?bearer\s+)[^\s\"']+", r"\1[redacted]", text)
    text = re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\s*[\"']?\s*[:=]\s*[\"']?)[^\s\"',}]+", r"\1[redacted]", text)
    return text


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") in ("text", "input_text", "output_text"))
    return ""


def user_text(text):
    # Environment/skill bootstrap isn't user work. Keep an actual request following it.
    for tag in ("environment_context", "INSTRUCTIONS", "system-reminder", "user_info", "rules"):
        text = re.sub(r"<" + tag + r"\b[^>]*>.*?</" + tag + ">", "", text, flags=re.S)
    if "## My request:" in text:
        text = text.split("## My request:", 1)[1]
    if text.lstrip().startswith(("# AGENTS.md instructions", "<permissions instructions>", "<recommended_plugins>")):
        return ""
    return text.strip()


def rows(path, diagnostics):
    try:
        with path.open("rb") as f:
            size = os.fstat(f.fileno()).st_size
            line = 0
            while f.tell() < size:
                data = f.readline(size - f.tell())
                line += 1
                try:
                    yield line, json.loads(data)
                except (ValueError, UnicodeDecodeError):
                    diagnostics["malformed_lines"] += 1
    except OSError as exc:
        diagnostics["errors"].append({"path": str(path), "error": str(exc)})


def host_collect(day, include_orca=True, exclude_sessions=()):
    start, end = bounds(day)
    host = socket.gethostname()
    home = Path.home()
    orca = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "orca"
    evidence = []
    diagnostics = {"host": host, "errors": [], "malformed_lines": 0, "files_scanned": 0, "roots": [], "limitations": []}
    seen_files = set()

    def add(source, agent, session, path, locator, when, kind, text, cwd="", basis="event", **extra):
        at = timestamp(when)
        if basis != "session_context" and (not at or not start <= at < end):
            return
        if session in exclude_sessions or not text:
            return
        text = clean(text)
        full_length = len(text)
        cap = 16000 if kind in ("assistant_final", "user") else 6000
        if full_length > cap:
            text = text[:cap] + "\n[truncated: inspect source for details]"
        identity = f"{agent}|{session}|{when}|{kind}|{text}"
        evidence.append({"id": hashlib.sha256(identity.encode()).hexdigest()[:20], "host": host,
                         "source": source, "agent": agent, "session": session, "timestamp": at.astimezone(JST).isoformat() if at else None,
                         "time_basis": basis, "kind": kind, "text": text, "cwd": cwd,
                         "truncated": full_length > cap, "original_chars": full_length,
                         "origins": [{"host": host, "source": source, "path": str(path), "locator": locator}], **extra})

    def parse_jsonl(path, source, agent, hint=None):
        key = str(path.resolve()).lower()
        if key in seen_files:
            return
        seen_files.add(key)
        try:
            if path.stat().st_mtime < start.timestamp():
                return
        except OSError as exc:
            diagnostics["errors"].append({"path": str(path), "error": str(exc)})
            return
        diagnostics["files_scanned"] += 1
        session = (hint or {}).get("sessionId", path.stem)
        if agent == "antigravity" and path.name == "transcript.jsonl":
            session = (hint or {}).get("sessionId", path.parents[2].name)
        cwd = (hint or {}).get("cwd") or ""
        calls = {}
        for line, r in rows(path, diagnostics):
            when = r.get("timestamp") or r.get("ts") or r.get("created_at")
            typ = r.get("type")
            p = r.get("payload") or {}
            if typ == "session_meta":
                session, cwd = p.get("id", session), p.get("cwd", cwd)
                continue
            session = r.get("sessionId", session)
            cwd = r.get("cwd", cwd)
            if session in exclude_sessions:
                return
            if agent == "codex":
                if typ == "response_item":
                    pt = p.get("type")
                    if pt == "message" and p.get("role") in ("user", "assistant"):
                        role = p["role"]
                        text = text_content(p.get("content"))
                        if role == "user":
                            text = user_text(text)
                        kind = "assistant_final" if role == "assistant" and p.get("phase") == "final_answer" else role
                        add(source, agent, session, path, line, when, kind, text, cwd)
                    elif pt in ("function_call", "custom_tool_call"):
                        name = p.get("name", "tool")
                        calls[p.get("call_id")] = name
                        add(source, agent, session, path, line, when, "tool_call", name + "\n" + str(p.get("arguments", p.get("input", ""))), cwd, call_id=p.get("call_id"))
                    elif pt in ("function_call_output", "custom_tool_call_output"):
                        output = p.get("output", "")
                        # Tool image/audio payloads are not useful for daily task extraction.
                        text = output if isinstance(output, str) else text_content(output)
                        add(source, agent, session, path, line, when, "tool_result", calls.get(p.get("call_id"), "tool") + "\n" + text, cwd, call_id=p.get("call_id"))
                elif typ == "event_msg" and p.get("type") in ("task_complete", "turn_aborted"):
                    add(source, agent, session, path, line, when, p["type"], p.get("last_agent_message") or p["type"], cwd)
            elif agent == "antigravity":
                if typ == "USER_INPUT":
                    text = text_content(r.get("content", ""))
                    match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", text, re.S)
                    add(source, agent, session, path, line, when, "user", user_text(match.group(1) if match else text), cwd)
                elif typ == "PLANNER_RESPONSE":
                    # Never collect the private thinking field.
                    add(source, agent, session, path, line, when, "assistant", text_content(r.get("content", "")), cwd)
                    for call in r.get("tool_calls", []):
                        add(source, agent, session, path, line, when, "tool_call", call.get("name", "tool")+"\n"+json.dumps(call.get("args", {}),ensure_ascii=False), cwd)
                elif typ == "GENERIC":
                    add(source, agent, session, path, line, when, "tool_result", text_content(r.get("content", "")), cwd)
            else:
                message = r.get("message") if isinstance(r.get("message"), dict) else r
                role = message.get("role", typ)
                if role in ("user", "assistant"):
                    text = text_content(message.get("content", message.get("text", "")))
                    if role == "user":
                        text = user_text(text)
                    add(source, agent, session, path, line, when, role, text, cwd)
                    for block in message.get("content", []) if isinstance(message.get("content"), list) else []:
                        if block.get("type") == "tool_result":
                            add(source, agent, session, path, line, when, "tool_result", text_content(block.get("content")), cwd, call_id=block.get("tool_use_id"))
                        elif block.get("type") == "tool_use":
                            add(source, agent, session, path, line, when, "tool_call", block.get("name", "tool") + "\n" + json.dumps(block.get("input", {}), ensure_ascii=False), cwd, call_id=block.get("id"))

    def scan(root, pattern, source, agent):
        diagnostics["roots"].append({"path": str(root), "exists": root.exists(), "source": source})
        if root.exists():
            for path in root.rglob(pattern):
                parse_jsonl(path, source, agent)

    codex_home = Path(os.environ.get("CODEX_HOME", str(home / ".codex")))
    for name in ("sessions", "archived_sessions"):
        scan(codex_home / name, "*.jsonl", "codex", "codex")
    if include_orca and orca.exists():
        for account in (orca / "codex-accounts").glob("*/home"):
            for name in ("sessions", "archived_sessions"):
                scan(account / name, "*.jsonl", "orca", "codex")
        for name in ("sessions", "archived_sessions"):
            scan(orca / "codex-runtime-home/home" / name, "*.jsonl", "orca", "codex")
        # Orca's vault is discovery metadata only: previews may be stale or truncated.
        cache = orca / "ai-vault/session-parse-cache.json"
        if cache.exists():
            try:
                entries = json.loads(cache.read_text(encoding="utf-8-sig")).get("entries", [])
                for path, value in entries:
                    s = value.get("session") or {}
                    if not Path(path).exists():
                        if (timestamp(s.get("updatedAt")) or start - dt.timedelta(days=1)) >= start:
                            diagnostics["errors"].append({"path": path, "error": "Recent vault transcript missing"})
                        continue
                    if s.get("agent") in ("codex", "claude", "antigravity", "omp") and Path(path).suffix == ".jsonl":
                        parse_jsonl(Path(path), "orca", s["agent"], s)
            except (ValueError, OSError, TypeError) as exc:
                diagnostics["errors"].append({"path": str(cache), "error": str(exc)})
        # Underlying native agent logs cover fresh sessions not yet in the vault cache.
        # The association with Orca is not proven; label it explicitly.
        for root, pattern, agent in [(home / ".claude/projects", "*.jsonl", "claude"),
                                      (home / ".gemini/antigravity-cli/brain", "transcript.jsonl", "antigravity"),
                                      (home / ".omp/agent/sessions", "*.jsonl", "omp")]:
            scan(root, pattern, "orca_related_native", agent)
        for path in (home / ".grok/sessions").rglob("events.jsonl"):
            if path.stat().st_mtime < start.timestamp():
                continue
            session = path.parent.name
            cwd = unquote(path.parent.parent.name)
            active = False
            for line, r in rows(path, diagnostics):
                at = timestamp(r.get("ts"))
                if at and start <= at < end and r.get("type") in ("turn_started", "turn_ended", "tool_completed"):
                    active = True
                    add("orca_related_native", "grok", session, path, line, r["ts"], r["type"], json.dumps(r, ensure_ascii=False), cwd)
            # Grok chat_history lacks timestamps. Never assign file mtime as event time.
            chat = path.with_name("chat_history.jsonl")
            if active and chat.exists():
                for line, r in rows(chat, diagnostics):
                    if r.get("type") in ("user", "assistant"):
                        text = text_content(r.get("content"))
                        if r["type"] == "user":
                            text = user_text(text)
                        add("orca_related_native", "grok", session, chat, line, None, r["type"], text, cwd, basis="session_context")
        database = orca / "orchestration.db"
        if database.exists():
            try:
                con = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
                con.row_factory = sqlite3.Row
                con.execute("PRAGMA query_only=ON")
                a, z = (x.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S") for x in (start, end))
                with con:
                    for row in con.execute("SELECT id,run_id,task_title,spec,status,result,created_at,completed_at FROM tasks WHERE (created_at>=? AND created_at<?) OR (completed_at>=? AND completed_at<?)", (a,z,a,z)):
                        r = dict(row)
                        for field in ("created_at", "completed_at"):
                            at = timestamp(r[field])
                            if at and start <= at < end:
                                add("orca", "orchestration", r["run_id"], database, "tasks:"+r["id"]+":"+field, r[field], "task_created" if field=="created_at" else "task_completed", json.dumps(r,ensure_ascii=False), basis="sqlite_utc")
                    for row in con.execute("SELECT id,run_id,from_handle,to_handle,subject,body,type,created_at FROM messages WHERE created_at>=? AND created_at<?", (a,z)):
                        r = dict(row)
                        add("orca", "orchestration", r["run_id"], database, "messages:"+r["id"], r["created_at"], "orchestration_message", json.dumps(r,ensure_ascii=False), basis="sqlite_utc")
                con.close()
            except (sqlite3.Error, OSError) as exc:
                diagnostics["errors"].append({"path": str(database), "error": str(exc)})
        diagnostics["limitations"].extend([
            "Orca terminal-history OCKL binary output is not decoded; native agent transcripts and orchestration records are used.",
            "orca_related_native means a native agent on the Orca host, not a verified Orca launch.",
            "Grok chat text has no per-message timestamp: session_context is context only, not proof of work on the target day.",
            "Vault discovery can be stale; unsupported agents and missing native transcripts may leave gaps."])
    elif include_orca:
        diagnostics["errors"].append({"path": str(orca), "error": "Orca data directory missing"})
    return {"evidence": evidence, "coverage": diagnostics}


def merge(records):
    unique = {}
    for r in records:
        if r["id"] in unique:
            for origin in r["origins"]:
                if origin not in unique[r["id"]]["origins"]:
                    unique[r["id"]]["origins"].append(origin)
        else:
            unique[r["id"]] = r
    return sorted(unique.values(), key=lambda r: (r["timestamp"] or "", r["id"]))


def write_bundle(out, day, results):
    out.mkdir(parents=True, exist_ok=True)
    records = merge([r for result in results for r in result.get("evidence", [])])
    (out / "evidence.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in records), encoding="utf-8")
    manifest = {"schema_version": 1, "date": day, "timezone": "Asia/Tokyo", "collected_at": dt.datetime.now(JST).isoformat(),
                "records": len(records), "coverage": [x["coverage"] for x in results], "slack": {"status": "not_collected"}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sessions = collections.defaultdict(list)
    for r in records:
        sessions[(r["agent"], r["session"])].append(r)
    index = []
    for (agent, session), rs in sessions.items():
        msgs = [r for r in rs if r["kind"] in ("user", "assistant", "assistant_final", "task_complete", "task_completed", "orchestration_message")]
        index.append({"agent": agent, "session": session, "cwd": next((r["cwd"] for r in rs if r["cwd"]), ""), "records": len(rs),
                      "hosts": sorted({r["host"] for r in rs}), "first": next((r["timestamp"] for r in rs if r["timestamp"]), None),
                      "last": next((r["timestamp"] for r in reversed(rs) if r["timestamp"]), None),
                      "first_messages": [{"id": r["id"], "kind": r["kind"], "text": r["text"][:700]} for r in msgs[:2]],
                      "last_messages": [{"id": r["id"], "kind": r["kind"], "text": r["text"][:1600]} for r in msgs[-2:]]})
    (out / "sessions.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.datetime.now(JST).date().isoformat())
    parser.add_argument("--out", required=True)
    parser.add_argument("--remote", default="dpc-019", help="SSH alias; empty string skips remote")
    parser.add_argument("--remote-python", default="python")
    parser.add_argument("--exclude-session", action="append", default=[])
    args = parser.parse_args()
    bounds(args.date)
    results = [host_collect(args.date, include_orca=False, exclude_sessions=args.exclude_session)]
    if args.remote:
        # stdin carries code, not a remote file or shell-generated command; never modifies source logs.
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.remote) or args.remote.startswith("-"):
            parser.error("Invalid SSH alias")
        if not re.fullmatch(r"[A-Za-z0-9_./:-]+", args.remote_python):
            parser.error("Use a Python command/path without spaces")
        src = Path(__file__).read_text(encoding="utf-8").split('\nif __name__ == "__main__":')[0]
        src += "\nprint(json.dumps(host_collect("+repr(args.date)+", True, "+repr(args.exclude_session)+"), ensure_ascii=True))\n"
        try:
            run = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", args.remote, args.remote_python, "-"],
                                 input=src.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
            if run.returncode:
                raise RuntimeError(run.stderr.decode("utf-8", "replace")[:1200])
            results.append(json.loads(run.stdout))
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            results.append({"coverage": {"host": args.remote, "errors": [{"error": str(exc)}]}, "evidence": []})
    manifest = write_bundle(Path(args.out), args.date, results)
    print(json.dumps({"date": args.date, "records": manifest["records"], "hosts": [{"host": c["host"], "errors": len(c.get("errors", [])), "files_scanned": c.get("files_scanned")} for c in manifest["coverage"]]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
