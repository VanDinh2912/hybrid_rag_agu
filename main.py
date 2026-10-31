"""Tiến trình chạy chính (serve): CLI tương tác hỏi - đáp quy chế AGU.

Luồng: kết nối ChromaDB đã persist (không index lại) → chuẩn hóa câu hỏi bằng
Local SLM (Qwen/Ollama) → truy xuất Top-K chunk bằng bge-m3 → Gemini API sinh
câu trả lời có trích dẫn Điều/Khoản → in kết quả trực quan ra màn hình.

Cách chạy:
    python main.py                       # chế độ tương tác, hỏi liên tục
    python main.py "Điều kiện xét tốt nghiệp?"   # hỏi một lần rồi thoát
    python main.py --top-k 6             # đổi số chunk truy xuất
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()  # Nạp .env (GEMINI_API_KEY, OLLAMA_HOST, CHROMA_PERSIST_DIR...)

from src.generator import (
    GeminiGenerator,
    GeneratorError,
    QwenGenerator,
    _env_flag,
    is_fallback_answer,
)
from src.generation.local_slm import LocalSLM, LocalSLMError
from src.core.config import DEFAULT_TOP_K, top_k_from_env
from src.core.pipeline import HybridRAGPipeline
from src.retrieval.vector_db import VectorStoreManager

EXIT_WORDS = {"exit", "quit", "thoat", "thoát", "q"}
HELP_WORDS = {"help", "h", "?", "hd", "huong dan"}

LINE = "=" * 78
THIN = "-" * 78


def _force_utf8_stdout() -> None:
    """Console Windows mặc định cp1258/cp437 sẽ làm lỗi chữ tiếng Việt."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hybrid RAG tra cứu quy chế đào tạo AGU (Local Qwen + Gemini API). "
                    "Chạy không tham số để vào chế độ hỏi đáp tương tác; "
                    "muốn dạy lại hệ thống thì dùng 'python scripts/learn.py'."
    )
    parser.add_argument("query", nargs="?", default=None,
                        help="Câu hỏi cần tra cứu (bỏ trống sẽ vào vòng lặp tương tác)")
    parser.add_argument("-k", "--top-k", type=int,
                        default=top_k_from_env(),
                        help=f"Số chunk ngữ cảnh truy xuất từ ChromaDB (mặc định: {DEFAULT_TOP_K})")
    return parser.parse_args()


def print_help() -> None:
    print(
        "\nHƯỚNG DẪN NHANH\n"
        "  - Gõ câu hỏi bất kỳ bằng tiếng Việt (văn phong đời thường cũng được,\n"
        "    Qwen cục bộ sẽ chuẩn hóa lại trước khi truy xuất).\n"
        "  - 'help'  : in lại hướng dẫn này\n"
        "  - 'exit'  : thoát (hoặc Ctrl+C / Ctrl+Z rồi Enter)\n"
    )


def use_qwen_generator() -> bool:
    """Cờ chế độ offline: USE_QWEN_GENERATOR=1 → Local Qwen làm generator thay Gemini."""
    return _env_flag("USE_QWEN_GENERATOR", False)


def build_generator(use_qwen: bool):
    """Dựng generator theo cờ: Qwen local (offline, không tốn quota) hoặc Gemini API.

    Cờ USE_QWEN_GENERATOR=1 (Bước 0 của P3.3 — trước đó main.py bỏ qua cờ này nên
    mọi smoke đều tiêu quota Gemini thật). Cảnh báo in rõ ràng để người dùng
    biết đang chạy chế độ offline với chất lượng thấp hơn bình thường.
    """
    if use_qwen:
        generator = QwenGenerator()
        print(
            f"      CẢNH BÁO: USE_QWEN_GENERATOR=1 — chế độ OFFLINE, dùng '{generator.model_name}' "
            "làm generator (không tốn quota Gemini, chất lượng câu trả lời thấp hơn bình thường)."
        )
        return generator
    return GeminiGenerator()


def build_pipeline(top_k: int) -> tuple[HybridRAGPipeline, int]:
    """Khởi tạo VectorDB + LocalSLM + Generator; trả về (pipeline, số chunk đã index)."""
    print(LINE)
    print("KHỞI TẠO HỆ THỐNG HYBRID RAG (CHẾ ĐỘ SERVE)")
    print(LINE)

    # Bước 1: nối ChromaDB đã persist. bge-m3 được nạp chỉ để nhúng CÂU HỎI,
    # corpus không bị đọc hay index lại.
    db_manager = VectorStoreManager()
    print(f"[1/3] Kết nối ChromaDB tại '{db_manager.persist_directory}' (không index lại)...")
    vector_db = db_manager.load_vector_store()
    try:
        indexed = vector_db._collection.count()
    except Exception as exc:
        raise SystemExit(
            f"Không đọc được collection trong ChromaDB tại '{db_manager.persist_directory}': {exc}\n"
            "Hãy chạy 'python ingest.py' để nạp corpus từ data/corpus/."
        )
    if indexed == 0:
        raise SystemExit(
            f"ChromaDB tại '{db_manager.persist_directory}' chưa có dữ liệu. "
            "Hãy chạy 'python ingest.py' để nạp corpus từ data/corpus/ trước."
        )
    print(f"      Sẵn sàng: {indexed} chunks (Tầng 1: quy chế gốc, Tầng 2: thông báo/kế hoạch).")

    # Bước 2: Local SLM. Ollama chết thì hệ thống vẫn chạy (dùng câu hỏi gốc),
    # chỉ mất đi bước chuẩn hóa.
    print("[2/3] Kết nối Local SLM (Qwen qua Ollama)...")
    local_slm = LocalSLM()
    ok, message = local_slm.check_connection()
    print(f"      {'OK' if ok else 'CẢNH BÁO'}: {message}")
    if not ok:
        print("      → Vẫn tiếp tục: mọi câu hỏi sẽ được dùng nguyên văn để truy xuất.")

    # Bước 3: Generator. Mặc định Gemini API; USE_QWEN_GENERATOR=1 → Qwen local (offline,
    # không tốn quota — dùng cho smoke test thử nghiệm).
    use_qwen = use_qwen_generator()
    print(f"[3/3] Kết nối generator ({'Local Qwen — OFFLINE' if use_qwen else 'Gemini API'})...")
    try:
        generator = build_generator(use_qwen)
    except GeneratorError as exc:
        engine = "Qwen local" if use_qwen else "Gemini"
        raise SystemExit(f"Lỗi cấu hình generator ({engine}): {exc}")
    print(f"      OK: model '{generator.model_name}', temperature={getattr(generator, 'temperature', '—')}.")
    print(LINE)

    return HybridRAGPipeline(local_slm=local_slm, vector_db=vector_db, generator=generator), indexed


def print_result(result: dict, elapsed: float, offline: bool = False) -> None:
    """In kết quả một lượt hỏi: câu gốc → câu chuẩn hóa → nguồn trích dẫn → trả lời."""
    sources = result.get("sources", [])

    print(f"\n{LINE}")
    print(f"[1] CÂU HỎI GỐC          : {result['raw_query']}")
    print(f"[2] CÂU HỎI CHUẨN HÓA    : {result['normalized_query']}")
    print(f"    (Local Qwen viết lại để tăng độ tương đồng vector khi truy xuất)")

    labels = result.get("labels")
    if labels:
        # P3.5: mục "Phân loại & Cấu hình" — người dùng nhìn thấy tầng phân loại
        # đang làm gì: nhãn được gán + cấu hình truy xuất + có tách truy vấn con.
        cfg = result.get("retrieval_config") or {}
        filter_txt = ",".join(cfg.get("source_filter") or []) or "không"
        sub_queries = result.get("sub_queries") or []
        sub_txt = f"CÓ ({len(sub_queries)} nhánh)" if sub_queries else "KHÔNG"
        print("[2b] PHÂN LOẠI & CẤU HÌNH :")
        print(f"     Chủ đề               : {labels.get('topic')}")
        print(f"     Loại câu hỏi         : {labels.get('question_type')}")
        print(f"     Cấu hình truy xuất   : top_k={cfg.get('top_k')} | bm25={cfg.get('bm25_weight')} "
              f"chroma={cfg.get('chroma_weight')} | lọc nguồn: {filter_txt}")
        print(f"     Tách truy vấn con    : {sub_txt}")
        if sub_queries:
            joined = " | ".join(f"({i}) {q}" for i, q in enumerate(sub_queries, start=1))
            print(f"     Danh sách            : {joined}")

    print(f"[3] NGUỒN TRÍCH DẪN      : {len(sources)} chunk từ ChromaDB")
    if not sources:
        print("      (không truy xuất được ngữ cảnh nào)")
    for src in sources:
        print(f"      #{src['rank']} [{src['tier']}] {src['source']} "
              f"(chunk_id={src['chunk_id']}, {src['chars']:,} ký tự)")
        print(f"         \"{src['preview']}\"")

    if offline:
        engine_label = "Local Qwen — OFFLINE"
    else:
        engine_label = "Local Qwen — FALLBACK" if is_fallback_answer(result["answer"]) else "Gemini"
    print(f"[4] CÂU TRẢ LỜI ({engine_label}) :")
    print(THIN)
    print(result["answer"])
    print(THIN)
    print(f"Thời gian xử lý: {elapsed:.1f}s | Số chunk ngữ cảnh: {len(sources)}")
    print(LINE)


def ask_once(pipeline: HybridRAGPipeline, question: str, top_k: int) -> bool:
    """Chạy một câu hỏi; trả về False nếu người dùng bấm Ctrl+C giữa chừng."""
    started = time.perf_counter()
    engine = getattr(pipeline.generator, "model_name", "Gemini")
    print(f"\nĐang xử lý: chuẩn hóa (Qwen) → truy xuất Top-{top_k} (bge-m3) → sinh câu trả lời ({engine})...")
    try:
        result = pipeline.run(question, top_k=top_k)
    except KeyboardInterrupt:
        print("\n[Đã hủy] Ngắt lượt hỏi này (Ctrl+C). Gõ 'exit' để thoát hẳn.")
        return False
    except GeneratorError as exc:
        print(f"\n[LỖI GEMINI] {exc}")
        return True
    except LocalSLMError as exc:
        print(f"\n[LỖI OLLAMA] {exc}")
        return True
    except ValueError as exc:
        print(f"\n[LỖI DỮ LIỆU] {exc}")
        return True
    except Exception as exc:
        print(f"\n[LỖI KHÔNG MONG ĐỢI] {type(exc).__name__}: {exc}")
        return True

    print_result(result, time.perf_counter() - started, offline=use_qwen_generator())
    return True


def interactive_loop(pipeline: HybridRAGPipeline, top_k: int) -> None:
    print(f"\nCHẾ ĐỘ HỎI ĐÁP TƯƠNG TÁC — {top_k} chunk ngữ cảnh mỗi lượt.")
    print("Gõ 'help' để xem hướng dẫn, 'exit' để thoát.\n")
    while True:
        try:
            question = input("Câu hỏi > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt.")
            return
        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            print("Tạm biệt.")
            return
        if question.lower() in HELP_WORDS:
            print_help()
            continue
        ask_once(pipeline, question, top_k)


def main() -> None:
    _force_utf8_stdout()
    args = parse_args()
    top_k = max(1, args.top_k)

    pipeline, _indexed = build_pipeline(top_k)

    if args.query:
        ok = ask_once(pipeline, args.query, top_k)
        sys.exit(0 if ok else 1)

    interactive_loop(pipeline, top_k)


if __name__ == "__main__":
    main()
