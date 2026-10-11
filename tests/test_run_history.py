import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.core.run_history import RunHistory, HistoryReadError
from backend.app.api import routes
from backend.app.main import app


class RunHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.history = RunHistory(self.root)
        self.names = []
        for index in range(6):
            filename = f'qwen3-tts-1.7b_{index}.run.json'
            audio_file = filename[:-9] + '.wav'
            (self.root / audio_file).write_bytes(b'original audio')
            path = self.root / filename
            path.write_text(json.dumps({'audio_file': audio_file, 'text': f'test {index}'}))
            os.utime(path, ns=(index + 1, index + 1))
            self.names.append(filename)

    def test_pages_are_stable_and_clamp_after_last_record_is_hidden(self):
        first = self.history.paginate(limit=5)
        self.assertEqual((first['total'], first['pages'], first['page']), (6, 2, 1))
        self.assertEqual([x['text'] for x in first['items']], [f'test {i}' for i in range(5, 0, -1)])
        self.history.set_deleted(self.names[0], True)
        last = self.history.paginate(page=2, limit=5)
        self.assertEqual((last['total'], last['page'], last['pages']), (5, 1, 1))
        self.assertEqual(self.history.paginate(deleted=True)['items'][0]['text'], 'test 0')

    def test_delete_and_restore_preserve_audio_parameters_reviews_and_batch(self):
        name = self.names[-1]
        (self.root / name.replace('.run.json', '.review.json')).write_text('saved human review')
        batches = self.root / 'comparisons'
        batches.mkdir()
        (batches / 'batch.json').write_text(json.dumps({'results': [{'audio_file': name[:-9] + '.wav'}]}))
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.history.set_deleted(name, True)
        reloaded = RunHistory(self.root)
        self.assertEqual(reloaded.paginate()['total'], 5)
        self.assertEqual(reloaded.paginate(deleted=True)['total'], 1)
        deleted_at = reloaded.paginate(deleted=True)['items'][0]['history_deleted_at']
        reloaded.set_deleted(name, True)
        self.assertEqual(reloaded.paginate(deleted=True)['items'][0]['history_deleted_at'], deleted_at)
        reloaded.set_deleted(name, False)
        self.assertEqual(RunHistory(self.root).paginate()['total'], 6)
        self.assertEqual(reloaded.paginate(deleted=True)['total'], 0)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_failed_atomic_write_does_not_change_visibility(self):
        with patch('backend.app.core.run_history.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.history.set_deleted(self.names[0], True)
        self.assertEqual(self.history.paginate()['total'], 6)
        self.assertFalse(list((self.root / '.run-history').glob('*.tmp')))
        self.history.set_deleted(self.names[0], True)
        with patch('backend.app.core.run_history.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.history.set_deleted(self.names[0], False)
        self.assertEqual(self.history.paginate(deleted=True)['total'], 1)

    def test_corrupt_metadata_is_reported_and_not_overwritten(self):
        self.history.set_deleted(self.names[0], True)
        path = self.root / '.run-history' / self.names[0]
        path.write_text('{broken')
        with self.assertRaises(HistoryReadError):
            self.history.paginate()
        with self.assertRaises(HistoryReadError):
            self.history.set_deleted(self.names[0], False)
        self.assertEqual(path.read_text(), '{broken')

    def test_invalid_paths_and_mismatched_audio_cannot_be_changed(self):
        for name in ('../qwen3-tts-1.7b_0.run.json', '/tmp/escape.run.json', 'missing.run.json'):
            with self.assertRaises(FileNotFoundError):
                self.history.set_deleted(name, True)
        (self.root / self.names[0]).write_text(json.dumps({'audio_file': '../escape.wav'}))
        self.assertEqual(self.history.paginate()['total'], 5)
        with self.assertRaises(FileNotFoundError):
            self.history.set_deleted(self.names[0], True)

    def test_external_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other)
            (outside / 'alias.run.json').write_text(json.dumps({'audio_file': 'alias.wav'}))
            (self.root / 'alias.run.json').symlink_to(outside / 'alias.run.json')
            with self.assertRaises(FileNotFoundError):
                self.history.set_deleted('alias.run.json', True)
            (self.root / '.run-history').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(HistoryReadError):
                self.history.set_deleted(self.names[0], True)
            self.assertFalse((outside / self.names[0]).exists())

    def test_api_pagination_restore_and_raw_record_access(self):
        with patch.object(routes, 'run_history', self.history), patch.object(routes, 'OUTPUTS_DIR', self.root):
            client = TestClient(app)
            self.assertEqual(client.get('/api/runs?page=2&limit=5').json()['pagination']['page'], 2)
            name = self.names[-1]
            self.assertEqual(client.delete('/api/runs/' + name).status_code, 200)
            self.assertEqual(client.get('/api/runs?deleted=true').json()['pagination']['total'], 1)
            self.assertEqual(client.get('/api/runs/' + name).status_code, 200)
            self.assertEqual(client.get('/api/audio/' + name[:-9] + '.wav').status_code, 200)
            self.assertEqual(client.post('/api/runs/' + name + '/restore').status_code, 200)
            self.assertEqual(client.get('/api/runs').json()['pagination']['total'], 6)
            self.assertEqual(client.get('/api/runs?page=0').status_code, 422)
            self.assertEqual(client.get('/api/runs?limit=101').status_code, 422)
            self.assertEqual(client.delete('/api/runs/missing.run.json').status_code, 404)

    def test_api_reports_storage_failures(self):
        with patch.object(routes, 'run_history', self.history):
            with patch.object(self.history, 'set_deleted', side_effect=OSError('disk full')):
                with self.assertRaises(HTTPException) as caught:
                    routes.delete_run(self.names[0])
                self.assertEqual(caught.exception.status_code, 500)
            with patch.object(self.history, 'paginate', side_effect=HistoryReadError('bad metadata')):
                with self.assertRaises(HTTPException) as caught:
                    routes.get_runs()
                self.assertEqual(caught.exception.status_code, 409)


if __name__ == '__main__':
    unittest.main()
