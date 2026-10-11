import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import soundfile as sf
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.core.comparison_jobs import ComparisonJobs
from backend.app.core.listening_reviews import ListeningReviews
from backend.app.core.config import MODELS_CATALOG
from backend.app.api.routes import (TTSCompareRequest, RetryComparisonInput, ListeningReviewInput,
    start_comparison, get_comparison, stop_comparison, retry_comparison, get_listening_review,
    save_listening_review, export_comparison)


class BatchActionTests(unittest.TestCase):
    def test_stop_preserves_current_result_and_skips_remaining_without_fake_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = ComparisonJobs(directory)
            running, release = Event(), Event()
            executed = []
            def runner(started, finished):
                for key in ('one', 'two'):
                    if not started(key):
                        break
                    executed.append(key)
                    if key == 'one':
                        running.set()
                        release.wait(3)
                    finished(dict(model_key=key, success=True))
            job = jobs.submit([dict(key=key, name=key) for key in ('one', 'two')], {}, runner)
            try:
                self.assertTrue(running.wait(3))
                with patch('backend.app.api.routes.comparison_jobs', jobs):
                    ack = stop_comparison(job['job_id'])['data']
                self.assertTrue(ack['stop_requested'])
                self.assertEqual(ack['status'], 'running')
                self.assertEqual(ack['completed'], 0)
            finally:
                release.set()
                jobs.close()
            final = jobs.get(job['job_id'])
            self.assertEqual((final['status'], final['completed'], final['failed'], final['total']), ('cancelled', 1, 0, 2))
            self.assertEqual(executed, ['one'])
            self.assertEqual([task['status'] for task in final['models']], ['succeeded', 'skipped'])
            restored = ComparisonJobs(directory)
            try:
                self.assertEqual(restored.get(job['job_id']), final)
            finally:
                restored.close()

    def test_queued_stop_never_invokes_the_runner(self):
        jobs = ComparisonJobs()
        running, release = Event(), Event()
        executed = []
        def first(started, finished):
            started('one'); running.set(); release.wait(3)
            finished(dict(model_key='one', success=True))
        jobs.submit([dict(key='one', name='One')], {}, first)
        try:
            self.assertTrue(running.wait(3))
            queued = jobs.submit([dict(key='two', name='Two')], {}, lambda started, finished: executed.append('two'))
            cancelled = jobs.request_stop(queued['job_id'])
            self.assertEqual((cancelled['status'], cancelled['completed']), ('cancelled', 0))
        finally:
            release.set(); jobs.close()
        self.assertEqual(executed, [])

    def test_stop_during_last_run_still_finishes_as_completed(self):
        jobs = ComparisonJobs()
        running, release = Event(), Event()
        def runner(started, finished):
            started('one'); running.set(); release.wait(3)
            finished(dict(model_key='one', success=True))
        job = jobs.submit([dict(key='one', name='One')], {}, runner)
        try:
            self.assertTrue(running.wait(3))
            jobs.request_stop(job['job_id'])
        finally:
            release.set(); jobs.close()
        self.assertEqual(jobs.get(job['job_id'])['status'], 'completed')
        self.assertEqual(jobs.request_stop(job['job_id'])['completed'], 1)
        self.assertIsNone(jobs.request_stop('unknown'))

    def test_retry_only_failed_task_preserves_sample_round_mode_and_speed(self):
        jobs = ComparisonJobs()
        calls = []
        fail_once = [True]
        def adapter(key):
            def generate(**kwargs):
                calls.append((key, kwargs))
                info = kwargs['evaluation']
                if fail_once[0] and key == 'melotts-zh' and info['sample_id'] == 'two' and info['repeat_index'] == 2:
                    fail_once[0] = False
                    raise RuntimeError('测试失败')
                return dict(model_key=key, success=True)
            return SimpleNamespace(metadata=MODELS_CATALOG[key], generate=generate)
        req = TTSCompareRequest(model_keys=['kokoro-82m','melotts-zh'], text='输入框文本', speed=1.2,
            benchmark_mode='recommended', repeats=2, samples=[dict(id='one',label='场景一',text='一'),dict(id='two',label='场景二',text='二')])
        try:
            with patch('backend.app.api.routes.comparison_jobs', jobs), patch('backend.app.api.routes.AdapterFactory.get_adapter',side_effect=adapter):
                original = start_comparison(req)['data']
                # 等待批次完成，不能关闭执行器后再提交重试。
                done = Event()
                jobs._executor.submit(done.set)
                self.assertTrue(done.wait(3))
                child = retry_comparison(original['job_id'],RetryComparisonInput())['data']
                jobs.close()
                final = get_comparison(child['job_id'])['data']
                parent = get_comparison(original['job_id'])['data']
            self.assertEqual((parent['successful'],parent['failed']), (7,1))
            self.assertEqual((final['total'],final['completed'],final['successful']), (1,1,1))
            self.assertEqual(final['retry_of'],parent['job_id'])
            self.assertEqual(len(calls),9)
            self.assertEqual(calls[-1][0], 'melotts-zh')
            self.assertEqual(calls[-1][1]['text'], '二')
            self.assertEqual(calls[-1][1]['evaluation']['repeat_index'],2)
            self.assertEqual(calls[-1][1]['evaluation']['mode'],'recommended')
            self.assertEqual(calls[-1][1]['evaluation']['output_speed'],1.2)
            self.assertEqual(final['samples'][0]['id'],'two')
            self.assertEqual(parent['models'][-1]['status'],'failed')
        finally:
            jobs.close()

    def test_retry_requires_explicit_reference_choice_and_does_not_retry_skipped(self):
        jobs = ComparisonJobs()
        stream = io.BytesIO(); sf.write(stream,np.ones(2400)*.1,24000,format='WAV')
        encoded = base64.b64encode(stream.getvalue()).decode()
        adapter = SimpleNamespace(metadata=MODELS_CATALOG['chattts'], generate=lambda **kwargs: (_ for _ in ()).throw(RuntimeError('失败')))
        try:
            with patch('backend.app.api.routes.comparison_jobs',jobs), patch('backend.app.api.routes.AdapterFactory.get_adapter',return_value=adapter):
                original = start_comparison(TTSCompareRequest(model_keys=['chattts'],text='测试',ref_audio=encoded,ref_text='原文'))['data']
                done = Event(); jobs._executor.submit(done.set); self.assertTrue(done.wait(3))
                with self.assertRaises(HTTPException) as missing:
                    retry_comparison(original['job_id'],RetryComparisonInput())
                self.assertEqual(missing.exception.status_code,400)
                child = retry_comparison(original['job_id'],RetryComparisonInput(use_default_reference=True))['data']
                jobs.close()
                self.assertEqual(child['reference_source'],'default')
                with self.assertRaises(HTTPException):
                    retry_comparison('missing',RetryComparisonInput())
        finally:
            jobs.close()

    def test_retry_active_or_no_failed_batch_is_rejected(self):
        jobs = ComparisonJobs()
        running,release=Event(),Event()
        def runner(started,finished):
            started('one'); running.set(); release.wait(3); finished(dict(model_key='one',success=True))
        job=jobs.submit([dict(key='one',name='One')],{},runner)
        try:
            self.assertTrue(running.wait(3))
            with patch('backend.app.api.routes.comparison_jobs',jobs):
                with self.assertRaises(HTTPException) as active:
                    retry_comparison(job['job_id'],RetryComparisonInput())
                self.assertEqual(active.exception.status_code,409)
        finally:
            release.set(); jobs.close()
        with patch('backend.app.api.routes.comparison_jobs',jobs),self.assertRaises(HTTPException) as no_failed:
            retry_comparison(job['job_id'],RetryComparisonInput())
        self.assertEqual(no_failed.exception.status_code,400)


class ListeningReviewTests(unittest.TestCase):
    def test_decimal_model_names_allow_reviews_and_still_reject_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            reviews = ListeningReviews(root)
            for stem in ('qwen3-tts-0.6b_12345678', 'qwen3-tts-1.7b_12345678', 'fish-speech-1.5_12345678'):
                with self.subTest(stem=stem):
                    name = stem + '.run.json'
                    (root / name).write_text('{}')
                    with patch('backend.app.api.routes.listening_reviews', reviews):
                        self.assertIsNone(get_listening_review(name)['data'])
                        saved = save_listening_review(name, ListeningReviewInput(issues=['pronunciation']))['data']
                        self.assertEqual(get_listening_review(name)['data'], saved)
                    self.assertEqual(reviews.enrich(dict(success=True, audio_file=stem+'.wav'))['listening_review'], saved)
            external = Path(outside) / 'one.run.json'
            external.write_text('{}')
            (root / 'linked.run.json').symlink_to(external)
            for name in ('../one.run.json', str(external), '.hidden.run.json', 'one..run.json', 'linked.run.json'):
                with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                    reviews.get(name)

    def test_review_persists_separately_and_enriches_export_without_changing_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            name='kokoro-82m_12345678.run.json'
            record=Path(directory)/name
            original=dict(success=True,model_key='kokoro-82m',audio_file='kokoro-82m_12345678.wav',metrics=dict(rtf=1.25))
            record.write_text(json.dumps(original))
            reviews=ListeningReviews(directory)
            self.assertIsNone(reviews.get(name))
            with patch('backend.app.api.routes.listening_reviews',reviews):
                saved=save_listening_review(name,ListeningReviewInput(verdict='needs_work',issues=['omission','omission'],notes='第三句需核对'))['data']
                self.assertEqual(get_listening_review(name)['data'],saved)
            self.assertEqual(saved['issues'],['omission'])
            self.assertEqual(saved['source'],'human')
            self.assertEqual(json.loads(record.read_text()),original)
            restored=ListeningReviews(directory)
            enriched=restored.enrich(original)
            self.assertEqual(enriched['metrics'],original['metrics'])
            self.assertNotIn('listening_review',original)
            self.assertEqual(enriched['listening_review'],saved)
            jobs=ComparisonJobs()
            try:
                job=jobs.submit([dict(key='kokoro-82m',name='Kokoro')],{},lambda started,finished:(started('kokoro-82m'),finished(original)))
                jobs.close()
                with patch('backend.app.api.routes.listening_reviews',restored),patch('backend.app.api.routes.comparison_jobs',jobs):
                    exported=json.loads(export_comparison(job['job_id']).body)
                self.assertEqual(exported['results'][0]['listening_review'],saved)
            finally:
                jobs.close()

    def test_unknown_records_and_traversal_are_rejected_and_corrupt_notes_are_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            reviews=ListeningReviews(directory)
            for name in ('../elsewhere.run.json','missing.run.json'):
                with patch('backend.app.api.routes.listening_reviews',reviews),self.assertRaises(HTTPException) as error:
                    get_listening_review(name)
                self.assertEqual(error.exception.status_code,404)
            name='one.run.json'; (Path(directory)/name).write_text('{}')
            (Path(directory)/'one.review.json').write_text('[]')
            with patch('backend.app.api.routes.listening_reviews',reviews),self.assertRaises(HTTPException) as error:
                get_listening_review(name)
            self.assertEqual(error.exception.status_code,409)

    def test_corrupt_review_cannot_be_overwritten_or_disappear_from_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); name='one.run.json'
            (root/name).write_text('{}')
            reviews=ListeningReviews(root)
            incomplete=json.dumps(dict(source='human',record_file=name,updated_at='2026-10-09T00:00:00+00:00'))
            for payload in ('{broken', '{}', '{"issues":42}', '[]', incomplete):
                path=root/'one.review.json'; path.write_text(payload)
                with patch('backend.app.api.routes.listening_reviews',reviews),self.assertRaises(HTTPException) as error:
                    save_listening_review(name,ListeningReviewInput(notes='新备注'))
                self.assertEqual(error.exception.status_code,409)
                self.assertEqual(path.read_text(),payload)
                result=reviews.enrich(dict(success=True,audio_file='one.wav',metrics=dict(rtf=1)))
                self.assertIn('listening_review_error',result)
                self.assertEqual(result['metrics'],dict(rtf=1))

    def test_unreadable_review_is_an_error_and_blocks_save(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); name='one.run.json'
            (root/name).write_text('{}')
            reviews=ListeningReviews(root)
            with patch('backend.app.api.routes.listening_reviews',reviews),patch.object(Path,'read_text',side_effect=PermissionError('unreadable')):
                for action in (lambda:get_listening_review(name),lambda:save_listening_review(name,ListeningReviewInput(notes='新备注'))):
                    with self.assertRaises(HTTPException) as error:
                        action()
                    self.assertEqual(error.exception.status_code,409)

    def test_review_validation_rejects_unknown_flags_and_oversized_notes(self):
        with self.assertRaises(ValidationError):
            ListeningReviewInput(issues=['made_up_score'])
        with self.assertRaises(ValidationError):
            ListeningReviewInput(notes='a'*2001)
        with self.assertRaises(ValidationError):
            ListeningReviewInput(verdict='perfect')


if __name__ == '__main__':
    unittest.main()
