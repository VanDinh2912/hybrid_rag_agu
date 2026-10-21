# So sánh A/B — bật/tắt tầng phân loại (P4.3)

Nguồn: `outputs\ab_results_without_classifier.json` (2026-10-21T18:39:57) và `outputs\ab_results_with_classifier.json` (2026-10-21T18:40:12); benchmark 100 câu v3.
Tham số chung: top_k=6 · retrieve_k=6 · generator local-qwen (qwen2.5:1.5b-instruct) · judge TẮT · 2026-10-21. Mọi con số truy được về 2 JSON nguồn (tổng thể đọc thẳng khối `aggregates` — trừ Faithfulness tính mean per-entry vì judge tắt khiến aggregates n=0; theo nhóm tính từ `per_question`).

> **Lưu ý kịch bản**: judge Gemini TẮT — cột Faithfulness là **heuristic_local** (chấm per-entry, cùng công thức 2 nhánh). Không so sánh trực tiếp với baseline Gemini cũ; A/B nội bộ vẫn công bằng.

## 1. Bảng tổng thể

| Chỉ số | WITHOUT (tắt phân loại) | WITH (bật phân loại) | Chênh lệch | Ghi chú |
|---|---|---|---|---|
| Hit@3 | 60.8% | 77.3% | +16.50 pp |  |
| Hit@5 | 65.0% | 78.3% | +13.40 pp |  |
| Hit@6 | 66.0% | 78.3% | +12.37 pp |  |
| Citation Precision | 15.6% | 24.8% | +9.22 pp |  |
| Citation Recall | 13.0% | 29.7% | +16.67 pp |  |
| Citation F1 | 13.4% | 25.7% | +12.34 pp |  |
| Citation Exact Match | 12.5% | 21.9% | +9.38 pp |  |
| Number support | 96.6% | 93.6% | -3.05 pp |  |
| Bảo toàn thực thể (chuẩn hóa) | 96.7% | 96.7% | +0.00 pp |  |
| MRR (recall window) | 0.5097 | 0.7689 | +0.26 |  |
| Faithfulness heuristic_local | 0.643 (n=53) | 0.647 (n=50) | +0.004 | chỉ câu trả lời — gộp cả từ chối (score 1.0): 0.811 / 0.823 |
| Latency trung bình (s) | 2.30 | 7.79 | +5.49 | CHỈ THAM CHIẾU (xem mục 6) |
| Topic accuracy | n/a (không classifier) | 87.0% | — |  |
| Type accuracy | n/a (không classifier) | 83.0% | — | khớp P2.3 gate (topic ~85%, type ~81%) |
| Từ chối oan (in_corpus) | 46/97 (47.4%) | 49/97 (50.5%) | +3 câu | in_corpus bị trả lời từ chối |
| Từ chối đúng (ngoài corpus) | 33.3% | 33.3% | — | trên 3 câu ngoài corpus |
| Ảo giác ngoài corpus | 2 | 2 | — | câu ngoài corpus bị trả lời thay vì từ chối |

**Kiểm tra GATE** (MRR/Hit không giảm > 5% tương đối):

| Chỉ số | WITHOUT | WITH | Thay đổi tương đối | GATE (ngưỡng −5%) |
|---|---|---|---|---|
| Hit@3 | 60.8% | 77.3% | +27.1% | ĐẠT |
| Hit@5 | 65.0% | 78.3% | +20.6% | ĐẠT |
| Hit@6 | 66.0% | 78.3% | +18.7% | ĐẠT |
| MRR | 0.5097 | 0.7689 | +50.9% | ĐẠT |

## 2. Theo loại câu hỏi (expected từ benchmark)

| Loại câu hỏi | n | Hit@3 (W/O) | Hit@3 (W) | ΔHit@3 | Hit@5 (W/O) | Hit@5 (W) | MRR (W/O) | MRR (W) | CitF1 (W/O) | CitF1 (W) | Faith. trả lời (W/O) | Faith. trả lời (W) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TRA_CUU | 87 | 58.6% | 77.0% | +18.39 | 62.1% | 77.0% | 0.5008 | 0.7671 | 10.6% | 23.3% | 0.642 | 0.645 |
| SO_SANH ⚠️ n nhỏ | 5 | 80.0% | 80.0% | +0.00 | 80.0% | 80.0% | 0.4333 | 0.8286 | 100.0% | 100.0% | 0.916 | 0.959 |
| THU_TUC ⚠️ n nhỏ | 5 | 80.0% | 80.0% | +0.00 | 100.0% | 100.0% | 0.7400 | 0.7400 | n/a | n/a | 0.516 | 0.453 |
| NGOAI_PHAM_VI ⚠️ n nhỏ | 3 | n/a | n/a | n/a | n/a | n/a | 0.0000 | 0.0000 | n/a | n/a | 0.438 | 0.500 |

> ⚠️ Nhóm n < 10 (SO_SANH, THU_TUC, NGOAI_PHAM_VI): sai số cao, chỉ đọc xu hướng, không kết luận mạnh.

## 3. Theo chủ đề (category benchmark)

| Chủ đề | n | Hit@3 (W/O) | Hit@3 (W) | ΔHit@3 | Hit@5 (W/O) | Hit@5 (W) | MRR (W/O) | MRR (W) | CitF1 (W/O) | CitF1 (W) | Faith. trả lời (W/O) | Faith. trả lời (W) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bảo hiểm y tế ⚠️ n nhỏ | 2 | 100.0% | 100.0% | +0.00 | 100.0% | 100.0% | 0.7500 | 0.7500 | n/a | n/a | 0.872 | 0.872 |
| chương trình đào tạo | 22 | 45.5% | 90.9% | +45.45 | 45.5% | 90.9% | 0.2255 | 0.9091 | n/a | n/a | 0.827 | 0.906 |
| cuộc thi chính luận | 12 | 91.7% | 100.0% | +8.33 | 91.7% | 100.0% | 0.7708 | 1.0000 | n/a | n/a | 0.558 | 0.425 |
| hành chính sinh viên ⚠️ n nhỏ | 1 | 0.0% | 0.0% | +0.00 | 100.0% | 0.0% | 0.2000 | 0.0833 | n/a | n/a | 1.000 | n/a |
| học phí | 12 | 50.0% | 50.0% | +0.00 | 50.0% | 50.0% | 0.4444 | 0.5595 | n/a | n/a | 0.885 | 0.570 |
| khen thưởng cấp ĐHQG ⚠️ n nhỏ | 2 | 50.0% | 50.0% | +0.00 | 50.0% | 50.0% | 0.2917 | 0.2917 | 0.0% | 0.0% | 0.667 | 0.667 |
| khen thưởng sinh viên | 10 | 10.0% | 50.0% | +40.00 | 10.0% | 50.0% | 0.1417 | 0.5000 | 10.0% | 30.0% | 0.582 | 0.547 |
| ký túc xá ⚠️ n nhỏ | 2 | 0.0% | 0.0% | +0.00 | 0.0% | 0.0% | 0.0000 | 0.0000 | 0.0% | 0.0% | 0.350 | 0.350 |
| quy chế công tác sinh viên ⚠️ n nhỏ | 6 | 66.7% | 100.0% | +33.33 | 83.3% | 100.0% | 0.7269 | 1.0000 | 40.0% | 46.7% | 0.427 | 0.408 |
| sinh viên 5 tốt ⚠️ n nhỏ | 6 | 83.3% | 83.3% | +0.00 | 83.3% | 83.3% | 0.7500 | 0.8333 | 0.0% | 0.0% | 0.636 | 0.644 |
| thực tập chuyên đề ⚠️ n nhỏ | 3 | 66.7% | 33.3% | -33.33 | 100.0% | 66.7% | 0.5667 | 0.2333 | n/a | n/a | 0.558 | 0.556 |
| thực tập tốt nghiệp ⚠️ n nhỏ | 9 | 66.7% | 100.0% | +33.33 | 83.3% | 100.0% | 0.2926 | 0.6667 | n/a | n/a | 0.463 | 0.500 |
| tài chính sinh viên ⚠️ n nhỏ | 2 | 100.0% | 100.0% | +0.00 | 100.0% | 100.0% | 1.0000 | 1.0000 | n/a | n/a | 0.433 | 0.425 |
| đánh giá rèn luyện | 11 | 100.0% | 81.8% | -18.18 | 100.0% | 81.8% | 1.0000 | 0.8182 | 11.7% | 26.4% | 0.413 | 0.405 |

> ⚠️ Nhóm n < 10 (bảo hiểm y tế, hành chính sinh viên, khen thưởng cấp ĐHQG, ký túc xá, quy chế công tác sinh viên, sinh viên 5 tốt, thực tập chuyên đề, thực tập tốt nghiệp, tài chính sinh viên): sai số cao, chỉ đọc xu hướng, không kết luận mạnh.

## 4. Router lượt WITH — phân bố predicted question_type

| Predicted | n | Hit@3 | Hit@5 | MRR | CitF1 | Faith. trả lời |
|---|---|---|---|---|---|---|
| TRA_CUU | 70 | 75.7% | 75.7% | 0.7534 | 15.2% | 0.637 |
| SO_SANH | 14 | 92.9% | 92.9% | 0.9388 | 31.7% | 0.784 |
| THU_TUC | 5 | 80.0% | 100.0% | 0.7400 | n/a | 0.453 |
| NGOAI_PHAM_VI | 11 | 62.5% | 62.5% | 0.4545 | 75.0% | 0.485 |

Phân bố predicted: {'TRA_CUU': 70, 'SO_SANH': 14, 'NGOAI_PHAM_VI': 11, 'THU_TUC': 5} (expected: TRA_CUU 87, SO_SANH 5, THU_TUC 5, NGOAI_PHAM_VI 3).

## 5. Từ chối oan — phân tích nguyên nhân

- WITHOUT: **46/97** câu in_corpus bị từ chối oan — lượt này KHÔNG có classifier, nên phần lớn nguyên nhân nền là guardrail overlap + khuynh hướng từ chối của generator local (không phải lỗi phân loại).
- WITH: **49/97** câu từ chối oan, theo predicted type: {'NGOAI_PHAM_VI': 7, 'SO_SANH': 4, 'TRA_CUU': 36, 'THU_TUC': 2}.
- Trong số đó, 7 câu bị classifier gán nhầm **NGOAI_PHAM_VI** (prompt từ chối khớp → từ chối oan): Q08, Q12, Q36, Q46, Q48, Q60, Q86.
- Đối chiếu danh sách 19 câu bị gán nhầm trong `logs/classifier/results.json` (10 TRA_CUU→SO_SANH, 9 TRA_CUU→NGOAI_PHAM_VI): 9/19 câu bị từ chối oan ở lượt WITH (Q08, Q12, Q15, Q26, Q36, Q46, Q48, Q60, Q86). Kết luận: misroute góp phần nhưng KHÔNG phải nguyên nhân chính — chênh lệch từ chối oan 2 lượt chỉ +3 câu, cả 2 lượt đều ~50% do tầng generator/guardrail.
- Ví dụ từ chối oan WITHOUT (không classifier): Q01, Q06, Q07, Q13, Q15 — xác nhận nguyên nhân nền.

## 6. Nhận xét tăng/giảm & dẫn chứng cụ thể

- **Tăng mạnh nhất theo chủ đề** (ΔHit@3): chương trình đào tạo (n=22) Hit@3 +45.5 pp; khen thưởng sinh viên (n=10) Hit@3 +40.0 pp.
- **Giảm theo chủ đề** (ΔHit@3): thực tập chuyên đề (n=3) Hit@3 -33.3 pp ⚠️; đánh giá rèn luyện (n=11) Hit@3 -18.2 pp (⚠️ = n nhỏ, chỉ đọc xu hướng).
- Theo loại câu hỏi: TRA_CUU (n=87) là nhóm tăng chính (Hit@3 58.6% → 77.0%); NGOAI_PHAM_VI (n=3) MRR 0.0000 ở cả 2 lượt — ngoài corpus không có tài liệu đúng để khớp, hành vi như kỳ vọng.
- **Q02** (SO_SANH, tăng MRR rõ nhất nhóm SO_SANH): WITHOUT matched_rank=3 (RR 0.33) → WITH rank=1 (RR 1.00). Câu: “Chuẩn đầu ra ELO 6, ELO 7, ELO 8 và ELO 9 của chương trình đào tạo ngành Công nghệ thông tin quy định như thế nào?…”
- **Q08**: in_corpus nhưng bị classifier gán NGOAI_PHAM_VI → từ chối oan ở lượt WITH (expected type: TRA_CUU).
- Q96/Q98 (ngoài corpus): cả 2 lượt đều trả lời thay vì từ chối (ảo giác); chỉ Q97 từ chối đúng.

## 7. Latency — chỉ tham chiếu

WITHOUT 2.30s/câu vs WITH 7.79s/câu. Hai lượt có pattern cache khác nhau (WITH miss nhiều ở nhóm SO_SANH do router đổi ngữ cảnh truy vấn) và chạy song song trên cùng máy — latency KHÔNG dùng để rút kết luận chất lượng.

## 8. Kết luận GATE P4.3

- Hit@3: +27.1% tương đối → ĐẠT (ngưỡng −5%).
- Hit@5: +20.6% tương đối → ĐẠT (ngưỡng −5%).
- Hit@6: +18.7% tương đối → ĐẠT (ngưỡng −5%).
- MRR: +50.9% tương đối → ĐẠT (ngưỡng −5%).
- Nhóm tăng rõ: SO_SANH (expected, n=5) MRR 0.4333 → 0.8286 (+0.3953); nhóm TRA_CUU (n=87) Hit@3 58.6% → 77.0%.
- **GATE tổng thể: ĐẠT**
