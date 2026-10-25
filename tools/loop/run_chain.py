"""Chạy một CHUỖI round bằng một lệnh, có manifest tái lập được.

Vì sao có file này (T7): mỗi round trong quá khứ được chạy bằng một driver `.sh` viết tay trong
`tmp/` (`r5_driver.sh`, `r7_driver.sh`, …). Driver tay thì (a) không ai biết round đó đã export
những biến nào nếu log bị mất, (b) dễ quên một biến và biến phép so sánh "một biến" thành sai,
(c) không tái lập được. File này thay các driver đó bằng **một spec JSON** + **một manifest** ghi
đúng argv và đúng các biến môi trường đã export cho từng bước.

Cách dùng tối thiểu:

    # chỉ in lệnh, không chạy gì (an toàn, đọc được spec trước khi tốn giờ)
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/run_chain.py \
        --chain tools/loop/chains/t5a_reranker.json --dry-run

    # chạy thật
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/run_chain.py \
        --chain tools/loop/chains/t5a_reranker.json

Hoặc qua wrapper: `tools/loop/run_chain.ps1 -Chain <spec> [-DryRun]` / `tools/loop/run_chain.sh <spec>`.

Ba bảo đảm (đúng T7):
1. **Dry-run không chạy gì**: chỉ in argv + env của từng bước và (tuỳ chọn) ghi manifest.
2. **Thiếu env bắt buộc thì dừng TRƯỚC bước đầu tiên** (preflight), không chạy nửa chuỗi.
3. **Không ghi đè round đã có**: nếu thư mục round đã có file thì DỪNG, trừ khi `--resume`
   (resume dùng đúng ngữ nghĩa sẵn có của `run_round.py`: bỏ qua id đã chạy).
4. **Manifest tất định**: cùng spec ⇒ cùng bytes manifest (không timestamp, key sắp xếp, có
   `spec_sha256`), nên hai lần dry-run so được bằng `diff`.

KHÔNG làm gì ngoài việc gọi công cụ sẵn có: `tools/loop/run_round.py`, `tools/loop/gate.py`,
`tools/loop/attribute.py`. Không sửa dữ liệu, không chấm lại round cũ, không gọi model trực tiếp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON.exists():  # môi trường khác Windows / venv đặt chỗ khác
    PYTHON = Path(sys.executable)

VALID_PHASES = {"retrieval", "full"}
# Biến trong danh sách này KHÔNG được đặt trong spec (bí mật/đường dẫn máy):
# spec phải tái lập được giữa các máy, còn key thì không được ghi ra đĩa.
FORBIDDEN_ENV_PREFIXES = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")
FORBIDDEN_ENV_NAMES = {"CHROMA_API_KEY"}


class ChainError(RuntimeError):
    """Lỗi cấu hình/điều kiện tiên quyết — dừng chuỗi, không chạy bước nào."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_spec(path: Path) -> dict:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ChainError(f"Không thấy spec: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ChainError(f"Spec không phải JSON hợp lệ ({path}): {exc}") from exc
    if not isinstance(spec, dict):
        raise ChainError("Spec phải là một object JSON.")
    spec.setdefault("name", path.stem)
    spec.setdefault("defaults", {})
    spec.setdefault("requires", [])
    spec.setdefault("out_root", str(ROOT / "data" / "loop" / "rounds"))
    rounds = spec.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        raise ChainError("Spec phải có 'rounds' là danh sách không rỗng.")
    seen: set[str] = set()
    for n, step in enumerate(rounds, 1):
        if not isinstance(step, dict) or not step.get("round"):
            raise ChainError(f"Bước {n}: thiếu 'round'.")
        name = step["round"]
        if name in seen:
            raise ChainError(f"Bước {n}: round '{name}' bị lặp trong cùng chuỗi.")
        seen.add(name)
        phase = step.get("phase", "retrieval")
        if phase not in VALID_PHASES:
            raise ChainError(f"Bước {n}: phase '{phase}' không hợp lệ ({sorted(VALID_PHASES)}).")
        for key in ("env", "defaults"):
            block = step.get(key, {})
            if not isinstance(block, dict):
                raise ChainError(f"Bước {n}: '{key}' phải là object.")
            for k in block:
                if k.startswith(FORBIDDEN_ENV_PREFIXES) or k in FORBIDDEN_ENV_NAMES:
                    raise ChainError(
                        f"Bước {n}: biến '{k}' là bí mật/không tái lập được — không được đặt trong spec."
                    )
    return spec


def parse_kv(pairs: list[str]) -> dict:
    out: dict = {}
    for raw in pairs:
        if "=" not in raw:
            raise ChainError(f"--set cần dạng KEY=VALUE, nhận: {raw!r}")
        k, v = raw.split("=", 1)
        k = k.strip()
        if not k:
            raise ChainError(f"--set có tên biến rỗng: {raw!r}")
        out[k] = v
    return out


def step_env(spec: dict, step: dict, cli_env: dict) -> dict:
    """Env của bước = defaults cấp chuỗi → defaults cấp bước → env cấp bước → --set (ưu tiên cuối)."""
    merged: dict = {}
    merged.update(spec.get("defaults") or {})
    merged.update(step.get("defaults") or {})
    merged.update(step.get("env") or {})
    merged.update(cli_env)
    return merged


def _rel(path: Path | str) -> str:
    """Đường dẫn tương đối với repo khi nằm trong repo — để manifest/diff không phụ thuộc ổ đĩa."""
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def step_argv(spec: dict, step: dict) -> list[str]:
    phase = step.get("phase", "retrieval")
    argv = [_rel(PYTHON), "tools/loop/run_round.py",
            "--round", step["round"],
            "--phase", phase,
            "--out-root", str(step.get("out_root") or spec["out_root"])]
    if step.get("testset"):
        argv += ["--testset", str(step["testset"])]
    argv += ["--split", str(step.get("split", "all"))]
    if step.get("families"):
        argv += ["--families", str(step["families"])]
    argv += ["--top-k", str(step.get("top_k", 6))]
    argv += ["--generator", str(step.get("generator", "offline_qwen"))]
    if step.get("limit"):
        argv += ["--limit", str(step["limit"])]
    if step.get("strategy"):
        argv += ["--strategy", str(step["strategy"])]
    if step.get("pin_subset_from"):
        argv += ["--pin-subset-from", str(step["pin_subset_from"])]
    if step.get("only_retrieved"):
        argv += ["--only-retrieved"]
    if step.get("normalize_query"):
        argv += ["--normalize-query"]
    return argv


def post_argv(spec: dict, step: dict) -> list[tuple[str, list[str]]]:
    """Các bước chấm sau round: gate + attribute (nếu spec khai)."""
    out: list[tuple[str, list[str]]] = []
    phase = step.get("phase", "retrieval")
    # Cổng và attribute phải đọc ĐÚNG gốc round của chuỗi. Bỏ sót chỗ này làm spec demo
    # (out_root riêng) chạy round xong mà cổng lại đi tìm ở data/loop/rounds — đã gặp thật.
    rounds_root = str(step.get("out_root") or spec["out_root"])
    gate = step.get("gate")
    if gate:
        if not isinstance(gate, dict) or not gate.get("baseline"):
            raise ChainError(f"Round '{step['round']}': 'gate' phải có 'baseline'.")
        argv = [_rel(PYTHON), "tools/loop/gate.py",
                "--candidate", step["round"], "--baseline", str(gate["baseline"]),
                "--phase", str(gate.get("phase", phase)),
                "--rounds-root", rounds_root]
        if gate.get("out"):
            argv += ["--out", str(gate["out"])]
        out.append(("gate", argv))
    attribute = step.get("attribute")
    if attribute:
        if not isinstance(attribute, dict):
            raise ChainError(f"Round '{step['round']}': 'attribute' phải là object.")
        argv = [_rel(PYTHON), "tools/loop/attribute.py",
                "--round", step["round"], "--phase", str(attribute.get("phase", phase))]
        if attribute.get("compare"):
            argv += ["--compare", str(attribute["compare"])]
        argv += ["--rounds-root", rounds_root]
        out.append(("attribute", argv))
    return out


def preflight(spec: dict, steps: list[dict], cli_env: dict) -> None:
    """Kiểm MỌI điều kiện trước khi chạy bước đầu: thiếu gì báo ngay, không chạy nửa chuỗi."""
    problems: list[str] = []
    for var in spec.get("requires") or []:
        if not os.environ.get(var):
            problems.append(f"thiếu biến môi trường bắt buộc: {var}")
    for step in steps:
        if step.get("require"):
            env = step_env(spec, step, cli_env)
            for var in step["require"]:
                if not (env.get(var) or os.environ.get(var)):
                    problems.append(f"round '{step['round']}': thiếu biến bắt buộc {var}")
        phase = step.get("phase", "retrieval")
        if phase == "full" and (step.get("pin_subset_from") is None) and step.get("limit"):
            # Không phải lỗi cứng, nhưng là cái bẫy đã có thật: full + limit cần pin để cùng thang đo.
            print(
                f"[chain] CẢNH BÁO round '{step['round']}': phase=full có --limit mà không "
                "'pin_subset_from' — cổng sẽ so trên tập khác nhau.",
                file=sys.stderr,
            )
    if problems:
        raise ChainError("Preflight thất bại:\n  - " + "\n  - ".join(problems))


def ensure_round_dir_free(spec: dict, step: dict, resume: bool) -> Path:
    out_root = Path(step.get("out_root") or spec["out_root"])
    target = out_root / step["round"]
    if target.exists() and any(target.iterdir()) and not resume:
        raise ChainError(
            f"Thư mục round đã có dữ liệu: {target}\n"
            "  Không ghi đè (bất biến của repo). Dùng round mới, hoặc --resume nếu muốn chạy tiếp."
        )
    return target


def build_manifest(spec: dict, spec_path: Path, steps: list[dict], cli_env: dict) -> dict:
    rows = []
    for step in steps:
        env = step_env(spec, step, cli_env)
        rows.append(
            {
                "round": step["round"],
                "phase": step.get("phase", "retrieval"),
                "argv": step_argv(spec, step),
                "env": dict(sorted(env.items())),
                "post": [
                    {"tool": tool, "argv": argv} for tool, argv in post_argv(spec, step)
                ],
            }
        )
    manifest = {
        "chain": spec["name"],
        "spec_path": _rel(spec_path),
        "spec_sha256": _sha256_file(spec_path),
        "out_root": str(spec["out_root"]),
        "requires": sorted(spec.get("requires") or []),
        "steps": rows,
    }
    # Chuỗi JSON tất định: key sắp xếp, không timestamp, ensure_ascii=False để diff đọc được.
    return json.loads(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


def _fmt_env(env: dict) -> str:
    if not env:
        return "(không đặt thêm biến nào)"
    return " ".join(f"{k}={v}" for k, v in sorted(env.items()))


def _gate_out_path(argv: list[str], step: dict, spec: dict) -> Path | None:
    """Đường dẫn báo cáo cổng: lấy --out nếu spec đặt, nếu không theo mặc định của gate.py."""
    if "--out" in argv:
        idx = argv.index("--out")
        return Path(argv[idx + 1])
    root = Path(step.get("out_root") or spec["out_root"])
    phase = step.get("phase", "retrieval")
    gate = step.get("gate") or {}
    if not gate.get("baseline"):
        return None
    return root / step["round"] / f"gate_vs_{gate['baseline']}_{gate.get('phase', phase)}.json"


def run_step(spec: dict, step: dict, cli_env: dict) -> None:
    env = dict(os.environ)
    env.update({k: str(v) for k, v in step_env(spec, step, cli_env).items()})
    env.setdefault("PYTHONIOENCODING", "utf-8")
    argv = step_argv(spec, step)
    print(f"\n[chain] === {step['round']} ({step.get('phase', 'retrieval')}) ===")
    print(f"[chain] env: {_fmt_env(step_env(spec, step, cli_env))}")
    print(f"[chain] argv: {' '.join(argv)}")
    proc = subprocess.run(argv, cwd=str(ROOT), env=env)
    if proc.returncode != 0:
        raise ChainError(f"round '{step['round']}' thoát với mã {proc.returncode} — dừng chuỗi.")
    for tool, post in post_argv(spec, step):
        print(f"[chain] {tool}: {' '.join(post)}")
        proc = subprocess.run(post, cwd=str(ROOT), env=env)
        if proc.returncode == 0:
            continue
        if tool == "gate":
            # `gate.py` trả 1 cho "cổng KHÔNG ĐẠT" — đó là KẾT QUẢ cần ghi lại, không phải lỗi
            # hạ tầng. Chuỗi phải đi tiếp để attribute.py cũng chạy trên round âm đó (nếu dừng,
            # người tái lập không bao giờ có báo cáo quy lỗi của chính kết quả âm).
            out_path = _gate_out_path(post, step, spec)
            if out_path and out_path.exists():
                try:
                    verdict = json.loads(out_path.read_text(encoding="utf-8")).get("passed")
                except json.JSONDecodeError:
                    verdict = None
                print(
                    f"[chain] gate trả mã {proc.returncode} — đã có báo cáo {_rel(out_path)} "
                    f"(passed={verdict}); tiếp tục chuỗi."
                )
                continue
        raise ChainError(f"{tool} sau '{step['round']}' thoát với mã {proc.returncode} — dừng chuỗi.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy một chuỗi round từ spec JSON (T7).")
    parser.add_argument("--chain", required=True, help="Đường dẫn spec JSON (xem tools/loop/chains/).")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in argv + env, không chạy gì.")
    parser.add_argument("--resume", action="store_true", help="Cho phép chạy tiếp vào thư mục round đã có.")
    parser.add_argument("--set", dest="sets", action="append", default=[], metavar="KEY=VALUE",
                        help="Ghi đè env của MỌI bước (lặp lại được). Không nhận biến bí mật.")
    parser.add_argument("--manifest-out", default="",
                        help="Ghi manifest JSON (mặc định data/loop/diag/chain_manifest_<name>.json; '-' = stdout).")
    parser.add_argument("--no-manifest", action="store_true", help="Không ghi manifest.")
    parser.add_argument("--only", default="", help="Chỉ chạy round có tên này (vẫn dry-run cả chuỗi).")
    args = parser.parse_args()

    spec_path = Path(args.chain)
    if not spec_path.is_absolute():
        spec_path = (ROOT / spec_path).resolve()
    try:
        spec = load_spec(spec_path)
        cli_env = parse_kv(args.sets)
        for k in cli_env:
            if k.startswith(FORBIDDEN_ENV_PREFIXES) or k in FORBIDDEN_ENV_NAMES:
                raise ChainError(
                    f"--set {k}=… bị từ chối: biến bí mật không được đi qua spec/manifest "
                    "(export nó trong shell trước khi gọi)."
                )
        steps = spec["rounds"]
        preflight(spec, steps, cli_env)
        manifest = build_manifest(spec, spec_path, steps, cli_env)
        if not args.no_manifest:
            if args.manifest_out == "-":
                text = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
                print(text)
            else:
                out = Path(args.manifest_out) if args.manifest_out else (
                    ROOT / "data" / "loop" / "diag" / f"chain_manifest_{spec['name']}.json"
                )
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"[chain] manifest: {out}")
        if args.dry_run:
            print(f"[chain] DRY-RUN '{spec['name']}' — {len(steps)} bước, không chạy gì.")
            for n, row in enumerate(manifest["steps"], 1):
                print(f"\n[{n}/{len(steps)}] round={row['round']} phase={row['phase']}")
                print(f"  env : {_fmt_env(row['env'])}")
                for tool, post in post_argv(spec, steps[n - 1]):
                    print(f"  post: {tool} → {' '.join(post)}")
                print(f"  argv: {' '.join(row['argv'])}")
            return 0
        # Chạy thật: kiểm ĐỦ mọi thư mục đích trước khi chạy bước đầu (preflight ghi đè).
        for step in steps:
            ensure_round_dir_free(spec, step, args.resume)
        for step in steps:
            if args.only and step["round"] != args.only:
                print(f"[chain] bỏ qua {step['round']} (--only {args.only})")
                continue
            run_step(spec, step, cli_env)
        print(f"[chain] xong '{spec['name']}'.")
        return 0
    except ChainError as exc:
        print(f"[chain] DỪNG: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
