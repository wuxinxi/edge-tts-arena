import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from fastapi import HTTPException
from backend.app.core.comparison_jobs import ComparisonJobs
from backend.app.api.routes import list_comparisons, delete_comparison, restore_comparison, get_comparison


class HistoryManagementTests(unittest.TestCase):
    def populate(self, directory, count):
        jobs = ComparisonJobs(directory)
        ids = [jobs.submit([], dict(text=f'历史 {i}'), lambda started, finished: None)['job_id'] for i in range(count)]
        jobs.close()
        self.addCleanup(jobs.close)
        return jobs, ids

    def test_pagination_has_full_count_no_duplicates_and_no_result_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, ids = self.populate(directory, 7)
            with patch('backend.app.api.routes.comparison_jobs', jobs):
                pages = [list_comparisons(limit=3, page=page) for page in (1, 2, 3)]
                self.assertEqual(pages[0]['pagination'], dict(total=7, page=1, page_size=3, pages=3))
                combined = [job['job_id'] for page in pages for job in page['data']]
                self.assertEqual(combined, list(reversed(ids)))
                self.assertTrue(all('results' not in job for page in pages for job in page['data']))
                self.assertEqual(list_comparisons(3, 99)['pagination']['page'], 3)

    def test_delete_restore_survive_reload_and_preserve_audio_and_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / 'existing.wav'
            audio.write_bytes(b'original audio')
            record = root / 'existing.run.json'
            record.write_text('{"original":true}')
            jobs, ids = self.populate(root / 'comparisons', 1)
            with patch('backend.app.api.routes.comparison_jobs', jobs):
                self.assertTrue(delete_comparison(ids[0])['data']['deleted'])
                self.assertEqual(list_comparisons()['pagination']['total'], 0)
                with self.assertRaises(HTTPException) as caught:
                    get_comparison(ids[0])
                self.assertEqual(caught.exception.status_code, 404)
            restored = ComparisonJobs(root / 'comparisons')
            self.addCleanup(restored.close)
            with patch('backend.app.api.routes.comparison_jobs', restored):
                trash = list_comparisons(deleted=True)
                self.assertEqual(trash['pagination']['total'], 1)
                self.assertIn('deleted_at', trash['data'][0])
                self.assertFalse(restore_comparison(ids[0])['data']['deleted'])
                self.assertIsNotNone(get_comparison(ids[0])['data'])
                self.assertEqual(list_comparisons(deleted=True)['data'], [])
            self.assertEqual(audio.read_bytes(), b'original audio')
            self.assertEqual(record.read_text(), '{"original":true}')
            again = ComparisonJobs(root / 'comparisons')
            self.addCleanup(again.close)
            self.assertEqual(again.paginate()['total'], 1)

    def test_deleting_last_item_moves_to_previous_page_and_empty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, ids = self.populate(directory, 6)
            jobs.set_deleted(ids[0])
            final = jobs.paginate(page=2, limit=5)
            self.assertEqual((final['page'], final['pages'], final['total'], len(final['items'])), (1, 1, 5, 5))
            for key in ids[1:]:
                jobs.set_deleted(key)
            self.assertEqual(jobs.paginate(page=9, limit=5), dict(items=[], page=1, pages=0, total=0, page_size=5))

    def test_running_and_queued_batches_cannot_be_deleted(self):
        jobs = ComparisonJobs()
        running, release = Event(), Event()
        def runner(started, finished):
            running.set()
            release.wait(3)
        first = jobs.submit([], {}, runner)
        try:
            self.assertTrue(running.wait(3))
            second = jobs.submit([], {}, lambda started, finished: None)
            with patch('backend.app.api.routes.comparison_jobs', jobs):
                for key in (first['job_id'], second['job_id']):
                    with self.assertRaises(HTTPException) as caught:
                        delete_comparison(key)
                    self.assertEqual(caught.exception.status_code, 409)
                    self.assertIsNotNone(jobs.get(key))
        finally:
            release.set()
            jobs.close()

    def test_storage_failure_does_not_hide_history_or_lose_restoration(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, ids = self.populate(directory, 1)
            with patch.object(jobs, '_save', side_effect=OSError('write failed')), patch('backend.app.api.routes.comparison_jobs', jobs):
                with self.assertRaises(HTTPException) as caught:
                    delete_comparison(ids[0])
                self.assertEqual(caught.exception.status_code, 500)
            self.assertIsNotNone(jobs.get(ids[0]))
            jobs.set_deleted(ids[0])
            with patch.object(jobs, '_save', side_effect=OSError('write failed')):
                with self.assertRaises(OSError):
                    jobs.set_deleted(ids[0], False)
            self.assertIsNone(jobs.get(ids[0]))
            self.assertEqual(jobs.paginate(deleted=True)['total'], 1)

    def test_missing_and_invalid_identifiers_do_not_modify_history(self):
        jobs = ComparisonJobs()
        self.addCleanup(jobs.close)
        with patch('backend.app.api.routes.comparison_jobs', jobs):
            for action in (delete_comparison, restore_comparison):
                for key in ('missing', '../elsewhere'):
                    with self.assertRaises(HTTPException) as caught:
                        action(key)
                    self.assertEqual(caught.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
