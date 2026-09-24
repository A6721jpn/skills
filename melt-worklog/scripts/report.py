"""Import Melt Connect evidence, inspect a bundle, validate and render AI-authored tasks."""
import argparse
import collections
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from collect import JST, bounds, clean, timestamp, merge


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_evidence(bundle):
    return [json.loads(x) for x in (bundle / "evidence.jsonl").read_text(encoding="utf-8").splitlines() if x]


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def slack_url(record):
    url = record.get("permalink")
    if not url:
        return None
    p = urlsplit(url)
    if (p.scheme != "https" or not p.hostname or not p.hostname.endswith(".slack.com")
            or p.username or p.password or not re.fullmatch(r"/archives/[A-Z0-9]+/p[0-9]+", p.path)
            or any(c in url for c in '\n\r<>"()')):
        raise ValueError("Invalid Slack source URL: " + record["id"])
    return url


def source_links(task, evidence, source_path):
    links = [("ログ・根拠", source_path.name + "#task-" + task["id"])]
    for eid in task["evidence_ids"]:
        url = slack_url(evidence[eid])
        if url and url not in [u for _, u in links]:
            links.append(("Slack", url))
    return links


def write_sources(path, tasks, evidence):
    parts = ['<!doctype html><html lang="ja"><meta charset="utf-8"><title>日報の出典</title>',
             '<style>body{max-width:900px;margin:40px auto;padding:0 20px;font:16px/1.7 sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f4f4;padding:16px}section{margin:48px 0}small{overflow-wrap:anywhere}</style>',
             '<h1>日報の出典</h1><p>収集時点のログ抜粋。元のホスト・ファイル・位置を併記しています。</p>']
    for task in tasks:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", task["id"]):
            raise ValueError("Task id must be safe for a source anchor")
        parts.append('<section id="task-'+task['id']+'"><h2>'+html.escape(task['project']+'：'+task['title'])+'</h2>')
        for eid in dict.fromkeys(task["evidence_ids"]):
            r = evidence[eid]
            if not r.get("origins") or any(not o.get("path") or o.get("locator") is None for o in r["origins"]):
                raise ValueError("Source provenance missing: " + eid)
            parts.append('<article data-evidence="'+html.escape(eid, quote=True)+'"><h3>'+html.escape(r.get('agent','')+' / '+str(r.get('timestamp') or '日時不明'))+'</h3>')
            url = slack_url(r)
            if url:
                parts.append('<p><a href="'+html.escape(url,quote=True)+'">Slackの元投稿</a></p>')
            for origin in r["origins"]:
                parts.append('<small>'+html.escape(str(origin.get('host',''))+' / '+str(origin['path'])+' / '+str(origin['locator']))+'</small><br>')
            parts.append('<pre>'+html.escape(r['text'])+'</pre></article>')
        parts.append('</section>')
    path.write_text('\n'.join(parts)+'</html>', encoding='utf-8')


def check_sources(markdown, data, evidence, source_path):
    """Check actual rendered task citation lines and their exact expected targets."""
    if not source_path.is_file():
        raise ValueError("Source file missing")
    source = source_path.read_text(encoding='utf-8')
    blocks = re.findall(r'<!-- task:([A-Za-z0-9_-]+) -->\n(.*?)<!-- /task -->', markdown, re.S)
    expected_ids = [t['id'] for t in data['tasks']]
    actual_ids = [key for key, _ in blocks]
    if sorted(actual_ids) != sorted(expected_ids):
        raise ValueError("Missing or duplicate task source blocks")
    by_id = dict(blocks)
    checked = 0
    for task in data['tasks']:
        block = by_id[task['id']]
        lines = re.findall(r'^  出典：(.*)$', block, re.M)
        if len(lines) != 1:
            raise ValueError("Missing source links: " + task['id'])
        links = re.findall(r'\[[^\]\n]+\]\(([^\s)]+)\)', lines[0])
        expected = [u for _, u in source_links(task, evidence, source_path)]
        if set(links) != set(expected):
            raise ValueError("Source links missing or mismatched: " + task['id'])
        section = re.search(r'<section id="task-'+re.escape(task['id'])+r'">(.*?)</section>', source, re.S)
        if not section:
            raise ValueError("Source anchor missing: " + task['id'])
        ids = re.findall(r'<article data-evidence="([^"]+)">', section[1])
        if set(ids) != set(task['evidence_ids']):
            raise ValueError("Source evidence mismatch: " + task['id'])
        checked += len(links)
    return {"status": "passed", "tasks_checked": len(expected_ids), "links_checked": checked,
            "scope": "Markdown citation presence, exact targets, local file/anchor and evidence ID mapping; external HTTP availability not checked."}


def import_slack(bundle, paths):
    manifest = read_json(bundle / "manifest.json")
    start, end = bounds(manifest["date"])
    records = read_evidence(bundle)
    query_pages = collections.defaultdict(set)
    page_counts = {}
    seen_queries = []
    failures = []
    count = 0
    # All imported data must be actual Melt Connect results, not reconstructed summaries.
    for path in paths:
        envelope = read_json(path)
        query, result = envelope["query"], envelope["result"]
        seen_queries.append(query)
        if isinstance(result, dict) and (result.get("error") or "messages" not in result):
            failures.append({"query": query, "error": str(result)[:500]})
            continue
        messages = result if isinstance(result, list) else result["messages"]
        if isinstance(result, dict) and "page" in result:
            query_pages[query].add(int(result["page"]))
            page_counts[query] = max(1, int(result.get("pages", 1)))
        is_thread = query.startswith("thread:")
        channel_id = query.split(":")[1] if is_thread else ""
        for msg in messages:
            at = timestamp(msg.get("ts"))
            if not at:
                failures.append({"query": query, "error": "Message missing valid ts"})
                continue
            in_day = start <= at < end
            if not in_day and not is_thread:
                continue
            channel = msg.get("channel_id", channel_id)
            identity = f"slack|{channel}|{msg['ts']}"
            r = {"id": hashlib.sha256(identity.encode()).hexdigest()[:20], "host": "Slack", "source": "slack", "agent": "slack",
                 "session": channel+":"+str(msg.get("thread_ts", msg["ts"])), "timestamp": at.astimezone(JST).isoformat(),
                 "time_basis": "event" if in_day else "thread_context", "kind": "slack_message", "text": clean(msg.get("text", "")),
                 "cwd": "", "author": msg.get("user"), "self_authored": query.startswith("from:me "),
                 "permalink": msg.get("permalink"), "channel": msg.get("channel", channel),
                 "files": [{"id": f.get("id"), "name": f.get("name")} for f in msg.get("files", [])],
                 "origins": [{"host": "Slack", "source": "slack", "path": str(Path(path).resolve()), "locator": str(msg["ts"]), "query": query}]}
            prior = next((x for x in records if x["id"] == r["id"]), None)
            if prior:
                # Thread fetch can carry edits newer than search cache. Preserve provenance.
                prior["self_authored"] = prior.get("self_authored", False) or r["self_authored"]
                prior["text"] = r["text"]
                prior["permalink"] = r["permalink"] or prior.get("permalink")
                prior["origins"].extend(o for o in r["origins"] if o not in prior["origins"])
            else:
                records.append(r)
                count += 1
    missing = {q: sorted(set(range(1,n+1)) - query_pages[q]) for q,n in page_counts.items() if len(query_pages[q]) < n}
    has_self = any(q.startswith("from:me ") for q in seen_queries)
    has_inbound = any(q.startswith("to:me ") for q in seen_queries)
    complete = has_self and has_inbound and not failures and not missing
    manifest["slack"] = {"status": "collected" if complete else "partial", "queries": seen_queries, "missing_pages": missing,
                          "errors": failures, "self_search": has_self, "inbound_search": has_inbound,
                          "scope": "Visible self-authored messages, to:me search, and selected related threads; not all workspace activity."}
    records = merge(records)
    manifest["records"] = len(records)
    (bundle / "evidence.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records), encoding="utf-8")
    save_json(bundle / "manifest.json", manifest)
    print(json.dumps({"added": count, "status": manifest["slack"]["status"], "missing_pages": missing}))


def render(bundle, tasks_path, out):
    manifest = read_json(bundle / "manifest.json")
    data = read_json(tasks_path)
    evidence = {r["id"]: r for r in read_evidence(bundle)}
    if data.get("date") != manifest["date"]:
        raise ValueError("Task date must match evidence date")
    tasks = data["tasks"]
    statuses = {"completed": "実施済み", "in_progress": "進行中", "planned": "予定", "blocked": "保留", "uncertain": "要確認"}
    confidence = {"confirmed": "ログで確認", "reported": "本人・AIの報告", "inferred": "推定"}
    seen = set()
    for task in tasks:
        if task["id"] in seen:
            raise ValueError("Duplicate task id")
        seen.add(task["id"])
        if task["status"] not in statuses or task["confidence"] not in confidence:
            raise ValueError("Invalid task status/confidence")
        refs = task.get("evidence_ids", [])
        if not refs or any(x not in evidence for x in refs):
            raise ValueError("Each task requires existing evidence IDs: " + task["id"])
        timed = [evidence[x] for x in refs if evidence[x]["time_basis"] not in ("session_context", "thread_context")]
        if not timed:
            raise ValueError("Context-only evidence cannot establish a daily task: " + task["id"])
        if task["status"] == "completed" and task["confidence"] == "inferred":
            raise ValueError("An inferred task cannot be labeled completed")
        if task["confidence"] == "confirmed" and not any(r["kind"] in ("tool_result", "tool_completed", "task_completed") for r in timed):
            raise ValueError("Confirmed work needs an execution-result reference")
        if task["status"] == "completed" and not any(r["kind"] not in ("user", "tool_call", "turn_started", "task_created") for r in timed):
            raise ValueError("Requests or starts alone cannot establish completion")
    out.mkdir(parents=True, exist_ok=True)
    # Versioned output: retain older daily drafts and runs.
    stamp = dt.datetime.now(JST).strftime("%H%M%S-%f")
    prefix = manifest["date"]+"-"+stamp
    selected = {eid: evidence[eid] for t in tasks for eid in t["evidence_ids"]}
    evidence_path = out / (prefix+"-evidence.json")
    save_json(evidence_path, {"manifest": manifest, "evidence": list(selected.values())})
    task_path = out / (prefix+"-tasks.json")
    save_json(task_path, data)
    source_path = out / (prefix+"-sources.html")
    write_sources(source_path, tasks, selected)
    md = ["# 作業日報 — "+manifest["date"], "", "日本時間・"+manifest["collected_at"][11:16]+"時点。AIの実行と本人の報告を集約。", ""]
    if data.get("summary"):
        md += [data["summary"], ""]
    for status, label in statuses.items():
        group = [t for t in tasks if t["status"] == status]
        if not group:
            continue
        md += ["## "+label, ""]
        for t in group:
            mark = "（推定）" if t["confidence"] == "inferred" else ""
            md += ["<!-- task:"+t['id']+" -->", "- **"+t["project"]+"："+t["title"]+"**"+mark+"  ", "  "+t.get("brief", t["outcome"])+"  ",
                   "  出典："+" / ".join('['+label+']('+url+')' for label,url in source_links(t,selected,source_path)), "<!-- /task -->", ""]
    md += ["## 補足", "", "両PCのCodex・Orca関連ログとSlackを集約。個別の根拠・次の対応は末尾のJSONに保存。"]
    if manifest["slack"]["status"] != "collected":
        md.append("Slack取得状態："+manifest["slack"]["status"]+"（不足あり）。")
    for cov in manifest["coverage"]:
        if cov.get("errors") or cov.get("malformed_lines"):
            md.append("- "+cov["host"]+"：収集エラー "+str(len(cov.get("errors", [])))+"件、読めなかった行 "+str(cov.get("malformed_lines", 0))+"件。詳細は根拠ファイルを参照。")
    for note in data.get("brief_limitations", data.get("limitations", [])):
        md.append("- "+note)
    md += ["", "[根拠と収集状況]("+evidence_path.name+") · [タスク一覧JSON]("+task_path.name+")", ""]
    report = out / (prefix+"-日報.md")
    rendered = "\n".join(md)
    result = check_sources(rendered, data, selected, source_path)
    report.write_text(rendered, encoding="utf-8")
    save_json(out / (prefix+"-source-check.json"), result)
    print(str(report.resolve()))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("import-slack")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--input", type=Path, action="append", required=True)
    s = sub.add_parser("inspect")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--session")
    s.add_argument("--source")
    s.add_argument("--kind", action="append")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--chars", type=int, default=2500)
    s = sub.add_parser("render")
    s.add_argument("--bundle", type=Path, required=True)
    s.add_argument("--tasks", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("check-sources")
    s.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    if a.cmd == "check-sources":
        prefix = a.report.name.removesuffix('-日報.md')
        data = read_json(a.report.with_name(prefix+'-tasks.json'))
        ev = read_json(a.report.with_name(prefix+'-evidence.json'))
        result = check_sources(a.report.read_text(encoding='utf-8'), data, {r['id']:r for r in ev['evidence']}, a.report.with_name(prefix+'-sources.html'))
        print(json.dumps(result, ensure_ascii=False))
    elif a.cmd == "import-slack":
        import_slack(a.bundle, a.input)
    elif a.cmd == "render":
        render(a.bundle, a.tasks, a.out)
    else:
        rows = [r for r in read_evidence(a.bundle) if (not a.session or r["session"] == a.session) and
                (not a.source or r["source"] == a.source) and (not a.kind or r["kind"] in a.kind)]
        print(json.dumps({"total": len(rows), "offset": a.offset, "records": [{**r, "text":r["text"][:a.chars]} for r in rows[a.offset:a.offset+a.limit]]},ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
