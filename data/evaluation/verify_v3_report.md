# Verify độc lập benchmark v3

> Ngày 2026-10-20 · Script: `tmp/verify_v3.py` (đã xóa sau phiên) · Nguồn: `data/evaluation/benchmark_100_questions_v3.json` so với v2 và `data/corpus/**`.
> **Kết luận: PASS 4/4 nhóm — v3 đủ điều kiện sang giai đoạn 2.**

## 1. Schema — PASS

- Số câu: **100/100**; ID duy nhất: **100/100**.
- Mỗi câu đúng **13 khóa** theo thứ tự: `id, category, tier, in_corpus, source_document, raw_query, normalized_query, expected_answer, expected_citations, ground_truth_answer, ground_truth_citation, supplement_if_wrong, question_type`.
- `in_corpus` là boolean: **100/100**.
- `question_type` hợp lệ: **100/100**; phân bố: `TRA_CUU`=87, `SO_SANH`=5, `THU_TUC`=5, `NGOAI_PHAM_VI`=3.
- `category` thuộc đúng 14 nhóm của v2: **100/100**.

## 2. Không phá v2 — PASS

- So khớp **100 câu × 12 khóa cũ** theo `id`: **0 lệch**.
- v2 giữ nguyên: **140,255 bytes**, SHA1 `8cc6e0118715401c6dce7fb63e48dd64148cffdc` (khớp mốc P1.2).

## 3. GT-verify nguồn — PASS

- `os.walk(data/corpus/**)` thấy **26 file**.
- **97/97** câu `in_corpus=true` có `source_document` và khớp file thật sau `fold()`.
- **3/3** câu `in_corpus=false` có `source_document` rỗng (Q96–Q98).
- Số nguồn phân biệt: **15**; số câu fail: **0**.

| source_document | File thật trong corpus | Số câu |
|---|---|---:|
| `ban-mo-ta-ctdt-nganh-cntt-2021.pdf` | `cac_file_bo_xung_khac/ban-mo-ta-ctdt-nganh-cntt-2021.pdf` | 22 |
| `367-QĐ-ĐU ngay 08-4-2026.pdf` | `Tầng 1/367-QĐ-ĐU ngay 08-4-2026.pdf` | 12 |
| `1059-qd-dhag-2020-09-29.pdf` | `Tầng 1/1059-qd-dhag-2020-09-29.pdf` | 11 |
| `888-qd-dhag-2022-08-08.pdf` | `Tầng 1/888-qd-dhag-2022-08-08.pdf` | 10 |
| `03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf` | `cac_file_bo_xung_khac/03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf` | 6 |
| `1054-qd-dhag-2020-09-28.pdf` | `Tầng 1/1054-qd-dhag-2020-09-28.pdf` | 6 |
| `118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` | `Tầng 1/118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` | 6 |
| `Qui dinh muc hoc phi nam hoc 2026-2027.pdf` | `cac_file_bo_xung_khac/Qui dinh muc hoc phi nam hoc 2026-2027.pdf` | 6 |
| `ke-hoach-ttck-kltn-dh24th-2026.pdf` | `Tầng 2/ke-hoach-ttck-kltn-dh24th-2026.pdf` | 6 |
| `ke-hoach-ttck-kltn-dh24pm-2026.pdf` | `cac_file_bo_xung_khac/ke-hoach-ttck-kltn-dh24pm-2026.pdf` | 3 |
| `163-tb-ctsv-thong-bao-ve-viec-bay-von-tin-chap-tai-ngan-hang-acb-theo-ct-acb-dong-hanh-cung-sinh-vien-dhqg-hcm.pdf` | `Tầng 2/163-tb-ctsv-thong-bao-ve-viec-bay-von-tin-chap-tai-ngan-hang-acb-theo-ct-acb-dong-hanh-cung-sinh-vien-dhqg-hcm.pdf` | 2 |
| `QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf` | `Tầng 1/QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf` | 2 |
| `TB tham gia BHYT SV NH 2026 - 2027.pdf` | `Tầng 2/TB tham gia BHYT SV NH 2026 - 2027.pdf` | 2 |
| `TB16 THAY DOI CONG RA VAO KTX.pdf` | `Tầng 2/TB16 THAY DOI CONG RA VAO KTX.pdf` | 2 |
| `don-xac-nhan-hoan-canh-kho-khan.docx` | `cac_file_bo_xung_khac/don-xac-nhan-hoan-canh-kho-khan.docx` | 1 |

## 4. Thống kê — PASS

### Phân bố `question_type`

| Nhãn | Số câu |
|---|---:|
| `TRA_CUU` | 87 |
| `SO_SANH` | 5 |
| `THU_TUC` | 5 |
| `NGOAI_PHAM_VI` | 3 |
| **Tổng** | **100** |

Nhãn trong v3 khớp bảng review: **100/100** (lệch: 0).

### Crosstab `category` × `question_type`

| Category | `TRA_CUU` | `SO_SANH` | `THU_TUC` | `NGOAI_PHAM_VI` | Tổng |
|---|---:|---:|---:|---:|---:|
| bảo hiểm y tế | 2 | 0 | 0 | 0 | 2 |
| chương trình đào tạo | 19 | 3 | 0 | 0 | 22 |
| cuộc thi chính luận | 12 | 0 | 0 | 0 | 12 |
| hành chính sinh viên | 1 | 0 | 0 | 0 | 1 |
| học phí | 10 | 1 | 1 | 0 | 12 |
| khen thưởng cấp ĐHQG | 2 | 0 | 0 | 0 | 2 |
| khen thưởng sinh viên | 10 | 0 | 0 | 0 | 10 |
| ký túc xá | 2 | 0 | 0 | 0 | 2 |
| quy chế công tác sinh viên | 6 | 0 | 0 | 0 | 6 |
| sinh viên 5 tốt | 5 | 0 | 1 | 0 | 6 |
| thực tập chuyên đề | 1 | 0 | 2 | 0 | 3 |
| thực tập tốt nghiệp | 6 | 0 | 0 | 3 | 9 |
| tài chính sinh viên | 1 | 0 | 1 | 0 | 2 |
| đánh giá rèn luyện | 10 | 1 | 0 | 0 | 11 |
| **Tổng** | **87** | **5** | **5** | **3** | **100** |

### Mẫu 5 câu mỗi loại

| Loại | ID | raw_query |
|---|---|---|
| `TRA_CUU` | Q01 | Môn học 'Thiết kế và cài đặt mạng' có mã môn học là gì, khối lượng mấy tín chỉ, học kỳ dự kiến và môn học… |
| `TRA_CUU` | Q03 | Tổng số tín chỉ của toàn chương trình đào tạo ngành CNTT là bao nhiêu và bao gồm bao nhiêu tín chỉ bắt buộc… |
| `TRA_CUU` | Q04 | Khối kiến thức đại cương (Mục I) trong chương trình đào tạo ngành CNTT có bao nhiêu tín chỉ và chiếm tỷ lệ… |
| `TRA_CUU` | Q05 | Môn 'Giới thiệu ngành – ĐH CNTT' có mã môn học là gì, mấy tín chỉ và học vào học kỳ nào? |
| `TRA_CUU` | Q06 | Để học môn 'Lập trình hướng đối tượng' (COS102), sinh viên bắt buộc phải học trước môn học nào? |
| `SO_SANH` | Q02 | Chuẩn đầu ra ELO 6, ELO 7, ELO 8 và ELO 9 của chương trình đào tạo ngành Công nghệ thông tin quy định như thế… |
| `SO_SANH` | Q09 | Chuẩn đầu ra ELO 1 và ELO 2 của chương trình đào tạo ngành Công nghệ thông tin quy định về những kiến thức… |
| `SO_SANH` | Q17 | Chuẩn đầu ra ELO 10 và ELO 11 quy định thái độ và năng lực học tập suốt đời của sinh viên như thế nào? |
| `SO_SANH` | Q23 | Tiêu chí xếp loại kết quả rèn luyện học kỳ đối với các mức Xuất sắc, Tốt, Khá, Trung bình, Yếu, Kém được tính… |
| `SO_SANH` | Q72 | Đơn giá học phí cho 1 tín chỉ thực hành so với tín chỉ lý thuyết được quy định như thế nào? |
| `THU_TUC` | Q55 | Hồ sơ cá nhân đăng ký danh hiệu 'Sinh viên 5 tốt' bao gồm những tài liệu chứng minh nào? |
| `THU_TUC` | Q63 | Hồ sơ đề nghị miễn giảm học phí đối với sinh viên khuyết tật gồm những giấy tờ gì? |
| `THU_TUC` | Q87 | Sinh viên lớp DH24PM khi thực tập chuyên đề tại doanh nghiệp phải nộp tài liệu nghiệm thu nào cho Giảng viên… |
| `THU_TUC` | Q88 | Trường hợp sinh viên tự liên hệ cơ sở thực tập ngoài danh sách liên kết của Trường cần làm thủ tục gì? |
| `THU_TUC` | Q93 | Chương trình tín dụng ưu đãi vay vốn học tập ACB yêu cầu sinh viên cung cấp các tài liệu xác thực nào? |
| `NGOAI_PHAM_VI` | Q96 | Kế hoạch tổ chức đánh giá Thực tập chuyên đề cấp Khoa do đơn vị nào phê duyệt ban hành? |
| `NGOAI_PHAM_VI` | Q97 | Sinh viên không hoàn thành đủ số giờ thực tập tại doanh nghiệp có được xem xét gia hạn không? |
| `NGOAI_PHAM_VI` | Q98 | Hình thức kỷ luật đối với sinh viên bị phát hiện đạo văn trong báo cáo Khóa luận tốt nghiệp là gì? |
| `NGOAI_PHAM_VI` | — | (chỉ có 3 câu trong v3) |

## 5. Kết luận GATE

**PASS 4/4.** Benchmark v3 đúng schema 13 khóa, giữ nguyên 12 khóa v2, toàn bộ 97 câu in-corpus khớp nguồn thật, 3 câu ngoài corpus đúng thiết kế. Đủ điều kiện chuyển sang giai đoạn 2 (classifier).

