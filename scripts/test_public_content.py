import unittest
from check_public_content import inspect


class PublicationTests(unittest.TestCase):
    def test_person_machine_and_home(self):
        samples = ['LPC' + '-999', 'C:' + '/Users/' + 'private-user/project', '山田' + 'さん']
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(inspect('SKILL.md', sample.encode()))

    def test_local_denylist_and_safe_examples(self):
        self.assertTrue(inspect('SKILL.md', b'internal-example-value', ['internal-example-value']))
        self.assertEqual(inspect('SKILL.md', 'Aさん、$env:USERPROFILE、workstation'.encode()), [])

    def test_private_service_and_generated_files(self):
        self.assertTrue(inspect('SKILL.md', ('http://' + 'service-host:8000').encode()))
        self.assertTrue(inspect('SKILL.md', ('http://' + '100.64.1.1:8000').encode()))
        self.assertTrue(inspect('outputs/evidence.jsonl', b'{}'))

    def test_output_does_not_echo_values(self):
        secret = 'ghp_' + 'a' * 40
        result = inspect('config.py', secret.encode())
        self.assertTrue(result)
        self.assertNotIn(secret, repr(result))


if __name__ == '__main__':
    unittest.main()
