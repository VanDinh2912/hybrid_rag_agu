# Báo cáo kiểm thử — Test Engineer, T0 (noise floor + bộ đếm `[AnswerRescue]`)

Ngày: 2026-10-24 · Nhánh `auto/overnight` · Đối tượng: `tools/loop/noise_floor.py`
· Test mới: `tests/test_noise_floor.py` · Harness: `tmp/mutation_check_t0.py`

> **Cập nhật 25-10 11:51 — làm chặt đúng chữ "CI luôn chứa ước lượng điểm":** thêm test
> `test_ci_chua_uoc_luong_diem_giai_tich_khong_chi_trung_binh_bootstrap`. Test cũ so CI với
> **trung bình các lượt bootstrap** (dễ đúng theo vòng tròn); test mới so với **hiệu tỉ lệ tính từ
> dữ liệu** (0,55 − 0,40 = 0,15) và kiểm `rate_ci` từng round chứa tỉ lệ thô (0,40 / 0,55).
> Kết quả: `tests/test_noise_floor.py` **22 passed**; toàn repo **1.006 passed**
> (`tmp/pytest_t0_final.txt`); mutation vẫn **5/5 bắt** (`tmp/mutation_check_t0.log`). Các số
> **21 test / 712 passed** ở §2 và §6 là **mốc lịch sử của phiên 24-10**, giữ nguyên.

## 1. Đã làm gì

1. Đọc `data/loop/README.md` (7 bất biến), quy tắc P-00, và `noise_floor.py` + `docs/reports/T0.md`.
2. Thăm dò hành vi thật của các hàm trước khi viết kỳ vọng (McNemar với `n=0`/đối xứng/`b=20,c=2`;
   `paired_bootstrap`/`rate_ci` với mẫu rỗng và `n=1`) — xác nhận **không có lỗi chức năng**:
   `mcnemar_exact(0,0)` trả p=1,0; `paired_bootstrap([],…)` trả `mean/CI=None`; `rate_ci([],…)` trả `{}`
   (không crash nhờ `for _ in range(0)` không sinh chỉ số). Không phải viết test "trước khi sửa lỗi" vì không phát hiện lỗi.
3. Thêm các hàm **thuần, import được** vào `noise_floor.py` (trước đây phép đếm rescue + đổi verdict làm tay,
   hardcode trong `main()`): `count_answer_rescue`, `rescue_decision`, `verdict_flips`,
   `count_verdict_flips`, `family_flip_stats`; đồng thời **rút gọn `main()`** để gọi đúng các helper này
   (bỏ logic trùng) và thêm cờ `mẫu_quá_nhỏ` vào đầu ra thật.
4. Thêm **cảnh báo tường minh (không crash, không số vô nghĩa)** cho trường hợp suy biến `n=0`/`n=1`
   (paired_bootstrap, rate_ci) và cho **dòng log `[AnswerRescue]` hỏng/dở dang** (`count_answer_rescue`).
5. Viết `tests/test_noise_floor.py` — **21 test**, dữ liệu giả nhỏ, deterministic, không gọi mạng/model.
6. Chạy **mutation check**: 5 lỗi cố ý (đúng 2 lỗi bắt buộc `<`→`<=` và tổng→trung bình), xác nhận
   ≥1 test đỏ mỗi lỗi, hoàn nguyên **byte-identical** (patch ở cấp bytes nên không lệch dòng kết thúc).

## 2. Số test

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| Test thêm mới (`test_noise_floor.py`) | **21 passed** | `venv/… -m pytest tests/test_noise_floor.py -q` |
| Đỏ sau cùng | **0** | — |
| Tổng bộ `tests/` (venv): 691 → **712** | 712 passed | `venv/… -m pytest tests -q` |
| Chữ ký trọng tài (trước = sau) | `9f1179ccab74` (không đổi) | `verify.referee_fingerprint()` |

`noise_floor.py` **không** thuộc `REFEREE_FILES` → sửa nó **không** đổi chữ ký (đã kiểm lại = `9f1179ccab74`).
`tools/loop/gate.py`, các round đã đóng `r5`/`r5b`, và `outputs/` **không bị chạm** (git status: vẫn `??`/nguyên vẹn).

## 3. Phủ 6 ca yêu cầu

- **#1 McNemar**: (a) vector giống hệt → 0 bất đồng, p=1, CI ghép cặp chứa 0; (b) `b==c` (k=1,2,5,10) → p ≥ 0,5;
  (c) `b=20,c=2` → p nhỏ, đối chiếu **tính tay** nhị thức hai phía, `|script − hand| < 1e-6`.
- **#2 Bootstrap CI**: cùng seed → kết quả **y hệt** (`a == b`); đổi seed → `mean_diff` lệch < 0,05; CI luôn chứa
  ước lượng điểm (`lo ≤ mean ≤ hi`); `n=0` → **cảnh báo + `None`/`{}`** (không crash, không số vô nghĩa);
  `n=1` → cảnh báo + CI suy biến xác định (`[-1,−1]`, `[1,1]`).
- **#3 `[AnswerRescue]`**: log giả 5 dòng thử / 2 cứu → `(5,2)`; log rỗng → `(0,0)` và **không chia 0**; dòng
  `[AnswerRescue]` dở dang (cụt "Cứu một câu…") → **không đếm, có cảnh báo**; bẫy chuỗi "cứu": dòng "…không
  đạt ngưỡng" chứa "cứu" nhưng không bị tính là cứu; log nhiều round trộn (`[round=r5b]`/`[round=r9]`) →
  lọc `round_tag` đếm **đúng round** (2/1 và 3/3), `None` đếm hết (5/4).
- **#4 quy tắc <5%**: `1/64`, `1/21` (< 0,05) → "bỏ lever"; **đúng 0,05** (`1/20`) → "giữ xem xét" (nghiêm ngặt `<`);
  trên ngưỡng → "giữ xem xét".
- **#5 family**: `n=9` → cờ `mẫu_quá_nhỏ=True`; `n=10` → `False`; `n=1` → `True`; đếm flip theo family đúng.
- **#6 hồi quy**: trên `r5`↔`r5b` thật (đọc từ đĩa, `skip` nếu thiếu), `count_verdict_flips` (`sum`) ==
  vòng-for độc lập == `len(verdict_flips(...))`; thực đo = **5/100** (khớp T0).

## 4. Bảng mutation check (lỗi cố ý → test nào bắt)

| # | Lỗi cố ý | Vị trí | Kết quả | Test bắt |
|---|---|---|---|---|
| M-T0-1 | `ratio < threshold` → `<=` | `rescue_decision` | 1 failed | `test_dung_nguong_giu_xem_xet` |
| M-T0-2 | **tổng → trung bình** (`sum(...)` → `sum(...)/len`) | `count_verdict_flips` | 1 failed | `test_tong_verdict_doi_khop_script_doc_lap` |
| M-T0-3 | `n < 10` → `n <= 10` (cờ mẫu quá nhỏ) | `family_flip_stats` | 1 failed | `test_family_du_nguong_khong_bi_co` |
| M-T0-4 | McNemar hai phía → một phía (bỏ nhân tử 2) | `mcnemar_exact` | 1 failed | `test_b20c2_p_nho_khop_tinh_tay_duoi_1e_minus_6` |
| M-T0-5 | SUCCESS marker → substring `"cứu"` (đếm nhầm) | `count_answer_rescue` | 2 failed | `test_5_dong_thu_2_cuu_duoc_tra_5_2` (+ `test_ba_loi_chu_cuu_khong_phai_cuu_duoc`) |

5/5 **BẮT ĐƯỢC**, mỗi vòng hoàn nguyên **byte-identical** (`sha` khớp, `# MUT` không còn, LF thuần).
Hai mutation bắt buộc của đề bài (`<`→`<=`, tổng→trung bình) nằm ở M-T0-1 và M-T0-2 — đều bị bắt.

## 5. Phần KHÔNG kiểm thử + lý do

- **Đường sinh `[AnswerRescue]` thật** (`src/generator.py` `_maybe_rescue_refusal`): không test ở đây vì cần
  Ollama/Gemini thật (nguyên tắc #2). Unit test chỉ kiểm **bộ đếm** trên log giả; marker chuỗi khớp đúng văn bản
  in ra ở `generator.py:1140-1173`. Test tích hợp end-to-end thuộc pha round (`run_round`), không phải unit.
- **`rate_ci`/`paired_bootstrap` khi mọi mẫu số = 0**: được phủ (`n=1 zero-den` → `{}`), nhưng chưa kiểm
  phân phối CI của tỉ số trên mẫu mất cân bằng cực đoan (mẫu giả nhỏ đã đủ cho hợp đồng hàm).
- **Hồi quy r5↔r5b** chạy đọc-disk nên phụ thuộc dữ liệu round còn trên repo; test **tự `skip`** khi thiếu
  ⇒ không làm đỏ trên môi trường không có `data/loop/rounds/`.

## 6. Lệnh tái lập

```bash
cd D:/DoAn/hybrid_rag_agu
venv/Scripts/python.exe -m pytest tests/test_noise_floor.py -q      # 21 passed
venv/Scripts/python.exe -m pytest tests -q                          # 712 passed
venv/Scripts/python.exe -c "import sys;sys.path[:0]=['tools/loop','.'];from verify import referee_fingerprint;print(referee_fingerprint())"  # 9f1179ccab74
venv/Scripts/python.exe tmp/mutation_check_t0.py                    # 5/5 BẮT ĐƯỢC, tự hoàn nguyên
```

## 7. Đề xuất / việc cần duyệt

- **DE-T0-1 (đã làm, không cần duyệt):** `main()` giờ gọi helper đã test, loại bỏ trùng lặp; đầu ra thêm
  `by_family[*].mẫu_quá_nhỏ`. Không chạy lại `noise_floor.py` để **không ghi đè** `data/loop/noise_floor.json`
  (artifact T0 đã đóng) — chỉ sửa mã nguồn; file JSON cũ giữ nguyên. Nếu muốn cập nhật JSON kèm cờ mới: cần duyệt.
- **DE-T0-2 (nên):** đổi convention gán round cho log rescue thành `[round=<tag>]` ngay tại `generator.py`
  để bộ đếm lọc round không phải suy đoán; hiện test dùng log giả theo convention này.
- **DE-T0-3 (duyệt):** cân nhắc nâng `count_answer_rescue` đọc thẳng `rescue_tally.txt`/stdout gốc của các round
  để thay các con số hardcode trong `main()` (`lines_answer_rescue_total: 60`…) bằng số tính lại tự động.
