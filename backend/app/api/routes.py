import base64
import binascii
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Literal, Annotated

import soundfile as sf
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.core.config import OUTPUTS_DIR
from backend.app.core.hardware import get_hardware_info
from backend.app.adapters.factory import AdapterFactory
from backend.app.core.comparison_jobs import comparison_jobs
from backend.app.core.config import MODELS_CATALOG
from backend.app.core.reference import default_reference
from backend.app.core.run_history import RunHistory, HistoryReadError
from backend.app.core.listening_reviews import listening_reviews, ListeningReviewInput, ReviewReadError

router = APIRouter()
run_history = RunHistory(OUTPUTS_DIR)


class SynthesisInput(BaseModel):
    text: str = Field(..., min_length=1, description='待合成的文本')
    speed: float = Field(1.0, ge=0.5, le=2.0)
    speed_mode: Literal['model', 'output'] = 'model'
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = None

    @field_validator('text')
    @classmethod
    def validate_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('合成文本不能为空')
        return value


class TTSGenerateRequest(SynthesisInput):
    model_key: str
    voice: Optional[str] = None
    prompt: Optional[str] = None
    preset: str = 'default'
    options: dict = Field(default_factory=dict)


class EvaluationSample(BaseModel):
    id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]{1,48}$')
    label: str = Field(..., min_length=1, max_length=80)
    text: str = Field(..., min_length=1, max_length=6000)
    listen_for: str = Field('', max_length=500)

    @field_validator('text', 'label')
    @classmethod
    def validate_nonempty(cls, value):
        if not value.strip():
            raise ValueError('测试文本和名称不能为空')
        return value.strip()


class TTSCompareRequest(SynthesisInput):
    text: str = Field('', description='未选择测试集时使用的自定义文本')
    model_keys: list[str] = Field(..., min_length=1, max_length=10)
    speed_mode: Literal['output'] = 'output'
    benchmark_mode: Literal['uniform', 'recommended'] = 'uniform'
    samples: list[EvaluationSample] = Field(default_factory=list, max_length=8)
    repeats: int = Field(1, ge=1, le=5)

    @field_validator('text')
    @classmethod
    def validate_text(cls, value):
        return value.strip()

    @model_validator(mode='after')
    def require_evaluation_text(self):
        if not self.samples and not self.text:
            raise ValueError('未选择测试集时，评测文本不能为空')
        return self

    @field_validator('samples')
    @classmethod
    def unique_samples(cls, values):
        if len({sample.id for sample in values}) != len(values):
            raise ValueError('测试文本 ID 不可重复')
        return values


class RetryComparisonInput(BaseModel):
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = None
    use_default_reference: bool = False


@contextmanager
def reference_audio(encoded):
    if not encoded:
        yield None
        return
    try:
        payload = encoded.split(',', 1)[1] if encoded.startswith('data:') else encoded
        data = base64.b64decode(payload, validate=True)
        if not data:
            raise ValueError('参考音频为空')
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail='参考音频不是有效的 Base64 数据') from exc
    with tempfile.TemporaryDirectory(prefix='tts_ref_') as directory:
        path = Path(directory) / 'reference.wav'
        path.write_bytes(data)
        try:
            info = sf.info(path)
            if info.frames <= 0:
                raise ValueError('音频没有有效采样')
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail='参考音频无法解码，请上传有效的 WAV / MP3 音频') from exc
        yield str(path)


@router.get('/system')
def get_system():
    return {'success': True, 'data': get_hardware_info()}


@router.get('/models')
def get_models():
    return {'success': True, 'data': AdapterFactory.get_all_models_status()}


@router.post('/tts/generate')
def generate_audio(req: TTSGenerateRequest):
    adapter = AdapterFactory.get_adapter(req.model_key)
    if not adapter:
        raise HTTPException(status_code=404, detail=f'未找到指定的模型: {req.model_key}')
    with reference_audio(req.ref_audio) as ref_path:
        try:
            result = adapter.generate(text=req.text, voice=req.voice, speed=req.speed, prompt=req.prompt,
                                      ref_audio_path=ref_path, ref_text=req.ref_text,
                                      preset=req.preset, options=req.options, speed_mode=req.speed_mode)
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f'语音合成失败: {exc}') from exc
    return {'success': True, 'data': result}


@router.get('/reference/default')
def get_default_reference():
    try:
        path, _ = default_reference()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FileResponse(path, media_type='audio/wav')


@router.post('/tts/compare')
def compare_models(req: TTSCompareRequest):
    results = []
    with reference_audio(req.ref_audio) as ref_path:
        for task in comparison_plan(req):
            results.append(compare_task(req, task, ref_path))
    return {'success': True, 'text': req.text, 'benchmark_mode': req.benchmark_mode,
            'total_compared': len(results), 'results': results}


def compare_one(req, key, ref_path, evaluation_extra=None):
    adapter = AdapterFactory.get_adapter(key)
    try:
        if not adapter:
            raise ValueError(f'未找到指定的模型: {key}')
        preset = ({'chattts': 'default', 'qwen3-tts-1.7b': 'news', 'cosyvoice3': 'warm'}.get(key, 'default')
                  if req.benchmark_mode == 'recommended' else 'default')
        options = {'refine_text': False} if key == 'chattts' and req.benchmark_mode == 'uniform' else {}
        return adapter.generate(text=req.text, speed=req.speed, ref_audio_path=ref_path, ref_text=req.ref_text,
                                preset=preset, options=options, speed_mode='output',
                                evaluation={'mode': req.benchmark_mode, 'scope': 'cold_worker_offline',
                                            'model_speed': 1.0, 'output_speed': req.speed, **(evaluation_extra or {})})
    except Exception as exc:
        return {'success': False, 'model_key': key,
                'model_name': adapter.metadata.name if adapter else key,
                'param_size': adapter.metadata.param_size if adapter else '--', 'error': str(exc)}


def comparison_plan(req):
    samples = req.samples or [EvaluationSample(id='custom', label='当前文本', text=req.text)]
    return [dict(key=key if len(samples) == 1 and req.repeats == 1 else f'{key}:{sample.id}:{repeat}',
                 model_key=key, name=MODELS_CATALOG[key].name if key in MODELS_CATALOG else key,
                 sample_id=sample.id, sample_label=sample.label, text=sample.text,
                 listen_for=sample.listen_for, repeat_index=repeat)
            for sample in samples for repeat in range(1, req.repeats + 1) for key in dict.fromkeys(req.model_keys)]


def compare_task(req, task, ref_path):
    extra = dict(sample_id=task['sample_id'], sample_label=task['sample_label'], repeat_index=task['repeat_index'])
    result = compare_one(req.model_copy(update={'text': task['text']}), task['model_key'], ref_path, extra)
    result.update(task_key=task['key'], text=task['text'], **extra)
    return result


@router.post('/tts/compare/jobs', status_code=202)
def start_comparison(req: TTSCompareRequest):
    entries = comparison_plan(req)
    return submit_comparison(req, entries)


def submit_comparison(req, entries, retry_of=None):

    def run(started, finished):
        # 临时参考文件覆盖整批模型的生命周期，结束后再清理。
        with reference_audio(req.ref_audio) as ref_path:
            for task in entries:
                if started(task['key']) is False:
                    break
                finished(compare_task(req, task, ref_path))

    job = comparison_jobs.submit(entries, dict(text=req.text, benchmark_mode=req.benchmark_mode,
                                              speed=req.speed, repeats=req.repeats,
                                              samples=[sample.model_dump() for sample in req.samples if any(task['sample_id'] == sample.id for task in entries)] or
                                              [dict(id='custom', label='当前文本', text=req.text, listen_for='')],
                                              model_keys=list(dict.fromkeys(req.model_keys)),
                                              ref_text=req.ref_text or '',
                                              retry_of=retry_of,
                                              reference_source='uploaded' if req.ref_audio else 'default'), run)
    job['results'] = [listening_reviews.enrich(result) for result in job['results']]
    return {'success': True, 'data': job}


@router.post('/tts/compare/jobs/{job_id}/stop')
def stop_comparison(job_id: str):
    job = comparison_jobs.request_stop(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='评测批次不存在')
    return {'success': True, 'data': job}


@router.post('/comparisons/{job_id}/retry', status_code=202)
def retry_comparison(job_id: str, req: RetryComparisonInput):
    previous = get_comparison(job_id)['data']
    if previous['status'] in ('queued', 'running'):
        raise HTTPException(status_code=409, detail='请等待本批次结束后再重试失败项')
    entries = [{key: value for key, value in task.items() if key not in ('status', 'error')}
               for task in previous['models'] if task['status'] == 'failed']
    if not entries:
        raise HTTPException(status_code=400, detail='本批次没有失败项；未运行项不会作为失败项重试')
    uploaded = previous['reference_source'] == 'uploaded'
    if uploaded and not req.ref_audio and not req.use_default_reference:
        raise HTTPException(status_code=400, detail='原批次使用上传参考音频，请重新上传，或明确选择使用默认参考音频')
    samples = previous.get('samples') or [dict(id='custom', label='当前文本', text=previous['text'])]
    # 兼容只含模型 key 的旧任务记录；新任务保持原始场景和轮次。
    for entry in entries:
        entry.setdefault('model_key', entry['key'])
        entry.setdefault('sample_id', samples[0]['id'])
        entry.setdefault('sample_label', samples[0]['label'])
        entry.setdefault('text', samples[0]['text'])
        entry.setdefault('repeat_index', 1)
    request = TTSCompareRequest(model_keys=list(dict.fromkeys(task['model_key'] for task in entries)),
                                text=previous['text'], samples=samples, repeats=previous.get('repeats', 1),
                                speed=previous['speed'], benchmark_mode=previous['benchmark_mode'],
                                ref_audio=req.ref_audio if uploaded and not req.use_default_reference else None,
                                ref_text=req.ref_text if req.ref_text is not None else previous.get('ref_text', ''))
    return submit_comparison(request, entries, retry_of=job_id)


@router.get('/tts/compare/jobs/{job_id}')
def get_comparison(job_id: str):
    job = comparison_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='评测批次不存在；已保存的音频可在最近生成中查看。')
    job['results'] = [listening_reviews.enrich(result) for result in job['results']]
    return {'success': True, 'data': job}


@router.get('/comparisons')
def list_comparisons(limit: Annotated[int, Query(ge=1, le=100)] = 20,
                     page: Annotated[int, Query(ge=1)] = 1, deleted: bool = False):
    result = comparison_jobs.paginate(page=page, limit=limit, deleted=deleted)
    items = result.pop('items')
    return {'success': True, 'data': items, 'pagination': result}


def change_comparison_visibility(job_id, deleted):
    try:
        job = comparison_jobs.set_deleted(job_id, deleted)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail='历史批次未能更新，请检查本机存储后重试。') from exc
    if not job:
        raise HTTPException(status_code=404, detail='评测批次不存在')
    return {'success': True, 'data': {'job_id': job_id, 'deleted': bool(job.get('deleted_at'))}}


@router.delete('/comparisons/{job_id}')
def delete_comparison(job_id: str):
    return change_comparison_visibility(job_id, True)


@router.post('/comparisons/{job_id}/restore')
def restore_comparison(job_id: str):
    return change_comparison_visibility(job_id, False)


@router.get('/comparisons/{job_id}/export')
def export_comparison(job_id: str):
    job = get_comparison(job_id)['data']
    return JSONResponse(job, headers={'Content-Disposition': f'attachment; filename="comparison-{job_id}.json"'})


@router.get('/runs')
def get_runs(limit: Annotated[int, Query(ge=1, le=100)] = 50,
             page: Annotated[int, Query(ge=1)] = 1, deleted: bool = False):
    try:
        result = run_history.paginate(page=page, limit=limit, deleted=deleted)
    except HistoryReadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    items = result.pop('items')
    return {'success': True, 'data': [listening_reviews.enrich(run) for run in items], 'pagination': result}


def change_run_visibility(filename, deleted):
    try:
        result = run_history.set_deleted(filename, deleted)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HistoryReadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail='生成历史未能更新，请检查本机存储后重试。') from exc
    return {'success': True, 'data': result}


@router.delete('/runs/{filename}')
def delete_run(filename: str):
    return change_run_visibility(filename, True)


@router.post('/runs/{filename}/restore')
def restore_run(filename: str):
    return change_run_visibility(filename, False)


@router.get('/runs/{filename}/review')
def get_listening_review(filename: str):
    try:
        review = listening_reviews.get(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewReadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {'success': True, 'data': review}


@router.put('/runs/{filename}/review')
def save_listening_review(filename: str, req: ListeningReviewInput):
    try:
        review = listening_reviews.save(filename, req.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewReadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail='试听记录未能保存，请检查本机存储后重试。') from exc
    return {'success': True, 'data': review}


@router.get('/runs/{filename}')
def get_run_record(filename: str):
    path = (OUTPUTS_DIR / filename).resolve()
    if path.parent != OUTPUTS_DIR.resolve() or not filename.endswith('.run.json') or not path.is_file():
        raise HTTPException(status_code=404, detail='生成记录不存在')
    return FileResponse(path, media_type='application/json', filename=filename)


@router.get('/audio/{filename}')
def get_audio_file(filename: str):
    path = (OUTPUTS_DIR / filename).resolve()
    if path.parent != OUTPUTS_DIR.resolve() or path.suffix != '.wav' or not path.is_file():
        raise HTTPException(status_code=404, detail='音频文件不存在')
    return FileResponse(str(path), media_type='audio/wav')
