"""音频级人工试听记录；与实测参数、指标分开保存。"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.app.core.config import OUTPUTS_DIR


class ListeningReviewInput(BaseModel):
    verdict: Literal['unreviewed', 'acceptable', 'needs_work', 'unusable'] = 'unreviewed'
    naturalness: Literal['unreviewed', 'natural', 'ordinary', 'mechanical'] = 'unreviewed'
    expression: Literal['unreviewed', 'appropriate', 'flat', 'exaggerated'] = 'unreviewed'
    issues: list[Literal['omission', 'repetition', 'cutoff', 'pronunciation', 'noise']] = Field(default_factory=list, max_length=5)
    notes: str = Field('', max_length=2000, strict=True)

    @field_validator('issues')
    @classmethod
    def unique_issues(cls, values):
        return list(dict.fromkeys(values))


class SavedListeningReview(ListeningReviewInput):
    source: Literal['human']
    record_file: str
    updated_at: datetime


class ReviewReadError(Exception):
    """已有记录未能安全读取，不能当作空记录覆盖。"""


class ListeningReviews:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self._lock = Lock()

    def _path(self, filename):
        # 模型版本名包含小数点（Qwen 0.6B / 1.7B、Fish 1.5）。
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.run\.json', filename):
            raise FileNotFoundError('生成记录不存在')
        record = (self.directory / filename).resolve()
        if record.parent != self.directory or not record.is_file():
            raise FileNotFoundError('生成记录不存在')
        path = record.with_name(filename.replace('.run.json', '.review.json'))
        if path.resolve().parent != self.directory:
            raise FileNotFoundError('试听记录路径无效')
        return path

    def _read(self, path, filename):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            SavedListeningReview.model_validate(value)
            if not set(SavedListeningReview.model_fields).issubset(value):
                raise ValueError('记录字段不完整')
            if value['record_file'] != filename:
                raise ValueError('记录对应的音频不一致')
            return value
        except FileNotFoundError:
            return None
        except (OSError, ValueError, ValidationError) as exc:
            raise ReviewReadError('已有试听记录读取异常，已阻止覆盖。请检查记录文件后重新读取。') from exc

    def get(self, filename):
        with self._lock:
            return self._read(self._path(filename), filename)

    def save(self, filename, values):
        path = self._path(filename)
        result = dict(**values, source='human', record_file=filename,
                      updated_at=datetime.now(timezone.utc).isoformat())
        with self._lock:
            # 即使页面曾成功读取，保存时也要重新核对已有文件。
            self._read(path, filename)
            temporary = path.with_suffix('.tmp')
            with temporary.open('w', encoding='utf-8') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        return result

    def enrich(self, result):
        if not result.get('success') or not result.get('audio_file', '').endswith('.wav'):
            return result
        try:
            review = self.get(result['audio_file'].replace('.wav', '.run.json'))
        except FileNotFoundError:
            return result
        except ReviewReadError as exc:
            return dict(result, listening_review_error=str(exc))
        return dict(result, listening_review=review) if review else result


listening_reviews = ListeningReviews(OUTPUTS_DIR)
