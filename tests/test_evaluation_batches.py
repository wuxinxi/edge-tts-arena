import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from backend.app.api.routes import (EvaluationSample, TTSCompareRequest, start_comparison,
                                    get_comparison, list_comparisons, export_comparison)
from backend.app.core.comparison_jobs import ComparisonJobs
from backend.app.core.config import MODELS_CATALOG


class EvaluationBatchTests(unittest.TestCase):
    def test_fixed_samples_run_without_unused_custom_text(self):
        jobs = ComparisonJobs()
        calls = []
        adapter = SimpleNamespace(metadata=MODELS_CATALOG['kokoro-82m'],
            generate=lambda **kwargs: (calls.append(kwargs['text']) or dict(success=True, model_key='kokoro-82m')))
        try:
            request = TTSCompareRequest(model_keys=['kokoro-82m'], text='  ', samples=[
                dict(id='short', label='短提示', text='您好，请留意通知。')])
            with patch('backend.app.api.routes.comparison_jobs', jobs), patch('backend.app.api.routes.AdapterFactory.get_adapter', return_value=adapter):
                job = start_comparison(request)['data']
                jobs.close()
                self.assertEqual(get_comparison(job['job_id'])['data']['successful'], 1)
            self.assertEqual(calls, ['您好，请留意通知。'])
            self.assertEqual(TTSCompareRequest(model_keys=['kokoro-82m'], samples=request.samples).text, '')
        finally:
            jobs.close()
        with self.assertRaises(ValidationError):
            TTSCompareRequest(model_keys=['kokoro-82m'], text='  ')

    def test_submit_storage_failure_does_not_leave_a_queued_orphan(self):
        jobs = ComparisonJobs()
        try:
            with patch.object(jobs, '_save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    jobs.submit([dict(key='one', name='One')], {}, lambda started, finished: None)
            self.assertEqual(jobs.recent(), [])
        finally:
            jobs.close()

    def test_worker_storage_failure_finishes_instead_of_polling_forever(self):
        jobs = ComparisonJobs()
        try:
            with patch.object(jobs, '_save', side_effect=[None, OSError('disk full'), None]):
                job = jobs.submit([dict(key='one', name='One')], {}, lambda started, finished: None)
                jobs.close()
            final = jobs.get(job['job_id'])
            self.assertEqual((final['status'], final['completed']), ('failed', 0))
            self.assertEqual(final['models'][0]['status'], 'skipped')
            self.assertIn('disk full', final['error'])
        finally:
            jobs.close()

    def test_multiple_texts_and_repeats_keep_identity_settings_and_order(self):
        jobs = ComparisonJobs()
        calls = []
        def adapter(key):
            def generate(**kwargs):
                calls.append((key, kwargs))
                if key == 'melotts-zh' and kwargs['evaluation']['repeat_index'] == 1:
                    raise RuntimeError('一次失败')
                return dict(success=True, model_key=key, text=kwargs['text'])
            return SimpleNamespace(metadata=MODELS_CATALOG[key], generate=generate)
        req = TTSCompareRequest(model_keys=['kokoro-82m', 'melotts-zh', 'kokoro-82m'], text='上方文本', repeats=2,
                                samples=[EvaluationSample(id='one', label='短句', text='第一段'),
                                         EvaluationSample(id='two', label='长句', text='第二段')])
        try:
            with patch('backend.app.api.routes.comparison_jobs', jobs), patch('backend.app.api.routes.AdapterFactory.get_adapter', side_effect=adapter):
                job = start_comparison(req)['data']
                jobs.close()
                result = get_comparison(job['job_id'])['data']
            self.assertEqual((result['total'], result['completed'], result['successful'], result['failed']), (8, 8, 6, 2))
            self.assertEqual(result['model_keys'], ['kokoro-82m', 'melotts-zh'])
            self.assertEqual(len({run['task_key'] for run in result['results']}), 8)
            self.assertEqual([call[1]['text'] for call in calls], ['第一段'] * 4 + ['第二段'] * 4)
            self.assertEqual([call[1]['evaluation']['repeat_index'] for call in calls], [1, 1, 2, 2, 1, 1, 2, 2])
            self.assertTrue(all(call[1]['evaluation']['model_speed'] == 1 for call in calls))
            self.assertEqual(result['results'][1]['sample_id'], 'one')
            self.assertEqual(result['results'][1]['text'], '第一段')
        finally:
            jobs.close()

    def test_completed_batch_survives_a_new_service_instance_and_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = ComparisonJobs(directory)
            job = jobs.submit([dict(key='one', name='One')], dict(text='测试', benchmark_mode='uniform', speed=1),
                              lambda started, finished: (started('one'), finished(dict(model_key='one', success=True))))
            jobs.close()
            restored = ComparisonJobs(directory)
            try:
                with patch('backend.app.api.routes.comparison_jobs', restored):
                    saved = get_comparison(job['job_id'])['data']
                    listing = list_comparisons(20)['data']
                    exported = export_comparison(job['job_id'])
                self.assertEqual(saved['status'], 'completed')
                self.assertEqual(len(saved['results']), 1)
                self.assertEqual(listing[0]['job_id'], job['job_id'])
                self.assertNotIn('results', listing[0])
                self.assertEqual(json.loads(exported.body), saved)
                self.assertIn(job['job_id'], exported.headers['content-disposition'])
            finally:
                restored.close()

    def test_restart_preserves_partial_results_without_auto_rerunning(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = 'a' * 32
            path = Path(directory) / (identity + '.json')
            job = dict(job_id=identity, status='running', created_at='2026-10-09T00:00:00+00:00',
                       completed=1, successful=1, failed=0, total=3, current_model='two', error=None,
                       models=[dict(key='one', status='succeeded'), dict(key='two', status='running'), dict(key='three', status='pending')],
                       results=[dict(model_key='one', success=True)])
            path.write_text(json.dumps(job))
            jobs = ComparisonJobs(directory)
            try:
                recovered = jobs.get(identity)
                self.assertEqual((recovered['status'], recovered['completed'], recovered['failed']), ('failed', 1, 0))
                self.assertEqual([row['status'] for row in recovered['models']], ['succeeded', 'skipped', 'skipped'])
                self.assertIsNone(recovered['current_model'])
                self.assertEqual(len(recovered['results']), 1)
                self.assertEqual(json.loads(path.read_text())['status'], 'failed')
                self.assertEqual(jobs.recent()[0]['completed'], 1)
            finally:
                jobs.close()

    def test_corrupt_archives_and_path_traversal_are_not_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            for filename, payload in [('b' * 32, '['), ('c' * 32, '[]'), ('d' * 32, '{}')]:
                (Path(directory) / (filename + '.json')).write_text(payload)
            jobs = ComparisonJobs(directory)
            try:
                self.assertEqual(jobs.recent(), [])
                self.assertIsNone(jobs.get('../outside'))
                self.assertIsNone(jobs.get('c' * 32))
            finally:
                jobs.close()

    def test_dataset_validation_rejects_duplicate_ids_and_empty_text(self):
        with self.assertRaises(ValidationError):
            TTSCompareRequest(model_keys=['chattts'], text='测试', samples=[
                dict(id='same', label='A', text='一'), dict(id='same', label='B', text='二')])
        with self.assertRaises(ValidationError):
            EvaluationSample(id='one', label='A', text='  ')
        for repeats in (0, 6):
            with self.assertRaises(ValidationError):
                TTSCompareRequest(model_keys=['chattts'], text='测试', repeats=repeats)


if __name__ == '__main__':
    unittest.main()
