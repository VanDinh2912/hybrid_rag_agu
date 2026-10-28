"""Kiểm thử T5 (mục 7–10) — CONTEXTUAL CHUNK HEADER, module build-time thuần.

Bốn mục của đề bài:
  7. Header gồm đúng tên văn bản + Chương/Điều/Khoản của chunk; chunk không có Điều
     (bảng, phụ lục) có nhãn dự phòng rõ ràng, không "None"/chuỗi rỗng.
  8. Header đi qua cùng fold/chuẩn hóa như nội dung; BM25 tokenization không hỏng —
     truy vấn trùng tên Điều/Khoản phải tìm thấy chunk tương ứng.
  9. Header vào phần ngữ cảnh gửi generator THEO THIẾT KẾ (nó là một phần của
     `page_content`, giống header production hiện có); phần HIỂN THỊ NGUỒN và định
     danh citation lấy từ metadata nên không bị header làm sai. Test ghim cả hai vế.
  10. Index mới phải ghi vào thư mục khác; index cũ giữ nguyên (so băm). Module có
      `ensure_separate_index_target` chặn ghi đè; test băm BẢN SAO của `chroma_db/` và
      `chroma_db_vie/` trước/sau khi chuyển đổi header trong bộ nhớ. C1: Chroma tự ghi lại
      container khi mở, nên chỉ được mở bản sao trong `tmp_path`, không mở index sản xuất.

GIỚI HẠN PHẢI NÓI RÕ: T5b chưa được phép build index thật (PA-1 chốt corpus), nên
mục 10 chỉ xanh ở mức "hàm chuyển đổi + chốt chặn + băm index cũ". Test dựng một index
Chroma TÍ HON trong `tmp_path` để chứng minh ghi được vào thư mục khác, KHÔNG phải
index 342 chunk của corpus. Xem docs/reports/test_T5.md.

Không gọi model; Chroma thật chỉ được COPY vào `tmp_path` rồi đọc bản sao (không mở trực
tiếp index sản xuất). Bất biến #6: không đọc trường vàng nào của testset.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import chromadb
import pytest
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from src.indexing.contextual_header import (
    DEFAULT_TITLE,
    ENABLE_CONTEXTUAL_HEADER_ENV,
    FALLBACK_APPENDIX,
    FALLBACK_PREAMBLE,
    FALLBACK_TABLE,
    FALLBACK_WHOLE,
    PROTECTED_INDEX_DIRS,
    apply_contextual_headers,
    build_header,
    chapter_spans,
    chapters_for_chunks,
    contextual_header_enabled,
    contextualize_text,
    directory_digest,
    ensure_separate_index_target,
    looks_like_table,
    parse_chunk,
)
from src.core.pipeline import HybridRAGPipeline, describe_document
from src.retrieval.vector_db import bm25_tokenize

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_INDEXES = {"chroma_db": 361, "chroma_db_vie": 342}

#: Đường dẫn thật của từng index đo được (tái cấu trúc 28-10: bản thực nghiệm dời vào
#: `indexes/experimental/`, index sản xuất vẫn ở gốc). Tên khoá = tên param test để id
#: collection KHÔNG đổi; số chunk trong REAL_INDEXES giữ nguyên — đây chỉ là sửa
#: đường dẫn trỏ tới thư mục đã di chuyển, không phải nới kỳ vọng đo.
REAL_INDEX_PATHS = {
    "chroma_db": "chroma_db",
    "chroma_db_vie": "indexes/experimental/chroma_db_vie",
}

HEADER_ENVS = (
    ENABLE_CONTEXTUAL_HEADER_ENV,
    "ENABLE_RERANKER",
    "ENABLE_CLASSIFIER",
    "ENABLE_DECOUPLED_REFUSAL",
    "ENABLE_EVIDENCE_SELECTION",
    "ENABLE_QUERY_EXPANSION",
    "ROUTER_SOFT_FILTER",
    "ROUTER_SOURCE_QUOTA",
    "BM25_WEIGHT",
    "CHROMA_WEIGHT",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in HEADER_ENVS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def real_index_copy(tmp_path):
    """Bản sao tạm của index thật — Chroma ghi vào bản sao, index sản xuất không bị chạm.

    Mở `chromadb.PersistentClient` làm Chroma ghi lại sqlite/HNSW container; đọc bản sao giữ
    `ARTIFACT_MANIFEST.json` khớp byte và không đổi index đang dùng cho round/benchmark.
    """

    def _copy(db_name: str) -> Path:
        rel = REAL_INDEX_PATHS.get(db_name, db_name)
        src = REPO_ROOT / rel
        if not src.exists():
            pytest.skip(f"không có {rel}")
        dst = tmp_path / Path(rel).name  # bản sao giữ tên cuối để chốt PROTECTED còn khớp
        shutil.copytree(src, dst)
        return dst

    return _copy


def md(source: str, chunk_id: int, tier: str = "Tầng 1") -> dict:
    return {"source": source, "tier": tier, "chunk_id": chunk_id}


# ================================================================ 7. HÌNH DẠNG HEADER
ARTICLE_CHUNK = (
    "[1054-qd-dhag-2020-09-28.pdf] - [Điều 8.] \n"
    " 1. Sinh viên ở ký túc xá đóng phí mỗi tháng.\n"
    "2. Phí được nộp theo học kỳ.\n"
    "a) Mức phí do nhà trường quy định.\n"
    "b) Miễn phí cho diện chính sách."
)


class TestBayHinhDangHeader:
    def test_header_du_ten_dieu_khoan_diem(self):
        header, body = build_header(ARTICLE_CHUNK)
        assert header.render() == (
            "[1054-qd-dhag-2020-09-28.pdf] - [Điều 8] - [Khoản 1-2] - [Điểm a-b]"
        )
        assert header.labels() == [
            "1054-qd-dhag-2020-09-28.pdf",
            "Điều 8",
            "Khoản 1-2",
            "Điểm a-b",
        ]
        assert body == parse_chunk(ARTICLE_CHUNK).body

    def test_chuong_chi_xuat_hien_khi_co_tieu_de_trong_chunk(self):
        without = "[A.pdf] - [Điều 8.] \n 1. Nội dung."
        with_chapter = "[A.pdf] - [Điều 8.] \n CHƯƠNG II\nQUY ĐỊNH VỀ HỌC PHÍ\n1. Nội dung."
        assert "Chương" not in build_header(without)[0].render()
        assert build_header(with_chapter)[0].render() == (
            "[A.pdf] - [Chương II] - [Điều 8] - [Khoản 1]"
        )

    def test_chuong_truyen_tu_build_theo_thu_tu_tai_lieu(self):
        full_text = (
            "CHƯƠNG I\nQUY ĐỊNH CHUNG\n"
            "Điều 1. Phạm vi điều chỉnh\nNội dung một.\n\n"
            "CHƯƠNG II\nHỌC PHÍ\n"
            "Điều 8. Mức thu\nNội dung hai.\n"
        )
        chunks = [
            "[A.pdf] - [Điều 1.] \nPhạm vi điều chỉnh\nNội dung một.",
            "[A.pdf] - [Điều 8.] \nMức thu\nNội dung hai.",
        ]
        chapters = chapters_for_chunks(full_text, chunks)
        assert chapters == ["Chương I", "Chương II"]
        decorated = contextualize_text(chunks[1], chapter=chapters[1])
        assert "[Chương II] - [Điều 8]" in decorated

    def test_chunk_bang_co_nhan_du_phong_bang_bieu(self):
        table = "[A.pdf]\n| Khoản | Nội dung |\n|---|---|\n| 1 | A |\n| 2 | B |"
        assert looks_like_table(parse_chunk(table).body) is True
        assert build_header(table)[0].render() == "[A.pdf] - [Bảng biểu]"

    def test_chunk_phu_luc_co_nhan_du_phong_phu_luc(self):
        appendix = "[A.pdf]\nPHỤ LỤC 1\nDANH MỤC HỒ SƠ"
        assert build_header(appendix)[0].render() == "[A.pdf] - [Phụ lục]"

    def test_chunk_mo_dau_giu_nhan_phan_mo_dau(self):
        preamble = "[A.pdf] - [Phần mở đầu] \n QUYẾT ĐỊNH"
        assert build_header(preamble)[0].render() == "[A.pdf] - [Phần mở đầu]"

    def test_chunk_khong_dieu_khong_bang_phu_luc_co_nhan_toan_van(self):
        plain = "[A.pdf]\nThông báo về việc nộp học phí."
        assert build_header(plain)[0].render() == "[A.pdf] - [Toàn văn]"

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "[A.pdf]",
            "[A.pdf]\n",
            "[None] - [None]\n nội dung",
            "[A.pdf] - []\n nội dung",
            "không có header",
        ],
    )
    def test_khong_bao_gio_co_none_hay_nhan_rong(self, text):
        header, _body = build_header(text)
        rendered = header.render()
        assert rendered
        assert "None" not in rendered
        assert "[]" not in rendered
        labels = header.labels()
        assert labels and all(label.strip() for label in labels)
        assert labels[0] == header.title and labels[0] != ""

    @pytest.mark.parametrize(
        "text,expected_title",
        [
            ("[None] - [Điều 8.]\n nội dung", DEFAULT_TITLE),
            ("[] - [Điều 8.]\n nội dung", DEFAULT_TITLE),
            ("", DEFAULT_TITLE),
            ("[A.pdf] - [Điều 8.]\n nội dung", "A.pdf"),
        ],
    )
    def test_title_du_phong_khi_thieu(self, text, expected_title):
        assert build_header(text)[0].title == expected_title

    def test_than_chunk_giu_nguyen_van_tung_ky_tu(self):
        out = contextualize_text(ARTICLE_CHUNK)
        body = parse_chunk(ARTICLE_CHUNK).body
        assert out.endswith(body)
        assert out == build_header(ARTICLE_CHUNK)[0].render() + "\n" + body
        # Dòng header cũ bị THAY, không bị nhân đôi.
        assert out.count("1054-qd-dhag-2020-09-28.pdf") == 1

    def test_hau_to_phan_i_n_duoc_giu(self):
        chunk = "[A.pdf] - [Điều 7.] (phần 2/3) \n 1. Nội dung phần hai."
        assert build_header(chunk)[0].render() == (
            "[A.pdf] - [Điều 7] - [Khoản 1] (phần 2/3)"
        )

    def test_idempotent_khong_cong_don_nhan(self):
        for text in (
            ARTICLE_CHUNK,
            "[A.pdf] - [Điều 8.] (phần 2/3) \n 1. Nội dung.",
            "[A.pdf] - [Phần mở đầu] \n QUYẾT ĐỊNH",
            "[A.pdf]\n| A | B |\n|---|---|\n| 1 | 2 |",
            "không header",
            "",
        ):
            once = contextualize_text(text)
            assert contextualize_text(once) == once, f"không idempotent: {text!r}"


# ================================================================ 8. FOLD + BM25
class TestTamFoldVaBM25:
    def test_bm25_tokenize_header_sinh_ca_hai_dang(self):
        tokens = bm25_tokenize("[A.pdf] - [Điều 8] - [Khoản 2] - [Điểm a]")
        assert "điều" in tokens and "dieu" in tokens
        assert "khoản" in tokens and "khoan" in tokens
        assert "điểm" in tokens and "diem" in tokens

    def _corpus(self):
        plain = [
            Document(
                page_content="[A.pdf] - [Điều 9.] \n 1. Học bổng được xét mỗi học kỳ.",
                metadata=md("A.pdf", 2),
            ),
            Document(
                page_content="[B.pdf] - [Điều 12.] \n 1. Thư viện mở cửa đến 19 giờ.",
                metadata=md("B.pdf", 3),
            ),
            Document(
                page_content=(
                    "[A.pdf] - [Điều 8.] \n 1. Sinh viên ở ký túc xá đóng phí mỗi tháng.\n"
                    "2. Phí được nộp theo học kỳ."
                ),
                metadata=md("A.pdf", 1),
            ),
        ]
        return [
            Document(page_content=contextualize_text(d.page_content), metadata=dict(d.metadata))
            for d in plain
        ]

    @pytest.mark.parametrize("query", ["Điều 8", "dieu 8", "Khoản 2", "khoan 2"])
    def test_truy_van_trung_ten_dieu_khoan_tim_thay_chunk(self, query):
        retriever = BM25Retriever.from_documents(self._corpus(), preprocess_func=bm25_tokenize)
        retriever.k = 1
        hits = retriever.invoke(query)
        assert [d.metadata["chunk_id"] for d in hits] == [1], query

    def test_header_khong_lam_hong_truy_van_ten_dieu_khac(self):
        retriever = BM25Retriever.from_documents(self._corpus(), preprocess_func=bm25_tokenize)
        retriever.k = 1
        assert [d.metadata["chunk_id"] for d in retriever.invoke("Điều 12")] == [3]

    def test_header_duoc_fold_nhu_noi_dung(self):
        from src.text_utils import fold

        header = build_header(ARTICLE_CHUNK)[0].render()
        folded = fold(header)
        assert "điều" not in folded and "dieu" in folded
        assert "khoản" not in folded and "khoan" in folded
        # Fold không rỗng và vẫn giữ số hiệu để BM25 khớp.
        assert "8" in folded and "1-2" in folded


# ================================================================ 9. NGỮ CẢNH / NGUỒN
class FakeEnsemble:
    def __init__(self, docs):
        self.docs = docs
        self.retrievers = []
        self.weights = [0.5, 0.5]

    def invoke(self, query):
        return list(self.docs)


class FakeLocalSLM:
    def generate(self, prompt, temperature=0.0):
        return QUESTION


class StubGenerator:
    def __init__(self):
        self.calls = 0
        self.received_docs = []

    def generate_answer(self, query, retrieved_docs, **kwargs):
        self.calls += 1
        self.received_docs = list(retrieved_docs)
        return "Câu trả lời mẫu."


QUESTION = "Sinh viên ở ký túc xá đóng phí bao nhiêu?"


def decorated_docs():
    originals = [
        ("A.pdf", "[A.pdf] - [Điều 8.]", " 1. Sinh viên ở ký túc xá đóng phí mỗi tháng.\n2. Nộp theo học kỳ."),
        ("A.pdf", "[A.pdf] - [Điều 9.]", " 1. Học bổng được xét mỗi học kỳ."),
        ("B.pdf", "[B.pdf] - [Điều 12.]", " 1. Thư viện mở cửa đến 19 giờ."),
    ]
    docs = []
    for i, (source, head, body) in enumerate(originals, start=1):
        text = contextualize_text(f"{head} \n{body}")
        docs.append(Document(page_content=text, metadata=md(source, i)))
    return docs


class TestChinContextVaNguon:
    def _run(self, docs):
        gen = StubGenerator()
        pipeline = HybridRAGPipeline(
            vector_db=None,
            local_slm=FakeLocalSLM(),
            generator=gen,
            retriever=FakeEnsemble(docs),
            oversample_factor=2,
        )
        return pipeline.run(QUESTION, top_k=2), gen

    def test_contexts_chua_header_theo_thiet_ke_va_than_nguyen_van(self):
        docs = decorated_docs()
        result, gen = self._run(docs)
        assert gen.calls == 1
        assert result["contexts"] == [d.page_content for d in gen.received_docs]
        assert result["contexts"] == [docs[0].page_content, docs[1].page_content]
        for context, original in zip(result["contexts"], docs[:2]):
            assert context.startswith("[A.pdf] - [Điều ")
            # Thân sau header vẫn là chuỗi con nguyên văn của chunk gốc.
            body = parse_chunk(context).body
            assert body == parse_chunk(original.page_content).body

    def test_sources_lay_dinh_danh_tu_metadata_khong_tu_header(self):
        docs = decorated_docs()
        result, _gen = self._run(docs)
        assert len(result["sources"]) == len(docs)
        for source, doc in zip(result["sources"], docs):
            assert source["source"] == doc.metadata["source"]
            assert source["chunk_id"] == doc.metadata["chunk_id"]
            assert source["tier"] == doc.metadata["tier"]
            assert source["rank"] == doc.metadata["chunk_id"]
            assert "None" not in source["preview"]

    def test_preview_la_ban_thu_nguyen_van_cua_context_co_header(self):
        """Preview là mặt HIỂN THỊ của chính page_content — header đi vào đây là chủ ý."""
        docs = decorated_docs()
        result, _gen = self._run(docs)
        for source, doc in zip(result["sources"], docs):
            assert source["preview"].startswith("[")
            assert source["chars"] == len(doc.page_content)
            assert source["preview"] == describe_document(doc, source["rank"] - 1)["preview"]

    def test_prompt_generator_nhan_header_trong_content_nguon_van_tu_metadata(self):
        from src.generator import build_prompt

        docs = decorated_docs()
        result, _gen = self._run(docs)
        dict_docs = []
        for source, content in zip(result["sources"][:2], result["contexts"]):
            dict_docs.append(
                {
                    "source": source["source"],
                    "tier": source["tier"],
                    "chunk_id": source["chunk_id"],
                    "content": content,
                }
            )
        prompt = build_prompt(QUESTION, dict_docs)
        assert "[A.pdf] - [Điều 8] - [Khoản 1-2]" in prompt  # content: có header (chủ ý)
        assert "Nguồn: A.pdf |" in prompt  # citation: lấy metadata
        assert "Nguồn: [A.pdf]" not in prompt  # không lấy header làm nguồn

    def test_tat_co_thi_context_khong_bi_chen_header(self):
        originals = ["[A.pdf] - [Điều 8.] \n 1. Nội dung."]
        assert apply_contextual_headers(originals) == originals
        assert contextual_header_enabled() is False


# ================================================================ 10. INDEX RIÊNG + BĂM
class TestMuoiIndexRiengVaBam:
    def test_co_tat_tra_lai_dung_chuoi_dau_vao(self):
        texts = [ARTICLE_CHUNK, "[A.pdf] - [Phần mở đầu] \n X", "không header"]
        out = apply_contextual_headers(texts)
        assert out == texts
        assert all(a is b or a == b for a, b in zip(out, texts))

    def test_co_bat_ap_header_cho_tung_chunk(self, monkeypatch):
        monkeypatch.setenv(ENABLE_CONTEXTUAL_HEADER_ENV, "1")
        texts = ["[A.pdf] - [Điều 8.] \n 1. Nội dung.", "[A.pdf] - [Phần mở đầu] \n X"]
        out = apply_contextual_headers(texts)
        assert out[0].startswith("[A.pdf] - [Điều 8] - [Khoản 1]")
        assert out[1].startswith("[A.pdf] - [Phần mở đầu]")

    def test_titles_chapters_sai_do_dai_bi_tu_choi(self, monkeypatch):
        monkeypatch.setenv(ENABLE_CONTEXTUAL_HEADER_ENV, "1")
        with pytest.raises(ValueError):
            apply_contextual_headers(["a"], titles=["A", "B"])
        with pytest.raises(ValueError):
            apply_contextual_headers(["a"], chapters=["Chương I", "Chương II"])

    def test_guard_tu_choi_ghi_de_index_cu(self, tmp_path):
        (tmp_path / "chroma_db").mkdir()
        (tmp_path / "chroma_db" / "chroma.sqlite3").write_bytes(b"old")
        for target in ("chroma_db", "chroma_db/headers", "chroma_db_vie"):
            with pytest.raises(ValueError):
                ensure_separate_index_target(target, repo_root=tmp_path)
        with pytest.raises(ValueError):
            ensure_separate_index_target(tmp_path, repo_root=tmp_path)
        accepted = ensure_separate_index_target("chroma_db_headers", repo_root=tmp_path)
        assert accepted == (tmp_path / "chroma_db_headers").resolve()

    def test_guard_tu_choi_la_thu_muc_cha_cua_index_cu(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "chroma_db").mkdir()
        with pytest.raises(ValueError):
            ensure_separate_index_target(
                "data", protected=["data/chroma_db"], repo_root=tmp_path
            )

    def test_index_ti_hon_ghi_vao_thu_muc_khac_index_cu_nguyen_bam(self, tmp_path):
        old_dir = tmp_path / "chroma_db"
        old_dir.mkdir()
        (old_dir / "chroma.sqlite3").write_bytes(b"du lieu index cu")
        before = directory_digest(old_dir)

        target = ensure_separate_index_target("chroma_db_headers", repo_root=tmp_path)
        client = chromadb.PersistentClient(path=str(target))
        collection = client.create_collection("agu_regulations")
        docs = ["[A.pdf] - [Điều 8.] \n 1. Nội dung.", "[A.pdf] - [Điều 9.] \n 1. Nội dung khác."]
        collection.add(
            ids=["a", "b"],
            documents=[contextualize_text(t) for t in docs],
            embeddings=[[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]],
            metadatas=[md("A.pdf", 1), md("A.pdf", 2)],
        )
        assert (target / "chroma.sqlite3").exists()
        assert directory_digest(old_dir) == before
        assert directory_digest(target) != before

    @pytest.mark.parametrize("db_name,expected_count", sorted(REAL_INDEXES.items()))
    def test_chuyen_doi_header_khong_ghi_gi_len_index_that(
        self, monkeypatch, real_index_copy, db_name, expected_count
    ):
        db_path = real_index_copy(db_name)
        texts = _real_chunk_texts(db_path)  # đọc xong trước khi băm
        assert len(texts) == expected_count
        before = directory_digest(db_path)

        monkeypatch.setenv(ENABLE_CONTEXTUAL_HEADER_ENV, "1")
        converted = apply_contextual_headers(texts)
        after = directory_digest(db_path)

        assert after == before, f"{db_name} bị ghi đè!"
        assert len(converted) == len(texts)
        for original, output in zip(texts, converted):
            body = parse_chunk(original).body
            assert output.endswith(body), "thân chunk phải nguyên văn"
            header = output.split("\n", 1)[0]
            assert header.startswith("[") and "None" not in header and "[]" not in header
            labels = build_header(original)[0].labels()
            assert labels and all(label.strip() for label in labels)

    def test_index_that_du_36x_chunk_va_nhan_hop_le(self, real_index_copy):
        """Đo phân bố nhãn trên dữ liệu thật — con số dùng trong báo cáo test_T5.md."""
        stats = {}
        for db_name in REAL_INDEXES:
            db_path = real_index_copy(db_name)
            counts = {
                "article": 0,
                "preamble": 0,
                "table": 0,
                "appendix": 0,
                "whole": 0,
                "chapter": 0,
            }
            for text in _real_chunk_texts(db_path):
                header = build_header(text)[0]
                if header.article:
                    counts["article"] += 1
                for key, label in (
                    ("preamble", FALLBACK_PREAMBLE),
                    ("table", FALLBACK_TABLE),
                    ("appendix", FALLBACK_APPENDIX),
                    ("whole", FALLBACK_WHOLE),
                ):
                    if header.fallback == label:
                        counts[key] += 1
                if header.chapter:
                    counts["chapter"] += 1
            assert sum(counts[k] for k in ("article", "preamble", "table", "appendix", "whole")) == REAL_INDEXES[db_name]
            assert counts["article"] > 0
            stats[db_name] = counts
        assert sum(stats["chroma_db_vie"].values()) > 0
        # In ra để người đọc báo cáo đối chiếu; không dùng làm assertion cứng.
        print("header_stats=" + json.dumps(stats, ensure_ascii=False, sort_keys=True))


def _real_chunk_texts(db_path: Path) -> list[str]:
    client = chromadb.PersistentClient(path=str(db_path))
    names = [c.name for c in client.list_collections()]
    assert names, f"{db_path} không có collection"
    collection = client.get_collection(names[0])
    data = collection.get(include=["documents"])
    return list(data["documents"] or [])
