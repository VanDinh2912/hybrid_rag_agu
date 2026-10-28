"""D3: dữ liệu giả, mock transport; tuyệt đối không gọi Ollama/Gemini/GPU."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.eval import classify_real_questions as runner


def write_rows(tmp_path, rows):
    path = tmp_path / 'questions.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows), encoding='utf-8')
    return path


def options(path, tmp_path, **changes):
    return SimpleNamespace(**({'in_path': path, 'out_dir': tmp_path / 'out', 'dry_run': False,
        'host': runner.DEFAULT_HOST, 'model': runner.DEFAULT_MODEL, 'timeout': 5.0} | changes))


def forbidden(*args, **kwargs):
    pytest.fail('Không được gọi model/API trong ca này.')


@pytest.mark.parametrize('rows', [[], [{'id': 'blank', 'question': ''}],
    [{'_schema': 'test'}, {'id': 'example', 'question': 'Câu giả', 'example': True}]])
def test_empty_never_initializes_backend_or_writes(tmp_path, rows):
    args = options(write_rows(tmp_path, rows), tmp_path)
    assert runner.run(args, forbidden) == 0
    assert not args.out_dir.exists()


def test_dry_run_with_real_shaped_synthetic_row_does_not_infer(tmp_path):
    args = options(write_rows(tmp_path, [{'id': 'X1', 'question': 'Câu hỏi giả để kiểm thử'}]), tmp_path, dry_run=True)
    assert runner.run(args, forbidden) == 0
    assert not args.out_dir.exists()


def test_load_rejects_duplicates_and_keeps_optional_labels(tmp_path):
    path = write_rows(tmp_path, [
        {'id': 'A', 'question': ' Học phí bao nhiêu? ', 'chu_de': 'học phí'},
        {'id': 'A', 'question': 'Khác nội dung'},
        {'id': 'B', 'question': 'hỌc   PHÍ bao nhiêu?'},
        {'id': '', 'question': 'Thiếu mã'},
        {'id': 'C', 'question': 'Câu giả không nhãn'},
    ])
    rows, report = runner.load_questions(path)
    assert [r['id'] for r in rows] == ['A', 'C']
    assert [r['reason'] for r in report['dropped']] == ['duplicate_id', 'duplicate_question', 'missing_or_invalid_id']
    assert rows[0]['chu_de'] == 'học phí'


@pytest.mark.parametrize('row', [[], 'string', 123])
def test_jsonl_requires_objects(tmp_path, row):
    with pytest.raises(ValueError, match='JSON object'):
        runner.load_questions(write_rows(tmp_path, [row]))


def test_gold_is_never_inferred_from_prediction():
    labels = runner.taxonomy()
    assert runner.label_state({}, 'topic', labels['topic']) == (None, 'missing')
    assert runner.label_state({'chu_de': 'tai_chinh'}, 'topic', labels['topic']) == (None, 'invalid')
    assert runner.label_state({'chu_de': 'hoc phi'}, 'topic', labels['topic']) == ('học phí', 'valid')
    assert runner.label_state({'question_type': 'so-sanh'}, 'question_type', labels['question_type']) == ('SO_SANH', 'valid')


@pytest.mark.parametrize('host', ['https://127.0.0.1:11435', 'http://remote.test:11435',
    'http://127.0.0.1:11434', 'http://localhost', 'http://u:p@localhost:11435',
    'http://localhost:11435/other', 'http://localhost:11435?x=1'])
def test_unsafe_or_shared_endpoint_rejected(host):
    with pytest.raises(ValueError):
        runner.validate_host(host)


class FakeClient:
    def __init__(self, response=None, error=None, vram=0):
        self.response = response or {'response': '{"topic":"học phí","question_type":"TRA_CUU"}'}
        self.error, self.vram = error, vram
        self.calls = []

    def ps(self):
        return SimpleNamespace(models=[SimpleNamespace(size_vram=self.vram)])

    def list(self):
        return SimpleNamespace(models=[SimpleNamespace(model=runner.DEFAULT_MODEL)])

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def test_cpu_transport_reuses_actual_classifier_and_restores_patch():
    from src import classifier
    old_transport = classifier.LocalSLM
    client = FakeClient()
    backend = runner.CpuClassifier(runner.DEFAULT_HOST, runner.DEFAULT_MODEL, client=client, classifier_module=classifier)
    result = backend.predict('Học phí bao nhiêu?')
    assert result['topic'] == 'học phí'
    assert result['question_type'] == 'TRA_CUU'
    assert result['cpu_verified'] and result['transport_error'] is None
    assert classifier.LocalSLM is old_transport
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call['prompt'] == classifier.build_classifier_prompt('Học phí bao nhiêu?')
    assert call['options'] == {'temperature': 0.0, 'num_predict': 160, 'num_gpu': 0, 'num_thread': 1}
    assert call['stream'] is False and call['model'] == runner.DEFAULT_MODEL


def test_invalid_model_json_keeps_production_keyword_fallback():
    from src import classifier
    backend = runner.CpuClassifier(runner.DEFAULT_HOST, runner.DEFAULT_MODEL,
        client=FakeClient({'response': 'not JSON'}), classifier_module=classifier)
    result = backend.predict('Học phí bao nhiêu?')
    assert result['topic'] == 'học phí' and result['question_type'] == 'TRA_CUU'
    assert result['transport_error'] is None


def test_network_error_is_visible_despite_production_fallback():
    from src import classifier
    backend = runner.CpuClassifier(runner.DEFAULT_HOST, runner.DEFAULT_MODEL,
        client=FakeClient(error=TimeoutError('mock timeout')), classifier_module=classifier)
    result = backend.predict('Học phí bao nhiêu?')
    assert result['topic'] is None and result['question_type'] == 'TRA_CUU'
    assert 'TimeoutError' in result['transport_error']
    assert result['cpu_verified'] is False


@pytest.mark.parametrize('vram', [1, None])
def test_backend_refuses_gpu_or_unknown_vram(vram):
    with pytest.raises(RuntimeError, match='CPU-only'):
        runner.CpuClassifier(runner.DEFAULT_HOST, runner.DEFAULT_MODEL, client=FakeClient(vram=vram), classifier_module=SimpleNamespace())


def test_metrics_unknown_predictions_and_missing_gold():
    labels = {'topic': ['a', 'b'], 'question_type': ['TRA_CUU', 'SO_SANH']}
    rows = [
        {'topic_gold': 'a', 'topic_gold_state': 'valid', 'topic_pred': 'a',
         'question_type_gold': 'TRA_CUU', 'question_type_gold_state': 'valid', 'question_type_pred': 'TRA_CUU'},
        {'topic_gold': 'b', 'topic_gold_state': 'valid', 'topic_pred': runner.UNKNOWN,
         'question_type_gold': None, 'question_type_gold_state': 'missing', 'question_type_pred': 'SO_SANH'},
        {'topic_gold': None, 'topic_gold_state': 'invalid', 'topic_pred': 'a',
         'question_type_gold': None, 'question_type_gold_state': 'invalid', 'question_type_pred': 'SO_SANH'},
    ]
    report = runner.evaluate(rows, labels, reps=200)
    assert report['topic']['accuracy'] == .5 and report['topic']['macro_f1'] == .5
    assert report['topic']['confusion_matrix'] == [[1, 0, 0], [0, 0, 1]]
    assert report['topic']['gold_counts'] == {'valid': 2, 'missing': 0, 'invalid': 1}
    assert report['question_type']['n'] == 1
    assert report['question_type']['macro_f1'] == .5  # fixed taxonomy, absent label not removed
    assert runner.evaluate([], labels, reps=10)['topic']['n'] == 0


class FakeBackend:
    def __init__(self, *args):
        self.calls = []

    def predict(self, text):
        self.calls.append(text)
        return {'topic': 'học phí', 'question_type': 'TRA_CUU', 'raw_response': 'mock',
                'cpu_verified': True, 'transport_error': None, 'latency_seconds': .001}


def test_run_creates_predictions_matrices_and_does_not_edit_input(tmp_path):
    path = write_rows(tmp_path, [{'id': 'X1', 'question': 'Câu giả', 'chu_de': 'học phí', 'question_type': 'TRA_CUU'},
                                {'id': 'X2', 'question': 'Câu giả khác'}])
    before = path.read_bytes()
    args = options(path, tmp_path)
    assert runner.run(args, FakeBackend) == 0
    summary = json.loads((args.out_dir / 'summary.json').read_text(encoding='utf-8'))
    assert summary['n_scored'] == 2 and summary['metrics']['topic']['n'] == 1
    assert summary['metrics']['topic']['accuracy'] == 1
    for name in ['predictions.csv', 'predictions.jsonl', 'confusion_topic.csv', 'confusion_question_type.csv']:
        assert (args.out_dir / name).exists()
    assert path.read_bytes() == before
    with pytest.raises(FileExistsError):
        runner.run(args, forbidden)


def test_error_stops_run_and_keeps_partial_predictions(tmp_path):
    class ErrorBackend(FakeBackend):
        def predict(self, text):
            return {**super().predict(text), 'topic': None, 'transport_error': 'mock failed', 'cpu_verified': False}
    args = options(write_rows(tmp_path, [{'id': f'X{i}', 'question': f'Câu giả {i}'} for i in range(3)]), tmp_path)
    assert runner.run(args, ErrorBackend) == 2
    summary = json.loads((args.out_dir / 'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'STOPPED_TRANSPORT_ERROR' and summary['n_scored'] == 1
    assert summary['remaining_ids'] == ['X1', 'X2']
    assert summary['metrics']['topic']['n'] == 0
    assert not (args.out_dir / 'confusion_topic.csv').exists()


@pytest.mark.parametrize('successful_before_failure', [0, 1])
def test_preflight_exception_preserves_partial_and_does_not_invent_predictions(tmp_path, successful_before_failure):
    class ProbeFailureBackend(FakeBackend):
        def predict(self, text):
            if len(self.calls) == successful_before_failure:
                raise RuntimeError('mock CPU probe failed')
            return super().predict(text)
    rows = [{'id': f'X{i}', 'question': f'Câu giả {i}', 'chu_de': 'học phí'} for i in range(2)]
    args = options(write_rows(tmp_path, rows), tmp_path)
    assert runner.run(args, ProbeFailureBackend) == 2
    summary = json.loads((args.out_dir / 'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'STOPPED_TRANSPORT_ERROR'
    assert summary['n_scored'] == successful_before_failure
    assert summary['remaining_ids'] == [r['id'] for r in rows[successful_before_failure:]]
    assert summary['stop_error']['id'] == rows[successful_before_failure]['id']
    assert 'probe failed' in summary['stop_error']['error']
    assert summary['metrics']['topic']['n'] == successful_before_failure
    assert (args.out_dir / 'predictions.csv').exists()
    predictions = (args.out_dir / 'predictions.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(predictions) == successful_before_failure
