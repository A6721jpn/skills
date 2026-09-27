import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import collect


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"CODEX_HOME": str(self.root)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def config(self, data):
        path = self.root / 'private/melt-worklog.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_missing_default_is_local_only(self):
        self.assertEqual(collect.load_settings(), {})

    def test_private_config_and_explicit_override(self):
        self.config({'remote': 'workstation', 'remote_python': 'python3'})
        self.assertEqual(collect.load_settings()['remote'], 'workstation')
        other = self.root / 'other.json'
        other.write_text('{"remote":"alternate"}', encoding='utf-8')
        with patch.dict(os.environ, {'MELT_WORKLOG_CONFIG': str(other)}):
            self.assertEqual(collect.load_settings()['remote'], 'alternate')
            self.assertEqual(collect.load_settings(self.root / 'private/melt-worklog.json')['remote'], 'workstation')

    def test_bad_config_does_not_silently_skip_remote(self):
        for value in [[], {'remote': []}, {'unknown': 'value'}]:
            self.config(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                collect.load_settings()
        with self.assertRaises(ValueError):
            collect.load_settings(self.root / 'missing.json')

    def run_main(self, extra=()):
        local = {'evidence': [], 'coverage': {'host': 'local', 'errors': [], 'limitations': []}}
        remote = {'evidence': [], 'coverage': {'host': 'remote', 'errors': [], 'limitations': []}}
        command = ['collect.py', '--date', '2026-01-02', '--out', str(self.root / 'bundle'), *extra]
        with patch('sys.argv', command), patch('collect.host_collect', return_value=local) as host, \
                patch('collect.subprocess.run') as run, contextlib.redirect_stdout(io.StringIO()):
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps(remote).encode()
            collect.main()
        return host, run, json.loads((self.root / 'bundle/manifest.json').read_text())

    def test_cli_uses_private_remote_and_preserves_ssh_controls(self):
        self.config({'remote': 'workstation', 'remote_python': 'python3'})
        _, run, manifest = self.run_main()
        argv = run.call_args.args[0]
        self.assertEqual(argv[-3:], ['workstation', 'python3', '-'])
        self.assertIn('BatchMode=yes', argv)
        self.assertNotIn('StrictHostKeyChecking=no', argv)
        self.assertEqual(len(manifest['coverage']), 2)

    def test_cli_can_disable_or_override_remote(self):
        self.config({'remote': 'workstation'})
        _, run, manifest = self.run_main(['--remote', ''])
        run.assert_not_called()
        self.assertTrue(manifest['coverage'][0]['limitations'])
        _, run, _ = self.run_main(['--remote', 'alternate', '--remote-python', 'python3'])
        self.assertEqual(run.call_args.args[0][-3:], ['alternate', 'python3', '-'])

    def test_invalid_alias_stops_before_collection(self):
        self.config({'remote': '-oProxyCommand=example'})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            self.run_main()
        self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
