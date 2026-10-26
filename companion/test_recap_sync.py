import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import recap_sync as r

REQ = {'version': 1, 'book_id': 'a'*32, 'title': 'Test', 'text': 'Anfang.\n',
       'cutoff': '/body/p[2]', 'activity': 1, 'opened': 1, 'session': 1}


class SyncTest(unittest.TestCase):
    def setUp(self):
        config = patch.object(r.ai_providers, 'load_settings', return_value={'provider': 'codex'})
        config.start()
        self.addCleanup(config.stop)

    def test_required_sections_and_old_cache_migration(self):
        complete = '\n\n'.join(heading + '\nInhalt?' for heading in r.SECTIONS)
        self.assertEqual(r.validate_summary(complete), complete)
        with self.assertRaises(ValueError):
            r.validate_summary(complete.split(r.SECTIONS[-1])[0])
        with self.assertRaises(ValueError):
            r.validate_summary(complete.split(r.SECTIONS[-1])[0] + r.SECTIONS[-1])
        calls = []
        def model(title, previous, excerpt, exe):
            calls.append((previous, excerpt))
            return complete
        old = {'source_length': len(REQ['text']), 'source_hash': r.digest(REQ['text']),
               'summary': 'Alter Rückblick ohne Fragen.'}
        result = r.build(REQ, old, 'fake', model)
        self.assertEqual(calls, [('', REQ['text'])])
        self.assertEqual(result['format_version'], r.FORMAT_VERSION)
        empty = r.build(dict(REQ, text=''), None, 'fake', model)
        r.validate_summary(empty['summary'])

    def test_incremental_and_backward_spoiler_guard(self):
        calls = []
        def model(title, previous, excerpt, exe):
            calls.append((previous, excerpt))
            return previous + excerpt
        first = r.build(REQ, None, 'unused', model)
        more = dict(REQ, text=REQ['text']+'Danach.', session=2)
        second = r.build(more, first, 'unused', model)
        self.assertEqual(calls[-1], ('Anfang.\n', 'Danach.'))
        r.build(REQ, second, 'unused', model)
        self.assertEqual(calls[-1], ('', 'Anfang.\n'))
        n = len(calls)
        reopened = r.build(dict(more, session=3), second, 'unused', model)
        self.assertEqual(len(calls), n)
        self.assertNotEqual(reopened['request_id'], second['request_id'])

    def test_repeat_delivery_failure_retry_and_multiple_books(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.resolve()) as t, patch.object(r, 'HERE', Path(t)/'pc'):
            r.HERE.mkdir()
            device = Path(t)/'device'
            requests = device/'koreader/settings/reading_recap_requests'
            requests.mkdir(parents=True)
            calls = []
            def model(*args):
                calls.append(args)
                return 'Eine überprüfbare Zusammenfassung.'
            for key in ['a','b']:
                r.atomic_json(requests/(key*32+'.json'), dict(REQ, book_id=key*32))
            self.assertEqual(r.sync(device, 'fake', model), 0)
            self.assertEqual(len(calls), 2)
            r.sync(device, 'fake', model)
            self.assertEqual(len(calls), 2)
            dest = device/'koreader/settings/reading_recaps'/('a'*32+'.json')
            dest.unlink()
            r.sync(device, 'fake', model)
            self.assertTrue(dest.exists())
            self.assertEqual(len(calls), 2)
            changed = dict(REQ, text='Neuer Text.', session=4)
            r.atomic_json(requests/('a'*32+'.json'), changed)
            before = dest.read_bytes()
            def fail(*args): raise RuntimeError('offline')
            self.assertEqual(r.sync(device, 'fake', fail), 1)
            self.assertEqual(dest.read_bytes(), before)
            self.assertEqual(r.sync(device, 'fake', model), 0)

    def test_validation_and_chunk_coverage(self):
        r.validate(REQ, 'a'*32+'.json')
        with self.assertRaises(ValueError): r.validate(REQ, '../bad.json')
        text = 'abc\n'*40000
        self.assertEqual(''.join(r.chunks(text)), text)
        self.assertTrue(all(len(x)<=60000 for x in r.chunks(text)))

    def test_api_sync_needs_no_codex_and_provider_change_rebuilds(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.resolve()) as t, patch.object(r, 'HERE', Path(t)/'pc'):
            r.HERE.mkdir()
            device = Path(t)/'device'
            path = device/'koreader/settings/reading_recap_requests'/('a'*32+'.json')
            r.atomic_json(path, REQ)
            complete = '\n\n'.join(heading + '\nInhalt?' for heading in r.SECTIONS)
            with patch.object(r.ai_providers, 'load_settings', return_value={'provider':'openai','model':'test-one','key':'fake'}), \
                 patch.object(r, 'find_codex', side_effect=AssertionError('Must not require Codex')), \
                 patch.object(r.ai_providers, 'summarize', return_value=complete) as model:
                self.assertEqual(r.sync(device), 0)
                self.assertEqual(model.call_count, 1)
                self.assertEqual(r.sync(device), 0)
                self.assertEqual(model.call_count, 1)
                first = json.loads((r.HERE/'recap-cache'/path.name).read_text())
                with patch.object(r.ai_providers, 'load_settings', return_value={'provider':'gemini','model':'test-two','key':'fake'}):
                    self.assertEqual(r.sync(device), 0)
                second = json.loads((r.HERE/'recap-cache'/path.name).read_text())
                self.assertNotEqual(first['request_id'], second['request_id'])
                self.assertEqual(second['generator'], 'gemini:test-two')
                payload = json.loads(model.call_args.args[0].split('\n', 1)[1])
                self.assertEqual(payload['previous_recap'], '')


class StartupTest(unittest.TestCase):
    def test_script_starts_in_isolated_mode_from_foreign_directory(self):
        # sync.ps1 runs `python -I recap_sync.py`; -I drops the script folder from sys.path.
        # Unit tests import the module directly and cannot catch a broken real start.
        script = Path(r.__file__).resolve()
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run([sys.executable, '-I', str(script), '--help'],
                                    cwd=cwd, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--device', result.stdout)


if __name__ == '__main__': unittest.main()
