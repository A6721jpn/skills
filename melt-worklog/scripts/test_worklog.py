import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collect import bounds, host_collect, merge, timestamp, write_bundle
from report import import_slack, render, write_sources, check_sources, source_links


class WorklogTest(unittest.TestCase):
    def test_source_links_required_and_resolvable(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sources.html'
            ev={'e1':{'id':'e1','text':'done','agent':'slack','timestamp':'2026-09-24T10:00:00+09:00',
                      'permalink':'https://example.slack.com/archives/C123/p1234567890000000',
                      'origins':[{'host':'Slack','path':'slack.json','locator':'1234567890.000000'}]}}
            task={'id':'t1','project':'Project','title':'Task','evidence_ids':['e1']}
            data={'tasks':[task]}
            write_sources(path,[task],ev)
            citation=' / '.join('['+label+']('+url+')' for label,url in source_links(task,ev,path))
            md='<!-- task:t1 -->\n- Task\n  出典：'+citation+'\n<!-- /task -->'
            self.assertEqual(check_sources(md,data,ev,path)['links_checked'],2)
            for bad in [md.replace('  出典：','  根拠ID：'),
                        md.replace('[Slack]('+ev['e1']['permalink']+')',''),
                        md.replace('#task-t1','#task-other'),
                        md.replace('p1234567890000000','p9999999990000000'),
                        md.replace('<!-- task:t1 -->','')]:
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    check_sources(bad,data,ev,path)
            good=path.read_text(encoding='utf-8')
            for bad in [good.replace('id="task-t1"','id="wrong"'),good.replace('data-evidence="e1"','data-evidence="wrong"')]:
                path.write_text(bad,encoding='utf-8')
                with self.assertRaises(ValueError):check_sources(md,data,ev,path)
            path.unlink()
            with self.assertRaisesRegex(ValueError,'Source file missing'):check_sources(md,data,ev,path)

    def test_invalid_source_url_and_missing_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sources.html'
            task={'id':'t1','project':'P','title':'T','evidence_ids':['e']}
            ev={'e':{'id':'e','text':'done','origins':[]}}
            with self.assertRaisesRegex(ValueError,'provenance missing'):write_sources(path,[task],ev)
            ev['e']['origins']=[{'path':'log.jsonl','locator':1}]
            ev['e']['permalink']='https://example.slack.com.evil.invalid/archives/C1/p123'
            with self.assertRaisesRegex(ValueError,'Invalid Slack'):write_sources(path,[task],ev)

    def test_jst_boundaries(self):
        a, b = bounds("2026-09-24")
        self.assertEqual(a.timestamp(), timestamp("2026-09-23T15:00:00Z").timestamp())
        self.assertTrue(a <= timestamp("2026-09-24T14:59:59Z") < b)
        self.assertFalse(a <= timestamp("2026-09-24T15:00:00Z") < b)

    def test_resumed_old_session_and_role_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "sessions/2026/09/20/old.jsonl"
            path.parent.mkdir(parents=True)
            records = [{"type":"session_meta","payload":{"id":"old-session","cwd":"C:/work"}}]
            for when, role, text in [("2026-09-23T14:59:59Z","user","yesterday"),
                                     ("2026-09-23T15:00:00Z","developer","secret instruction"),
                                     ("2026-09-24T01:00:00Z","user","today request"),
                                     ("2026-09-24T15:00:00Z","assistant","tomorrow")]:
                records.append({"type":"response_item","timestamp":when,"payload":{"type":"message","role":role,"content":[{"type":"text","text":text}]}})
            path.write_text("\n".join(json.dumps(r) for r in records),encoding="utf-8")
            with patch.dict(os.environ, {"CODEX_HOME":temp}):
                result = host_collect("2026-09-24",False)
                self.assertEqual([r["text"] for r in result["evidence"]],["today request"])
                self.assertEqual(host_collect("2026-09-24",False,["old-session"])["evidence"],[])

    def test_duplicate_keeps_origins(self):
        a = {"id":"x","timestamp":"now","origins":[{"source":"codex"}]}
        b = {"id":"x","timestamp":"now","origins":[{"source":"orca"}]}
        result = merge([a,b])
        self.assertEqual(len(result),1)
        self.assertEqual(len(result[0]["origins"]),2)

    def test_antigravity_sessions_and_thinking(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"AppData/Roaming/orca").mkdir(parents=True)
            for sid in ["session-a","session-b"]:
                p=root/".gemini/antigravity-cli/brain"/sid/".system_generated/logs/transcript.jsonl"
                p.parent.mkdir(parents=True)
                p.write_text(json.dumps({"type":"PLANNER_RESPONSE","created_at":"2026-09-24T03:00:00Z","thinking":"private","content":"result"}),encoding="utf-8")
            with patch("collect.Path.home", return_value=root), patch.dict(os.environ,{"APPDATA":str(root/"AppData/Roaming"),"CODEX_HOME":str(root/".codex")}):
                result=host_collect("2026-09-24",True)
            self.assertEqual({r["session"] for r in result["evidence"]},{"session-a","session-b"})
            self.assertTrue(all(r["text"]=="result" for r in result["evidence"]))

    def test_slack_pagination_and_timezone(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            write_bundle(root,"2026-09-24",[])
            a,b=bounds("2026-09-24")
            messages=[{"channel_id":"C1","ts":str(t.timestamp()),"text":"m","user":"me"} for t in [a-dt.timedelta(seconds=1),a,b]]
            path=root/"slack.json"
            path.write_text(json.dumps({"query":"from:me after:x before:y","result":{"page":1,"pages":2,"messages":messages}}))
            import_slack(root,[path])
            manifest=json.loads((root/"manifest.json").read_text())
            self.assertEqual(manifest["slack"]["status"],"partial")
            self.assertEqual(manifest["slack"]["missing_pages"],{"from:me after:x before:y":[2]})
            self.assertEqual(len((root/"evidence.jsonl").read_text().splitlines()),1)

    def test_zero_slack_is_success_and_context_not_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            write_bundle(root,"2026-09-24",[])
            paths=[]
            for i,query in enumerate(["from:me after:x before:y","to:me after:x before:y"]):
                path=root/f"slack{i}.json"
                path.write_text(json.dumps({"query":query,"result":{"page":1,"pages":0,"messages":[],"total":0}}))
                paths.append(path)
            import_slack(root,paths)
            self.assertEqual(json.loads((root/"manifest.json").read_text())["slack"]["status"],"collected")
            r={"id":"ctx","timestamp":None,"time_basis":"session_context","kind":"assistant","text":"done","origins":[]}
            (root/"evidence.jsonl").write_text(json.dumps(r))
            tasks={"date":"2026-09-24","tasks":[{"id":"1","status":"completed","confidence":"reported","evidence_ids":["ctx"]}]}
            path=root/"tasks.json";path.write_text(json.dumps(tasks))
            with self.assertRaisesRegex(ValueError,"Context-only"):
                render(root,path,root/"out")

    def test_request_does_not_prove_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_bundle(root,"2026-09-24",[])
            r={"id":"request","timestamp":"2026-09-24T10:00:00+09:00","time_basis":"event","kind":"user","text":"please do X","origins":[]}
            (root/"evidence.jsonl").write_text(json.dumps(r))
            path=root/"tasks.json"
            path.write_text(json.dumps({"date":"2026-09-24","tasks":[{"id":"1","status":"completed","confidence":"reported","evidence_ids":["request"]}]}))
            with self.assertRaisesRegex(ValueError,"Requests or starts"):
                render(root,path,root/"out")


if __name__ == "__main__":
    unittest.main()
