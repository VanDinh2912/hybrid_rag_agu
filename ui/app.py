"""Giao diện đồ họa (GUI) đa tab cho hệ thống Hybrid RAG - Tra cứu Quy chế Đào tạo AGU.

Bao gồm 3 tab chức năng:
1. Tab 1: Tra cứu (Search) - Giao diện tra cứu câu hỏi sinh viên với Qwen, ChromaDB và Gemini.
2. Tab 2: Nạp dữ liệu (Ingest & Learn) - Rebuild & nạp lại corpus đa luồng với log hiển thị trực tiếp.
3. Tab 3: Vừa test vừa học (Interactive Testing & Feedback) - Kiểm tra câu hỏi, gắn nhãn Đúng/Sai,
   nhập đáp án đúng thực tế và lưu vào outputs/user_feedback.json.

Cách chạy:
    python ui/app.py
"""

import io
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# Đảm bảo đường dẫn import thư mục gốc
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Cấu hình encoding trên môi trường Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from src.vector_db import VectorStoreManager
from src.local_slm import LocalSLM
from src.generator import GeminiGenerator, is_fallback_answer, GeneratorError
from src.pipeline import HybridRAGPipeline
from ingest import run_ingestion
from learn import append_note, log_learning

# Đường dẫn lưu trữ
FEEDBACK_PATH = ROOT_DIR / "outputs" / "user_feedback.json"
NOTES_PATH = ROOT_DIR / "data" / "corpus" / "ghi_chu_hoc_them.txt"

# Hằng số giao diện
APP_TITLE = "Hệ thống Hybrid RAG - Tra cứu Quy chế Đào tạo AGU"
DEFAULT_FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"
FONT_TITLE = (DEFAULT_FONT_FAMILY, 13, "bold")
FONT_SUBTITLE = (DEFAULT_FONT_FAMILY, 9, "italic")
FONT_BOLD = (DEFAULT_FONT_FAMILY, 10, "bold")
FONT_NORMAL = (DEFAULT_FONT_FAMILY, 10)
FONT_CODE = ("Consolas" if sys.platform == "win32" else "Courier", 9)


class StdoutRedirector:
    """Chuyển hướng tạm thời stdout sang callback của Tkinter để cập nhật log thời gian thực."""

    def __init__(self, callback):
        self.callback = callback

    def write(self, string):
        if string:
            self.callback(string)

    def flush(self):
        pass


class RAGApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("960x750")
        self.minsize(800, 600)

        # Trạng thái backend
        self.db_manager: VectorStoreManager | None = None
        self.local_slm: LocalSLM | None = None
        self.generator: GeminiGenerator | None = None
        self.pipeline: HybridRAGPipeline | None = None

        self.is_searching = False
        self.is_ingesting = False
        self.is_testing = False

        self._setup_style()
        self._build_ui()

        # Khởi tạo backend ở luồng nền khi vừa bật app
        self.after(100, self._init_backend_thread)

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.bg_color = "#f8fafc"
        self.primary_color = "#1d4ed8"
        self.success_color = "#15803d"
        self.danger_color = "#b91c1c"
        self.configure(bg=self.bg_color)

        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, font=FONT_NORMAL)
        style.configure("Header.TLabel", font=FONT_TITLE, foreground="#1e3a8a", background=self.bg_color)
        style.configure("SubHeader.TLabel", font=FONT_SUBTITLE, foreground="#64748b", background=self.bg_color)
        style.configure("Bold.TLabel", font=FONT_BOLD, background=self.bg_color)

        # Style nút bấm
        style.configure(
            "Primary.TButton",
            font=FONT_BOLD,
            background=self.primary_color,
            foreground="white",
            padding=6,
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#1e40af"), ("disabled", "#94a3b8")],
            foreground=[("disabled", "#e2e8f0")],
        )

        style.configure(
            "Success.TButton",
            font=FONT_BOLD,
            background=self.success_color,
            foreground="white",
            padding=6,
        )
        style.map(
            "Success.TButton",
            background=[("active", "#166534"), ("disabled", "#94a3b8")],
            foreground=[("disabled", "#e2e8f0")],
        )

        style.configure(
            "Danger.TButton",
            font=FONT_BOLD,
            background=self.danger_color,
            foreground="white",
            padding=6,
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#991b1b"), ("disabled", "#94a3b8")],
            foreground=[("disabled", "#e2e8f0")],
        )

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header tổng
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 6))

        lbl_title = ttk.Label(
            header_frame,
            text="HỆ THỐNG HYBRID RAG — QUY CHẾ ĐÀO TẠO ĐẠI HỌC AN GIANG (AGU)",
            style="Header.TLabel",
        )
        lbl_title.pack(anchor=tk.W)

        # Trạng thái kết nối
        self.status_var = tk.StringVar(value="Đang kết nối ChromaDB, Local Qwen & Gemini...")
        self.lbl_status = ttk.Label(
            header_frame, textvariable=self.status_var, foreground="#d97706", font=FONT_BOLD
        )
        self.lbl_status.pack(anchor=tk.W, pady=(2, 0))

        # Main Notebook chia 3 tab chính
        self.main_notebook = ttk.Notebook(main_frame)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        # Tab 1: Tra cứu
        self.tab_search = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(self.tab_search, text=" 🔍 1. Tra cứu (Search) ")
        self._build_tab_search(self.tab_search)

        # Tab 2: Nạp dữ liệu / Corpus
        self.tab_ingest = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(self.tab_ingest, text=" 📥 2. Nạp dữ liệu (Ingest & Learn) ")
        self._build_tab_ingest(self.tab_ingest)

        # Tab 3: Vừa test vừa học
        self.tab_feedback = ttk.Frame(self.main_notebook, padding="10")
        self.main_notebook.add(self.tab_feedback, text=" 🧪 3. Vừa test vừa học (Feedback) ")
        self._build_tab_feedback(self.tab_feedback)

    # =========================================================================
    # TAB 1: TRA CỨU
    # =========================================================================
    def _build_tab_search(self, parent):
        # Khung nhập câu hỏi
        input_group = ttk.LabelFrame(parent, text=" Nhập câu hỏi cần tra cứu ", padding="10")
        input_group.pack(fill=tk.X, pady=(0, 10))

        input_row = ttk.Frame(input_group)
        input_row.pack(fill=tk.X)

        self.query_entry = ttk.Entry(input_row, font=(DEFAULT_FONT_FAMILY, 11))
        self.query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.query_entry.bind("<Return>", lambda event: self.on_search())
        self.query_entry.focus_set()

        ttk.Label(input_row, text="Top-K:").pack(side=tk.LEFT, padx=(4, 4))
        self.top_k_var = tk.IntVar(value=6)
        self.top_k_spin = ttk.Spinbox(input_row, from_=1, to=15, width=4, textvariable=self.top_k_var)
        self.top_k_spin.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_search = ttk.Button(
            input_row, text="Tra cứu 🔍", style="Primary.TButton", command=self.on_search
        )
        self.btn_search.pack(side=tk.RIGHT)

        # Khung hiển thị kết quả
        output_group = ttk.LabelFrame(parent, text=" Kết quả từ hệ thống RAG ", padding="10")
        output_group.pack(fill=tk.BOTH, expand=True)

        norm_row = ttk.Frame(output_group)
        norm_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(norm_row, text="Câu hỏi chuẩn hóa (Qwen):", style="Bold.TLabel").pack(side=tk.LEFT)
        self.norm_query_var = tk.StringVar(value="—")
        self.lbl_norm_query = ttk.Label(norm_row, textvariable=self.norm_query_var, foreground="#1e40af")
        self.lbl_norm_query.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

        self.sub_notebook = ttk.Notebook(output_group)
        self.sub_notebook.pack(fill=tk.BOTH, expand=True)

        # Tab con 1: Câu trả lời
        tab_answer = ttk.Frame(self.sub_notebook, padding="6")
        self.sub_notebook.add(tab_answer, text="  Câu trả lời  ")
        self.txt_answer = scrolledtext.ScrolledText(
            tab_answer, wrap=tk.WORD, font=(DEFAULT_FONT_FAMILY, 11), padx=10, pady=10, bg="#ffffff"
        )
        self.txt_answer.pack(fill=tk.BOTH, expand=True)

        # Tab con 2: Nguồn trích dẫn
        tab_sources = ttk.Frame(self.sub_notebook, padding="6")
        self.sub_notebook.add(tab_sources, text="  Nguồn trích dẫn (ChromaDB)  ")
        self.txt_sources = scrolledtext.ScrolledText(
            tab_sources, wrap=tk.WORD, font=FONT_CODE, padx=10, pady=10, bg="#f8fafc"
        )
        self.txt_sources.pack(fill=tk.BOTH, expand=True)

        # Footer Tab 1
        footer_frame = ttk.Frame(parent)
        footer_frame.pack(fill=tk.X, pady=(6, 0))

        self.search_footer_var = tk.StringVar(value="Sẵn sàng")
        ttk.Label(footer_frame, textvariable=self.search_footer_var, font=FONT_SUBTITLE).pack(side=tk.LEFT)

        btn_clear = ttk.Button(footer_frame, text="Xóa kết quả", command=self.clear_search_results)
        btn_clear.pack(side=tk.RIGHT)

    def on_search(self):
        if self.is_searching or self.is_ingesting:
            return

        query = self.query_entry.get().strip()
        if not query:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập câu hỏi cần tra cứu!")
            self.query_entry.focus_set()
            return

        if self.pipeline is None:
            messagebox.showerror("Chưa sẵn sàng", "Hệ thống AI đang khởi động, vui lòng chờ trong giây lát!")
            return

        top_k = self.top_k_var.get()
        self.is_searching = True
        self.btn_search.configure(state=tk.DISABLED)
        self.search_footer_var.set("Đang xử lý: Qwen chuẩn hóa → ChromaDB tìm kiếm → Gemini sinh câu trả lời...")
        self.norm_query_var.set("Đang chuẩn hóa...")

        self.txt_answer.delete("1.0", tk.END)
        self.txt_answer.insert(tk.END, "Đang tra cứu và sinh câu trả lời, vui lòng chờ...")
        self.txt_sources.delete("1.0", tk.END)

        threading.Thread(target=self._run_search_thread, args=(query, top_k), daemon=True).start()

    def _run_search_thread(self, query: str, top_k: int):
        t0 = time.perf_counter()
        try:
            result = self.pipeline.run(query, top_k=top_k)
            elapsed = time.perf_counter() - t0
            self.after(0, self._render_search_result, result, elapsed)
        except Exception as exc:
            self.after(0, self._render_search_error, str(exc))

    def _render_search_result(self, result: dict, elapsed: float):
        self.norm_query_var.set(result.get("normalized_query", "—"))

        answer = result.get("answer", "")
        self.txt_answer.delete("1.0", tk.END)
        self.txt_answer.insert(tk.END, answer)

        sources = result.get("sources", [])
        self.txt_sources.delete("1.0", tk.END)
        if not sources:
            self.txt_sources.insert(tk.END, "Không tìm thấy đoạn ngữ cảnh nào phù hợp trong ChromaDB.")
        else:
            for s in sources:
                header = f"[{s['rank']}] Nguồn: {s['source']} | Tầng: {s['tier']} | chunk_id: {s['chunk_id']}\n"
                preview = f"{s['preview']}\n"
                divider = "-" * 80 + "\n"
                self.txt_sources.insert(tk.END, header)
                self.txt_sources.insert(tk.END, preview)
                self.txt_sources.insert(tk.END, divider)

        engine_type = "Local Qwen (Fallback)" if is_fallback_answer(answer) else "Gemini"
        self.search_footer_var.set(
            f"Hoàn thành trong {elapsed:.2f}s | Nguồn: {engine_type} | Ngữ cảnh: {len(sources)} chunk"
        )
        self.is_searching = False
        self.btn_search.configure(state=tk.NORMAL)
        self.sub_notebook.select(0)

    def _render_search_error(self, err_msg: str):
        self.txt_answer.delete("1.0", tk.END)
        self.txt_answer.insert(tk.END, f"Đã xảy ra lỗi:\n\n{err_msg}")
        self.search_footer_var.set("Gặp sự cố khi tra cứu!")
        self.is_searching = False
        self.btn_search.configure(state=tk.NORMAL)
        messagebox.showerror("Lỗi tra cứu", err_msg)

    def clear_search_results(self):
        self.query_entry.delete(0, tk.END)
        self.norm_query_var.set("—")
        self.txt_answer.delete("1.0", tk.END)
        self.txt_sources.delete("1.0", tk.END)
        self.search_footer_var.set("Sẵn sàng")
        self.query_entry.focus_set()

    # =========================================================================
    # TAB 2: NẠP DỮ LIỆU (INGEST & LEARN)
    # =========================================================================
    def _build_tab_ingest(self, parent):
        ctrl_group = ttk.LabelFrame(parent, text=" Quản lý Corpus & Vector Database ", padding="12")
        ctrl_group.pack(fill=tk.X, pady=(0, 10))

        lbl_desc = ttk.Label(
            ctrl_group,
            text="Quét toàn bộ tài liệu trong data/corpus/ (.pdf, .docx, .txt), thực hiện OCR (nếu cần),\n"
                 "phân đoạn văn bản (chunking với overlap) và nhúng vector BAAI/bge-m3 vào ChromaDB.",
            font=FONT_NORMAL,
        )
        lbl_desc.pack(anchor=tk.W, pady=(0, 10))

        btn_row = ttk.Frame(ctrl_group)
        btn_row.pack(fill=tk.X)

        self.btn_ingest = ttk.Button(
            btn_row,
            text="🚀 Rebuild & Nạp lại Corpus (Ingest)",
            style="Success.TButton",
            command=self.on_start_ingest,
        )
        self.btn_ingest.pack(side=tk.LEFT, padx=(0, 10))

        self.reuse_model_var = tk.BooleanVar(value=True)
        chk_reuse = ttk.Checkbutton(
            btn_row,
            text="Tái sử dụng bge-m3 đã nạp (tiết kiệm RAM & khởi động nhanh)",
            variable=self.reuse_model_var,
        )
        chk_reuse.pack(side=tk.LEFT)

        # Khung log
        log_group = ttk.LabelFrame(parent, text=" Nhật ký xử lý thời gian thực (Console Log) ", padding="10")
        log_group.pack(fill=tk.BOTH, expand=True)

        self.txt_ingest_log = scrolledtext.ScrolledText(
            log_group, wrap=tk.WORD, font=FONT_CODE, bg="#0f172a", fg="#f8fafc", padx=10, pady=10
        )
        self.txt_ingest_log.pack(fill=tk.BOTH, expand=True)

        btn_clear_log = ttk.Button(parent, text="Xóa nhật ký", command=lambda: self.txt_ingest_log.delete("1.0", tk.END))
        btn_clear_log.pack(anchor=tk.E, pady=(6, 0))

    def on_start_ingest(self):
        if self.is_ingesting:
            return

        if self.is_searching or self.is_testing:
            messagebox.showwarning("Đang bận", "Vui lòng đợi quá trình tra cứu/kiểm tra hoàn tất!")
            return

        confirm = messagebox.askyesno(
            "Xác nhận Nạp lại Corpus",
            "Quá trình này sẽ đọc lại toàn bộ file trong data/corpus/, thực hiện chunking và làm mới ChromaDB.\n\n"
            "Bạn có muốn tiếp tục không?",
        )
        if not confirm:
            return

        self.is_ingesting = True
        self.btn_ingest.configure(state=tk.DISABLED)
        self.txt_ingest_log.delete("1.0", tk.END)
        self._append_ingest_log("[BẮT ĐẦU] Bắt đầu tiến trình nạp dữ liệu vào ChromaDB...\n")

        reuse = self.reuse_model_var.get()
        threading.Thread(target=self._run_ingest_thread, args=(reuse,), daemon=True).start()

    def _append_ingest_log(self, text: str):
        self.txt_ingest_log.insert(tk.END, text)
        self.txt_ingest_log.see(tk.END)

    def _run_ingest_thread(self, reuse_model: bool):
        old_stdout = sys.stdout
        redirector = StdoutRedirector(lambda s: self.after(0, self._append_ingest_log, s))
        sys.stdout = redirector

        try:
            target_manager = self.db_manager if (reuse_model and self.db_manager) else None
            # reset=False khi reuse_model để tránh lỗi lock file ChromaDB
            reset_mode = not reuse_model
            new_manager, new_vector_db, total = run_ingestion(db_manager=target_manager, reset=reset_mode)

            # Cập nhật pipeline ngay sau khi ingest thành công
            self.db_manager = new_manager
            if self.pipeline:
                self.pipeline.vector_db = new_vector_db

            msg = f"\n[HOÀN TẤT] Nạp thành công {total} chunks vào ChromaDB!\n"
            self.after(0, self._append_ingest_log, msg)
            self.after(0, self._on_ingest_completed, total)

        except Exception as exc:
            self.after(0, self._append_ingest_log, f"\n[LỖI INGEST] {exc}\n")
            self.after(0, self._on_ingest_error, str(exc))
        finally:
            sys.stdout = old_stdout

    def _on_ingest_completed(self, total: int):
        self.is_ingesting = False
        self.btn_ingest.configure(state=tk.NORMAL)
        status_msg = f"Hệ thống sẵn sàng | DB: {total} chunks"
        self.status_var.set(status_msg)
        self.lbl_status.configure(foreground="#16a34a")
        messagebox.showinfo("Thành công", f"Đã hoàn thành nạp dữ liệu! Tổng cộng: {total} chunks.")

    def _on_ingest_error(self, err_msg: str):
        self.is_ingesting = False
        self.btn_ingest.configure(state=tk.NORMAL)
        messagebox.showerror("Lỗi Ingest", f"Quá trình nạp dữ liệu gặp sự cố:\n{err_msg}")

    # =========================================================================
    # TAB 3: VỪA TEST VỪA HỌC (FEEDBACK & ACTIVE LEARNING)
    # =========================================================================
    def _build_tab_feedback(self, parent):
        # Biến lưu trữ kết quả lần test gần nhất
        self.current_test_data: dict | None = None

        # 1. Khung kiểm tra
        test_input_group = ttk.LabelFrame(parent, text=" Câu hỏi thử nghiệm (Quick Test) ", padding="10")
        test_input_group.pack(fill=tk.X, pady=(0, 10))

        row1 = ttk.Frame(test_input_group)
        row1.pack(fill=tk.X)

        self.test_entry = ttk.Entry(row1, font=(DEFAULT_FONT_FAMILY, 11))
        self.test_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.test_entry.bind("<Return>", lambda event: self.on_test_run())

        self.btn_test = ttk.Button(row1, text="Kiểm tra 🚀", style="Primary.TButton", command=self.on_test_run)
        self.btn_test.pack(side=tk.RIGHT)

        # 2. Khung kết quả kiểm tra
        test_res_group = ttk.LabelFrame(parent, text=" Kết quả phản hồi của RAG ", padding="10")
        test_res_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Nhãn câu hỏi chuẩn hóa
        norm_box = ttk.Frame(test_res_group)
        norm_box.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(norm_box, text="Chuẩn hóa:", style="Bold.TLabel").pack(side=tk.LEFT)
        self.test_norm_var = tk.StringVar(value="—")
        ttk.Label(norm_box, textvariable=self.test_norm_var, foreground="#1e40af").pack(side=tk.LEFT, padx=(6, 0))

        # Hiển thị câu trả lời
        self.txt_test_answer = scrolledtext.ScrolledText(
            test_res_group, wrap=tk.WORD, font=(DEFAULT_FONT_FAMILY, 10), height=7, bg="#ffffff"
        )
        self.txt_test_answer.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # 3. Khung Đánh giá & Phản hồi
        feedback_group = ttk.LabelFrame(parent, text=" Trọng tài đánh giá & Phản hồi cải thiện ", padding="10")
        feedback_group.pack(fill=tk.X)

        action_row = ttk.Frame(feedback_group)
        action_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(action_row, text="Đánh giá chất lượng đáp án:", style="Bold.TLabel").pack(side=tk.LEFT, padx=(0, 10))

        self.btn_correct = ttk.Button(
            action_row, text="✅ Đúng / Chính xác", style="Success.TButton", command=self.on_feedback_correct
        )
        self.btn_correct.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_wrong = ttk.Button(
            action_row, text="❌ Sai / Ảo giác", style="Danger.TButton", command=self.on_feedback_wrong
        )
        self.btn_wrong.pack(side=tk.LEFT)

        # Khung nhập thông tin đúng (khi câu trả lời bị sai)
        self.wrong_frame = ttk.Frame(feedback_group)
        # Ẩn mặc định, chỉ hiện khi ấn nút Sai

        ttk.Label(
            self.wrong_frame,
            text="Nhập đáp án đúng thực tế / Căn cứ Điều Khoản chính xác:",
            font=FONT_BOLD,
            foreground="#b91c1c",
        ).pack(anchor=tk.W, pady=(6, 2))

        self.txt_correct_info = scrolledtext.ScrolledText(
            self.wrong_frame, wrap=tk.WORD, font=(DEFAULT_FONT_FAMILY, 10), height=4, bg="#fff1f2"
        )
        self.txt_correct_info.pack(fill=tk.X, pady=(0, 6))

        opt_row = ttk.Frame(self.wrong_frame)
        opt_row.pack(fill=tk.X)

        self.learn_now_var = tk.BooleanVar(value=True)
        chk_learn = ttk.Checkbutton(
            opt_row,
            text="Đồng thời ghi vào bài học mới (ghi_chu_hoc_them.txt) để hệ thống học ngay",
            variable=self.learn_now_var,
        )
        chk_learn.pack(side=tk.LEFT)

        btn_save_feedback = ttk.Button(
            opt_row, text="Lưu phản hồi & Ghi nhận 💾", style="Primary.TButton", command=self.save_wrong_feedback
        )
        btn_save_feedback.pack(side=tk.RIGHT)

    def on_test_run(self):
        if self.is_testing or self.is_ingesting:
            return

        query = self.test_entry.get().strip()
        if not query:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập câu hỏi cần test!")
            self.test_entry.focus_set()
            return

        if self.pipeline is None:
            messagebox.showerror("Chưa sẵn sàng", "Hệ thống AI đang khởi động, vui lòng chờ trong giây lát!")
            return

        self.is_testing = True
        self.btn_test.configure(state=tk.DISABLED)
        self.test_norm_var.set("Đang chuẩn hóa...")
        self.txt_test_answer.delete("1.0", tk.END)
        self.txt_test_answer.insert(tk.END, "Hệ thống đang truy xuất và tạo câu trả lời...")
        self.wrong_frame.pack_forget()

        threading.Thread(target=self._run_test_thread, args=(query,), daemon=True).start()

    def _run_test_thread(self, query: str):
        try:
            result = self.pipeline.run(query, top_k=6)
            self.after(0, self._render_test_result, result)
        except Exception as exc:
            self.after(0, self._render_test_error, str(exc))

    def _render_test_result(self, result: dict):
        self.current_test_data = result
        self.test_norm_var.set(result.get("normalized_query", "—"))
        self.txt_test_answer.delete("1.0", tk.END)
        self.txt_test_answer.insert(tk.END, result.get("answer", ""))
        self.is_testing = False
        self.btn_test.configure(state=tk.NORMAL)

    def _render_test_error(self, err_msg: str):
        self.current_test_data = None
        self.txt_test_answer.delete("1.0", tk.END)
        self.txt_test_answer.insert(tk.END, f"Lỗi: {err_msg}")
        self.is_testing = False
        self.btn_test.configure(state=tk.NORMAL)
        messagebox.showerror("Lỗi test", err_msg)

    def on_feedback_correct(self):
        if not self.current_test_data:
            messagebox.showwarning("Chưa có dữ liệu", "Vui lòng chạy kiểm tra một câu hỏi trước khi đánh giá!")
            return

        self._save_feedback_record(feedback_type="correct", correct_answer=None)
        self.wrong_frame.pack_forget()
        messagebox.showinfo("Đã ghi nhận", "Cảm ơn bạn! Đã ghi nhận câu trả lời ĐÚNG vào outputs/user_feedback.json.")

    def on_feedback_wrong(self):
        if not self.current_test_data:
            messagebox.showwarning("Chưa có dữ liệu", "Vui lòng chạy kiểm tra một câu hỏi trước khi đánh giá!")
            return

        # Hiển thị khung nhập thông tin đúng
        self.wrong_frame.pack(fill=tk.X, pady=(6, 0))
        self.txt_correct_info.delete("1.0", tk.END)
        self.txt_correct_info.focus_set()

    def save_wrong_feedback(self):
        if not self.current_test_data:
            return

        correct_info = self.txt_correct_info.get("1.0", tk.END).strip()
        if not correct_info:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đáp án đúng thực tế trước khi lưu!")
            return

        # 1. Lưu vào outputs/user_feedback.json
        self._save_feedback_record(feedback_type="wrong", correct_answer=correct_info)

        # 2. Nếu người dùng chọn học ngay qua ghi_chu_hoc_them.txt
        learn_now = self.learn_now_var.get()
        if learn_now:
            raw_query = self.current_test_data["raw_query"]
            wrong_ans = self.current_test_data["answer"]
            chunks_before = self.pipeline.vector_db._collection.count()

            append_note(raw_query, correct_info)

            # Rebuild nhẹ nhàng không reset thư mục
            try:
                _db, new_vector_db, _total = run_ingestion(db_manager=self.db_manager, reset=False)
                self.pipeline.vector_db = new_vector_db
                chunks_after = new_vector_db._collection.count()
                log_learning(raw_query, wrong_ans, correct_info, chunks_before, chunks_after)
                self.status_var.set(f"Đã học bài mới! Chunks: {chunks_before} → {chunks_after}")
            except Exception as e:
                print(f"[Learn Error] Không thể tự động rebuild: {e}")

        self.wrong_frame.pack_forget()
        msg = "Đã lưu phản hồi vào outputs/user_feedback.json!"
        if learn_now:
            msg += "\nHệ thống cũng đã cập nhật bài học vào corpus và nạp lại ChromaDB thành công!"
        messagebox.showinfo("Thành công", msg)

    def _save_feedback_record(self, feedback_type: str, correct_answer: str | None):
        """Ghi nhận log đánh giá của người dùng vào outputs/user_feedback.json."""
        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "feedback": feedback_type,
            "raw_query": self.current_test_data.get("raw_query"),
            "normalized_query": self.current_test_data.get("normalized_query"),
            "system_answer": self.current_test_data.get("answer"),
            "correct_answer": correct_answer,
            "sources": [
                {"rank": s["rank"], "source": s["source"], "tier": s["tier"], "chunk_id": s["chunk_id"]}
                for s in self.current_test_data.get("sources", [])
            ],
        }

        records = []
        if FEEDBACK_PATH.exists():
            try:
                records = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
                if not isinstance(records, list):
                    records = []
            except Exception:
                records = []

        records.append(record)
        FEEDBACK_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # =========================================================================
    # KHỞI TẠO BACKEND (CHẠY NGẦM)
    # =========================================================================
    def _init_backend_thread(self):
        threading.Thread(target=self._init_backend_task, daemon=True).start()

    def _init_backend_task(self):
        try:
            self.status_var.set("Đang kết nối ChromaDB...")
            self.db_manager = VectorStoreManager()
            vector_db = self.db_manager.load_vector_store()

            self.status_var.set("Kiểm tra Local SLM (Ollama)...")
            self.local_slm = LocalSLM()
            slm_ok, _msg = self.local_slm.check_connection()

            self.status_var.set("Kết nối Gemini API...")
            self.generator = GeminiGenerator()

            self.pipeline = HybridRAGPipeline(
                vector_db=vector_db, local_slm=self.local_slm, generator=self.generator
            )

            status_msg = f"Hệ thống sẵn sàng | DB: {vector_db._collection.count()} chunks"
            if not slm_ok:
                status_msg += " | Cảnh báo: Ollama tắt (dùng query gốc)"
            self.status_var.set(status_msg)
            self.lbl_status.configure(foreground="#16a34a")

        except Exception as exc:
            self.status_var.set(f"Khởi tạo thất bại: {exc}")
            self.lbl_status.configure(foreground="#dc2626")
            messagebox.showerror("Lỗi khởi tạo Backend", f"Không thể khởi động hệ thống RAG:\n{exc}")


if __name__ == "__main__":
    app = RAGApplication()
    app.mainloop()
