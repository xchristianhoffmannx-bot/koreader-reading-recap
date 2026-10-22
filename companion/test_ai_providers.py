import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

import ai_providers as a
import recap_sync as r


class ProviderTest(unittest.TestCase):
    def test_requests_for_each_provider(self):
        samples = {
            'openai': {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"summary":"Recap"}'}}]},
            'anthropic': {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '```json\n{"summary":"Recap"}\n```'}]},
            'gemini': {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"summary":"Recap"}'}]}}]},
        }
        hosts = {'openai': 'https://api.openai.com/', 'anthropic': 'https://api.anthropic.com/',
                 'gemini': 'https://generativelanguage.googleapis.com/'}
        for provider, data in samples.items():
            with self.subTest(provider=provider):
                opener = Mock()
                opener.open.return_value = io.BytesIO(json.dumps(data).encode())
                with patch.object(a.urllib.request, 'build_opener', return_value=opener):
                    self.assertEqual(a.summarize('Read text', {'provider': provider, 'model': 'test-model', 'key': 'fake-key'}), 'Recap')
                request = opener.open.call_args.args[0]
                self.assertTrue(request.full_url.startswith(hosts[provider]))
                self.assertNotIn('fake-key', request.full_url)
                self.assertNotIn('fake-key', request.data.decode())
                self.assertIn('fake-key', str(request.header_items()))
                self.assertNotIn('tools', json.loads(request.data))

    def test_errors_hide_credentials_and_truncation_is_rejected(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError('https://api.openai.com', 401, 'fake-key must never appear', {}, None)
        settings = {'provider': 'openai', 'model': 'test-model', 'key': 'fake-key'}
        with patch.object(a.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(RuntimeError) as error: a.summarize('text', settings)
            self.assertNotIn('fake-key', str(error.exception))
        for provider, data in [
            ('openai', {'choices': [{'finish_reason': 'length', 'message': {'content': '{"summary":"truncated"}'}}]}),
            ('anthropic', {'stop_reason': 'max_tokens', 'content': []}),
            ('gemini', {'candidates': [{'finishReason': 'MAX_TOKENS'}]}),
        ]:
            opener.open.side_effect = None
            opener.open.return_value = io.BytesIO(json.dumps(data).encode())
            with patch.object(a.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(RuntimeError): a.summarize('text', dict(settings, provider=provider))
        self.assertIsNone(a.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid'))

    def test_settings_and_provider_fingerprints(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.resolve()) as tmp:
            with patch.dict(os.environ, {'LOCALAPPDATA': tmp}, clear=True):
                self.assertEqual(a.load_settings(), {'provider': 'codex'})
                os.environ.update(RECAP_PROVIDER='anthropic', RECAP_MODEL='test-model', ANTHROPIC_API_KEY='fake-key')
                self.assertEqual(a.load_settings()['key'], 'fake-key')
                del os.environ['ANTHROPIC_API_KEY']
                with self.assertRaises(ValueError): a.load_settings()
                os.environ['RECAP_PROVIDER'] = 'unknown'
                with self.assertRaises(ValueError): a.load_settings()
        self.assertNotEqual(r.request_id({}, 'openai:model'), r.request_id({}, 'anthropic:model'))

    @unittest.skipUnless(os.name == 'nt', 'Windows-only credential round trip')
    def test_configuration_encrypts_and_python_decrypts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.resolve()) as tmp:
            script = Path(__file__).with_name('configure.ps1').resolve()
            command = ("$ErrorActionPreference='Stop'; Import-Module Microsoft.PowerShell.Security; "
                       "function Read-Host { param($Prompt,[switch]$AsSecureString) "
                       "if ($AsSecureString) { return (ConvertTo-SecureString 'synthetic-test-key' -AsPlainText -Force) }; "
                       "if ($Prompt -eq 'Provider') { return 'openai' }; return 'test-model' }; & '" +
                       str(script).replace("'", "''") + "'")
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
                                    env=dict({k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}, LOCALAPPDATA=tmp),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            config_file = Path(tmp)/'KOReaderReadingRecap/provider.json'
            raw = config_file.read_text(encoding='utf-8-sig')
            self.assertNotIn('synthetic-test-key', raw)
            self.assertEqual(a.unprotect(json.loads(raw)['encrypted_key']), 'synthetic-test-key')
            with patch.dict(os.environ, {'LOCALAPPDATA': tmp}, clear=True):
                self.assertEqual(a.load_settings()['key'], 'synthetic-test-key')


if __name__ == '__main__': unittest.main()
