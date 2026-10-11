"""生成历史的可恢复隐藏状态，独立于原始音频、参数和评测批次。"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class HistoryReadError(ValueError):
    pass


class RunHistory:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.lock = Lock()

    def _record(self, filename):
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.run\.json', filename):
            raise FileNotFoundError('生成记录不存在')
        path = (self.directory / filename).resolve()
        if path.parent != self.directory or not path.is_file():
            raise FileNotFoundError('生成记录不存在')
        result = json.loads(path.read_text(encoding='utf-8'))
        audio = (self.directory / result['audio_file']).resolve()
        if audio.parent != self.directory or not audio.is_file() or result['audio_file'] != filename[:-9] + '.wav':
            raise FileNotFoundError('生成记录的音频不存在或不匹配')
        return path, result

    def _metadata_path(self, filename):
        folder = self.directory / '.run-history'
        path = folder / filename
        if folder.resolve() != folder or path.resolve().parent != folder:
            raise HistoryReadError('生成历史管理文件路径无效，请检查本机存储。')
        return path

    def _deleted_at(self, filename):
        path = self._metadata_path(filename)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            timestamp = data['deleted_at']
            if data['record_file'] != filename or (timestamp is not None and not isinstance(timestamp, str)):
                raise ValueError('历史状态不匹配')
            if timestamp is not None:
                datetime.fromisoformat(timestamp)
            return timestamp
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HistoryReadError('生成历史管理文件无法读取，请检查本机存储后重试。') from exc

    def paginate(self, page=1, limit=50, deleted=False):
        with self.lock:
            records = []
            for path in self.directory.glob('*.run.json'):
                try:
                    record_path, result = self._record(path.name)
                    modified = record_path.stat().st_mtime_ns
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                timestamp = self._deleted_at(path.name)
                if bool(timestamp) != deleted:
                    continue
                if timestamp:
                    result['history_deleted_at'] = timestamp
                records.append((modified, path.name, result))
            records.sort(key=lambda item: (item[0], item[1]), reverse=True)
            total = len(records)
            pages = (total + limit - 1) // limit
            page = max(1, min(page, pages or 1))
            return {'items': [item[2] for item in records[(page - 1) * limit:page * limit]],
                    'total': total, 'page': page, 'page_size': limit, 'pages': pages}

    def set_deleted(self, filename, deleted):
        with self.lock:
            try:
                self._record(filename)
            except (ValueError, KeyError, TypeError) as exc:
                raise HistoryReadError('原始生成记录无法读取，历史状态未更新。') from exc
            previous = self._deleted_at(filename)
            timestamp = (previous or datetime.now(timezone.utc).isoformat()) if deleted else None
            if bool(previous) == deleted:
                return {'record_file': filename, 'deleted': deleted}
            path = self._metadata_path(filename)
            path.parent.mkdir(exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                                 prefix='.history-', suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump({'record_file': filename, 'deleted_at': timestamp}, handle, ensure_ascii=False)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return {'record_file': filename, 'deleted': deleted}
