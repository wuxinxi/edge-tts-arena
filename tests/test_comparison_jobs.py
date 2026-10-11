import base64
import io
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import soundfile as sf
from fastapi import HTTPException

from backend.app.api.routes import TTSCompareRequest, start_comparison, get_comparison
from backend.app.core.comparison_jobs import ComparisonJobs
from backend.app.core.config import MODELS_CATALOG


class ComparisonJobTests(unittest.TestCase):
    def setUp(self):
        self.jobs = ComparisonJobs()

    def tearDown(self):
        self.jobs.close()

    def test_partial_results_are_visible_before_the_last_model_finishes(self):
        running, release = Event(), Event()

        def runner(started, finished):
            started('one')
            finished(dict(model_key='one', success=True))
            started('two')
            running.set()
            release.wait(3)
            finished(dict(model_key='two', success=False, error='生成失败'))

        initial = self.jobs.submit([dict(key='one', name='One'), dict(key='two', name='Two')], {}, runner)
        try:
            self.assertTrue(running.wait(3))
            live = self.jobs.get(initial['job_id'])
            self.assertEqual((live['completed'], live['total'], live['current_model']), (1, 2, 'two'))
            self.assertEqual([model['status'] for model in live['models']], ['succeeded', 'running'])
            live['results'].clear()
            self.assertEqual(len(self.jobs.get(initial['job_id'])['results']), 1)
        finally:
            release.set()
        self.jobs.close()
        final = self.jobs.get(initial['job_id'])
        self.assertEqual((final['status'], final['completed'], final['successful'], final['failed']), ('completed', 2, 1, 1))

    def test_batches_are_queued_instead_of_running_concurrently(self):
        running, release = Event(), Event()

        def first(started, finished):
            started('one')
            running.set()
            release.wait(3)
            finished(dict(model_key='one', success=True))

        self.jobs.submit([dict(key='one', name='One')], {}, first)
        try:
            self.assertTrue(running.wait(3))
            second = self.jobs.submit([dict(key='two', name='Two')], {},
                                      lambda started, finished: (started('two'), finished(dict(model_key='two', success=True))))
            self.assertEqual((second['status'], second['completed']), ('queued', 0))
        finally:
            release.set()
        self.jobs.close()
        self.assertEqual(self.jobs.get(second['job_id'])['status'], 'completed')

    def test_route_keeps_reference_alive_and_preserves_uniform_settings(self):
        stream = io.BytesIO()
        sf.write(stream, np.ones(2400, dtype=np.float32) * .1, 24000, format='WAV')
        encoded = base64.b64encode(stream.getvalue()).decode()
        calls = []

        def generate(**kwargs):
            self.assertTrue(Path(kwargs['ref_audio_path']).is_file())
            calls.append(kwargs)
            return dict(model_key='chattts', success=True)

        adapter = SimpleNamespace(metadata=MODELS_CATALOG['chattts'], generate=generate)
        with patch('backend.app.api.routes.comparison_jobs', self.jobs), \
                patch('backend.app.api.routes.AdapterFactory.get_adapter', return_value=adapter):
            response = start_comparison(TTSCompareRequest(model_keys=['chattts', 'chattts'], text='测试',
                                                          speed=1.2, ref_audio=encoded, ref_text='参考文字'))
            self.jobs.close()
            final = get_comparison(response['data']['job_id'])['data']
        self.assertEqual(final['total'], 1)
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(final['ref_text'], '参考文字')
        self.assertEqual(calls[0]['preset'], 'default')
        self.assertEqual(calls[0]['options'], {'refine_text': False})
        self.assertEqual(calls[0]['speed_mode'], 'output')
        self.assertEqual(calls[0]['evaluation']['model_speed'], 1.0)
        self.assertEqual(calls[0]['evaluation']['output_speed'], 1.2)
        self.assertFalse(Path(calls[0]['ref_audio_path']).exists())

    def test_setup_failure_does_not_report_unrun_models_as_complete(self):
        with patch('backend.app.api.routes.comparison_jobs', self.jobs):
            response = start_comparison(TTSCompareRequest(model_keys=['chattts'], text='测试', ref_audio='bad-base64'))
            self.jobs.close()
            final = get_comparison(response['data']['job_id'])['data']
        self.assertEqual((final['status'], final['completed']), ('failed', 0))
        self.assertEqual(final['models'][0]['status'], 'skipped')
        self.assertIn('Base64', final['error'])

    def test_one_model_failure_does_not_block_the_next_model(self):
        adapter = SimpleNamespace(metadata=MODELS_CATALOG['chattts'], generate=lambda **kwargs: dict(model_key='chattts', success=True))
        with patch('backend.app.api.routes.comparison_jobs', self.jobs), \
                patch('backend.app.api.routes.AdapterFactory.get_adapter', side_effect=lambda key: adapter if key == 'chattts' else None):
            response = start_comparison(TTSCompareRequest(model_keys=['missing', 'chattts'], text='测试'))
            self.jobs.close()
            final = get_comparison(response['data']['job_id'])['data']
        self.assertEqual((final['completed'], final['successful'], final['failed']), (2, 1, 1))

    def test_unknown_job_has_a_clear_error(self):
        with patch('backend.app.api.routes.comparison_jobs', self.jobs), self.assertRaises(HTTPException) as caught:
            get_comparison('missing')
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
