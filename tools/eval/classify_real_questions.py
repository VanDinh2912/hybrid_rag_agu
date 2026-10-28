"""D3: phân loại câu thật bằng classifier Qwen hiện có, transport CPU riêng.

Không gọi pipeline, chuẩn hóa, truy xuất hoặc sinh câu trả lời RAG. Ollama generate
chỉ dùng để sinh JSON nhãn phân loại. Không gọi model/API khi không có câu thật.

Xem trước (không cần Ollama):
  python tools/eval/classify_real_questions.py --dry-run
Khi đã có câu thật VÀ Ollama CPU riêng ở cổng 11435:
  python tools/eval/classify_real_questions.py --out-dir tmp/real_classifier_run_01

Nhãn người: chu_de (14 tên taxonomy; so khớp bỏ dấu), question_type (tùy chọn).
Nhãn thiếu/lạ được đếm riêng, không tự suy nhãn gold. Ví dụ luôn bị loại.
Không khởi động server, tải model, sửa .env, sửa src hoặc ghi đè kết quả cũ.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / 'tools/eval/real_questions.jsonl'
DEFAULT_HOST = 'http://127.0.0.1:11435'
DEFAULT_MODEL = 'qwen2.5:1.5b-instruct'
UNKNOWN = '<UNK>'
AXES = ('topic', 'question_type')


def fold(text):
    value = unicodedata.normalize('NFD', str(text).lower())
    return re.sub(r'\s+', ' ', ''.join(c for c in value if not unicodedata.combining(c)).replace('đ', 'd')).strip()


def taxonomy():
    """Đọc literal, không import module Ollama ở bước kiểm dữ liệu."""
    found = {}
    for node in ast.parse((ROOT / 'src/classifier.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('TOPICS', 'QUESTION_TYPES'):
                    found[target.id] = list(ast.literal_eval(node.value))
    return {'topic': found['TOPICS'], 'question_type': found['QUESTION_TYPES']}


def canonical(value, axis, labels):
    if not isinstance(value, str) or not value.strip():
        return None
    if axis == 'topic':
        return {fold(label): label for label in labels}[fold(value)] if fold(value) in {fold(label) for label in labels} else None
    key = re.sub(r'[\s\-]+', '_', fold(value)).upper()
    return key if key in labels else None


def load_questions(path):
    accepted, dropped = [], []
    seen_ids, seen_questions = set(), set()
    for line_no, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'Dòng {line_no}: cần JSON object.')
        if '_schema' in row or '_cot_can_dien_tay' in row:
            continue
        question, rid = row.get('question'), row.get('id')
        reason = None
        if row.get('example'):
            reason = 'example'
        elif not isinstance(question, str) or not question.strip():
            reason = 'empty_or_invalid_question'
        elif not isinstance(rid, str) or not rid.strip():
            reason = 'missing_or_invalid_id'
        else:
            rid, question = rid.strip(), question.strip()
            norm = ' '.join(question.split()).casefold()
            if rid in seen_ids:
                reason = 'duplicate_id'
            elif norm in seen_questions:
                reason = 'duplicate_question'
            else:
                seen_ids.add(rid)
                seen_questions.add(norm)
                accepted.append({**row, 'id': rid, 'question': question})
        if reason:
            dropped.append({'line': line_no, 'id': rid, 'reason': reason})
    return accepted, {'accepted_n': len(accepted), 'dropped': dropped}


def label_state(row, axis, labels):
    field = 'chu_de' if axis == 'topic' else 'question_type'
    value = row.get(field)
    if value is None or value == '':
        return None, 'missing'
    answer = canonical(value, axis, labels)
    return answer, 'valid' if answer is not None else 'invalid'


def validate_host(host):
    parsed = urlparse(host)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Chỉ cho phép Ollama HTTP loopback CPU riêng.')
    if parsed.port is None or parsed.port == 11434:
        raise ValueError('Dùng cổng CPU riêng, không dùng cổng mặc định 11434 của phiên GPU.')
    if parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Host không được chứa credentials, đường dẫn, query hoặc fragment.')
    return host


class CpuClassifier:
    """Giữ nguyên classify_query/prompt/parser/fallback; chỉ thay transport trong process CLI."""
    def __init__(self, host, model, timeout=90.0, client=None, classifier_module=None):
        validate_host(host)
        if client is None:
            import ollama
            client = ollama.Client(host=host, timeout=timeout)
        if classifier_module is None:
            sys.path.insert(0, str(ROOT))
            from src import classifier as classifier_module
        self.client, self.module, self.model = client, classifier_module, model
        self.last_error = None
        self.check_cpu()
        names = {getattr(m, 'model', None) or getattr(m, 'name', '') for m in self.client.list().models}
        if model not in names:
            raise RuntimeError(f'CPU endpoint chưa có đúng model {model!r}; runner không tự tải model.')

    def check_cpu(self):
        """Probe chỉ đọc; không unload model hoặc can thiệp server."""
        for model in self.client.ps().models:
            size_vram = getattr(model, 'size_vram', None)
            if size_vram is None or size_vram != 0:
                raise RuntimeError('Endpoint không xác nhận CPU-only (size_vram phải bằng 0).')

    def predict(self, query):
        self.check_cpu()
        self.last_error = None
        owner = self

        class CpuTransport:
            def __init__(self, **kwargs):
                self.num_predict = kwargs.get('num_predict', 160)

            def generate(self, prompt, temperature=0.0, num_predict=None):
                try:
                    response = owner.client.generate(model=owner.model, prompt=prompt, stream=False,
                        options={'temperature': temperature, 'num_predict': num_predict or self.num_predict,
                                 'num_gpu': 0, 'num_thread': 1})
                    text = response.get('response') if isinstance(response, dict) else getattr(response, 'response', None)
                    if not isinstance(text, str):
                        raise RuntimeError('Ollama response không có chuỗi response.')
                    return text.strip()
                except Exception as exc:
                    owner.last_error = f'{type(exc).__name__}: {exc}'
                    raise

        started = time.perf_counter()
        with patch.object(self.module, 'LocalSLM', CpuTransport):
            result = self.module.classify_query(query)
        try:
            self.check_cpu()
        except Exception as exc:
            self.last_error = f'{type(exc).__name__}: {exc}'
        return {**result, 'latency_seconds': time.perf_counter() - started,
                'transport_error': self.last_error, 'cpu_verified': self.last_error is None}


def evaluate(scored, labels, reps=10000, seed=20261028):
    """Ma trận dòng=gold/cột=pred; CI iid nhỏ mẫu, fixed labels, không bỏ UNK."""
    import numpy as np
    from sklearn.metrics import accuracy_score, f1_score
    result = {}
    for axis in AXES:
        eligible = [r for r in scored if r[f'{axis}_gold_state'] == 'valid']
        states = {s: sum(r[f'{axis}_gold_state'] == s for r in scored) for s in ('valid', 'missing', 'invalid')}
        if not eligible:
            result[axis] = {'n': 0, 'gold_counts': states, 'note': 'Chưa có nhãn người hợp lệ; không tính accuracy/ma trận/CI.'}
            continue
        gold = [r[f'{axis}_gold'] for r in eligible]
        pred = [r[f'{axis}_pred'] or UNKNOWN for r in eligible]
        cols = labels[axis] + sorted(set(pred) - set(labels[axis]))
        nr, nc = len(labels[axis]), len(cols)
        codes = np.array([labels[axis].index(a) * nc + cols.index(b) for a, b in zip(gold, pred)])
        cm = np.bincount(codes, minlength=nr * nc).reshape(nr, nc)
        rng = np.random.default_rng(seed)
        boot_acc, boot_macro = [], []
        for _ in range(reps):
            sample = np.bincount(codes[rng.integers(0, len(codes), len(codes))], minlength=nr * nc).reshape(nr, nc)
            tp = np.diag(sample[:, :nr])
            denominator = sample.sum(axis=1) + sample[:, :nr].sum(axis=0)
            fs = np.divide(2 * tp, denominator, out=np.zeros(nr), where=denominator != 0)
            boot_acc.append(tp.sum() / len(codes))
            boot_macro.append(fs.mean())
        result[axis] = {'n': len(gold), 'gold_counts': states, 'labels': labels[axis], 'columns': cols,
            'confusion_matrix': cm.tolist(), 'accuracy': float(accuracy_score(gold, pred)),
            'macro_f1': float(f1_score(gold, pred, labels=labels[axis], average='macro', zero_division=0)),
            'accuracy_ci95': np.quantile(boot_acc, [.025, .975]).tolist(),
            'macro_f1_ci95': np.quantile(boot_macro, [.025, .975]).tolist(),
            'bootstrap': {'method': 'iid item percentile', 'resamples': reps, 'seed': seed},
            'note': 'Mẫu nhỏ: CI có thể rộng hoặc suy biến. Không chứng minh tổng quát; bootstrap không khắc phục thiếu lớp/nguồn độc lập.'}
    return result


def run(args, classifier_factory=CpuClassifier):
    rows, validation = load_questions(args.in_path)
    labels = taxonomy()
    validation['human_labels'] = {a: {s: sum(label_state(r, a, labels[a])[1] == s for r in rows) for s in ('valid', 'missing', 'invalid')} for a in AXES}
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if not rows:
        print('CHƯA CHẠY: 0 câu thật; 0 lượt classifier/API; không tạo output.')
        return 0
    if args.dry_run:
        print(f'DRY-RUN: dự kiến {len(rows)} lượt classifier; hiện tại 0 lượt model/API; không tạo output.')
        return 0
    validate_host(args.host)
    if args.out_dir.exists():
        raise FileExistsError(f'Không ghi đè thư mục: {args.out_dir}')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    classifier = classifier_factory(args.host, args.model, args.timeout)
    args.out_dir.mkdir(parents=True, exist_ok=False)
    scored = []
    stop_error = None
    # Flush từng dòng để giữ phần đã làm nếu Ctrl-C hoặc process dừng.
    with (args.out_dir / 'predictions.jsonl').open('x', encoding='utf-8') as stream:
        for row in rows:
            try:
                answer = classifier.predict(row['question'])
            except Exception as exc:
                # Probe trước lượt có thể thất bại: không bịa prediction cho câu chưa chạy.
                # Vẫn xuất CSV/summary/ma trận của phần đã có, giữ câu này trong remaining_ids.
                stop_error = {'id': row['id'], 'error': f'{type(exc).__name__}: {exc}'}
                break
            item = {'id': row['id'], 'question': row['question'], 'nguon': row.get('nguon', ''),
                    'human_labels_original': {k: row.get(k) for k in ('chu_de', 'question_type')},
                    'raw_response': answer.get('raw_response', ''), 'latency_seconds': answer.get('latency_seconds'),
                    'transport_error': answer.get('transport_error'), 'cpu_verified': answer.get('cpu_verified', False)}
            for axis in AXES:
                item[f'{axis}_gold'], item[f'{axis}_gold_state'] = label_state(row, axis, labels[axis])
                item[f'{axis}_pred'] = canonical(answer.get(axis), axis, labels[axis]) or UNKNOWN
            scored.append(item)
            stream.write(json.dumps(item, ensure_ascii=False) + '\n')
            stream.flush()
            if item['transport_error']:
                break  # Giữ fallback như production, nhưng không âm thầm đo cả bộ khi endpoint lỗi.
    fields = ['id', 'question', 'topic_gold', 'topic_gold_state', 'topic_pred', 'question_type_gold',
              'question_type_gold_state', 'question_type_pred', 'latency_seconds', 'transport_error', 'cpu_verified']
    with (args.out_dir / 'predictions.csv').open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(scored)
    metrics = evaluate(scored, labels)
    for axis, metric in metrics.items():
        if not metric['n']:
            continue
        with (args.out_dir / f'confusion_{axis}.csv').open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['gold / prediction', *metric['columns']])
            writer.writerows([label, *values] for label, values in zip(metric['labels'], metric['confusion_matrix']))
    summary = {'status': 'STOPPED_TRANSPORT_ERROR' if stop_error or any(r['transport_error'] for r in scored) else 'COMPLETE',
        'n_requested': len(rows), 'n_scored': len(scored), 'remaining_ids': [r['id'] for r in rows[len(scored):]],
        'stop_error': stop_error,
        'backend': 'production Qwen classifier with CPU-only local transport (not sklearn v2)',
        'host': args.host, 'model': args.model, 'options': {'num_gpu': 0, 'num_thread': 1},
        'classifier_source_sha256': hashlib.sha256((ROOT / 'src/classifier.py').read_bytes()).hexdigest(),
        'input_sha256': hashlib.sha256(args.in_path.read_bytes()).hexdigest(),
        'validation': validation, 'metrics': metrics}
    with (args.out_dir / 'summary.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(f"{summary['status']}: {len(scored)}/{len(rows)} câu; output={args.out_dir}")
    return 0 if summary['status'] == 'COMPLETE' else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--in', dest='in_path', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'tmp' / ('real_classifier_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--timeout', type=float, default=90.0)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout phải > 0')
    try:
        return run(args)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'DỪNG: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
