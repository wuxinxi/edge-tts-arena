"""串行评测任务；真实逐次进度与可恢复的本地批次记录。"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
import json
import os
import re
import logging
from pathlib import Path
from backend.app.core.config import OUTPUTS_DIR

logger = logging.getLogger(__name__)


class ComparisonJobs:
    def __init__(self, directory=None):
        self._lock = Lock()
        self._jobs = {}
        self._directory = Path(directory) if directory else None
        if self._directory:
            self._directory.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='tts-comparison')

    def _save(self, job):
        if not self._directory:
            return
        path = self._directory / (job['job_id'] + '.json')
        temporary = path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(job, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def _read(self, job_id):
        if not self._directory or not re.fullmatch(r'[a-f0-9]{32}', job_id):
            return None
        try:
            job = json.loads((self._directory / (job_id + '.json')).read_text(encoding='utf-8'))
            if not isinstance(job, dict) or job.get('job_id') != job_id or not isinstance(job.get('results'), list):
                return None
            # 只恢复已保存结果，不在重启时自动重跑剩余模型。
            if job['status'] in ('queued', 'running'):
                job.update(status='failed', current_model=None, error='服务重启导致本批次中断；已完成结果已保留。可准备相同设置后重新评测。')
                for model in job['models']:
                    if model['status'] in ('pending', 'running'):
                        model['status'] = 'skipped'
                self._save(job)
            return job
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def submit(self, models, metadata, runner):
        job_id = uuid4().hex
        job = dict(job_id=job_id, status='queued', created_at=datetime.now(timezone.utc).isoformat(),
                   completed=0, successful=0, failed=0, total=len(models), current_model=None,
                   models=[dict(**model, status='pending') for model in models], results=[], error=None,
                   **metadata)
        with self._lock:
            # 保留最近任务供刷新恢复；不丢弃仍在运行或排队的任务。
            finished = [key for key, value in self._jobs.items() if value['status'] in ('completed', 'failed', 'cancelled')]
            for key in finished[:-31]:
                del self._jobs[key]
            self._jobs[job_id] = job
            try:
                self._save(job)
            except Exception:
                del self._jobs[job_id]
                raise
        self._executor.submit(self._run, job_id, runner)
        return self.get(job_id)

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            return deepcopy(job) if job and not job.get('deleted_at') else None

    def recent(self, limit=20):
        return self.paginate(limit=limit)['items']

    def paginate(self, page=1, limit=20, deleted=False):
        with self._lock:
            jobs = dict(self._jobs)
            if self._directory:
                for path in self._directory.glob('*.json'):
                    if path.stem not in jobs:
                        job = self._read(path.stem)
                        if job:
                            jobs[path.stem] = job
            visible = [job for job in jobs.values() if bool(job.get('deleted_at')) == deleted]
            ordered = sorted(visible, key=lambda job: (job['created_at'], job['job_id']), reverse=True)
            total = len(ordered)
            pages = (total + limit - 1) // limit
            page = max(1, min(page, pages or 1))
            items = ordered[(page - 1) * limit:page * limit]
            return dict(items=[deepcopy({key: value for key, value in job.items() if key != 'results'}) for job in items],
                        total=total, page=page, page_size=limit, pages=pages)

    def set_deleted(self, job_id, deleted=True):
        with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            if not job:
                return None
            if deleted and job['status'] in ('queued', 'running'):
                raise ValueError('运行中或排队中的批次不能删除，请先等待结束或停止后续生成。')
            updated = deepcopy(job)
            if deleted:
                updated.setdefault('deleted_at', datetime.now(timezone.utc).isoformat())
            else:
                updated.pop('deleted_at', None)
            # 先写入成功，再更新缓存；存储失败时保留原状态。
            self._save(updated)
            self._jobs[job_id] = updated
            return deepcopy(updated)

    def request_stop(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id) or self._read(job_id)
            if not job or job.get('deleted_at'):
                return None
            if job['status'] in ('queued', 'running'):
                before = deepcopy(job)
                job['stop_requested'] = True
                if job['status'] == 'queued':
                    job['status'] = 'cancelled'
                    for model in job['models']:
                        model['status'] = 'skipped'
                try:
                    self._save(job)
                except Exception:
                    job.clear()
                    job.update(before)
                    raise
            return deepcopy(job)

    def _run(self, job_id, runner):
        def started(key):
            with self._lock:
                job = self._jobs[job_id]
                if job.get('stop_requested'):
                    return False
                job['current_model'] = key
                next(model for model in job['models'] if model['key'] == key)['status'] = 'running'
                self._save(job)
                return True

        def finished(result):
            with self._lock:
                job = self._jobs[job_id]
                model = next(model for model in job['models'] if model['key'] == result.get('task_key', result['model_key']))
                model['status'] = 'succeeded' if result['success'] else 'failed'
                model['error'] = result.get('error')
                job['results'].append(deepcopy(result))
                job['completed'] += 1
                job['successful' if result['success'] else 'failed'] += 1
                job['current_model'] = None
                self._save(job)

        try:
            with self._lock:
                if self._jobs[job_id]['status'] == 'cancelled':
                    return
                self._jobs[job_id]['status'] = 'running'
                self._save(self._jobs[job_id])
            runner(started, finished)
            with self._lock:
                job = self._jobs[job_id]
                pending = [model for model in job['models'] if model['status'] == 'pending']
                job['status'] = 'cancelled' if job.get('stop_requested') and pending else 'completed'
                for model in pending:
                    if job['status'] == 'cancelled':
                        model['status'] = 'skipped'
                self._save(job)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job['status'] = 'failed'
                job['error'] = str(exc)
                job['current_model'] = None
                for model in job['models']:
                    if model['status'] in ('running', 'pending'):
                        model['status'] = 'skipped'
                try:
                    self._save(job)
                except (OSError, ValueError, TypeError):
                    logger.exception('评测任务中断后无法保存批次记录')

    def close(self):
        self._executor.shutdown(wait=True)


comparison_jobs = ComparisonJobs(OUTPUTS_DIR / 'comparisons')
