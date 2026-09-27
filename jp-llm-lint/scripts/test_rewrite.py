import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import rewrite


class PrivateSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'CODEX_HOME': str(self.root)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def config(self, value):
        path = self.root / 'private/jp-llm-lint.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def test_private_url_and_environment_override(self):
        self.config({'url': 'http://localhost:8765/'})
        self.assertEqual(rewrite.service_url(), 'http://localhost:8765')
        with patch.dict(os.environ, {'JPLLMLINT_URL': 'http://localhost:9999'}):
            self.assertEqual(rewrite.service_url(), 'http://localhost:9999')

    def test_custom_file(self):
        path = self.root / 'custom.json'
        path.write_text('{"url":"https://example.com/service/"}', encoding='utf-8')
        with patch.dict(os.environ, {'JPLLMLINT_CONFIG': str(path)}):
            self.assertEqual(rewrite.service_url(), 'https://example.com/service')

    def test_bad_config(self):
        for value in [[], {'url': []}, {'url': 'file:///service'}, {'url': 'http://localhost/#fragment'}]:
            self.config(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                rewrite.service_url()

    def test_unconfigured_returns_original_without_network(self):
        output = io.StringIO()
        with patch('sys.argv', ['rewrite.py']), patch('sys.stdin', io.StringIO('original text')), \
                patch('sys.stdout', output), contextlib.redirect_stderr(io.StringIO()), \
                patch('rewrite.urllib.request.urlopen') as network:
            self.assertEqual(rewrite.main(), 3)
        self.assertEqual(output.getvalue(), 'original text')
        network.assert_not_called()

    def test_success_and_guard_fallback(self):
        for result, expected, status in [
            ({'changed': True, 'rewritten': 'new text'}, 'new text', 0),
            ({'changed': False, 'fallback': True}, 'original text', 2),
        ]:
            output = io.StringIO()
            with self.subTest(status=status), patch('sys.argv', ['rewrite.py']), \
                    patch('sys.stdin', io.StringIO('original text')), patch('sys.stdout', output), \
                    contextlib.redirect_stderr(io.StringIO()), patch('rewrite.call', side_effect=[{}, result]):
                self.assertEqual(rewrite.main(), status)
            self.assertEqual(output.getvalue(), expected)


if __name__ == '__main__':
    unittest.main()
