# Bộ 50 câu hỏi benchmark — Hybrid RAG AGU

> Sinh từ toàn bộ 27 tài liệu trong `data/corpus` (Tầng 1, Tầng 2, cac_file_bo_xung_khac).
> Mỗi câu gồm **câu hỏi**, **đáp án chuẩn** và **dòng bổ sung đáp án đúng nếu kết quả sai** (`supplement_if_wrong`).
> Bản máy đọc: `benchmark_50_questions.json` (tương thích `src/assessment/evaluation.py`).

## Tầng 1

### Q01 · quy chế công tác sinh viên
**Câu hỏi:** Cố vấn học tập của Khoa được tổ chức họp định kỳ ít nhất bao nhiêu lần mỗi học kỳ?
**Tài liệu nguồn:** `1054-qd-dhag-2020-09-28.pdf` — Quyết định số 1504/QĐ-ĐHAG (Quy chế CTSV) - Điều 6, Khoản 2
**Đáp án chuẩn:** Ít nhất 1 lần/học kỳ. Theo Quy chế Công tác sinh viên (QĐ 1504/QĐ-ĐHAG), Khoa phân công cố vấn học tập cho các lớp sinh viên và định kỳ tổ chức họp cố vấn học tập của Khoa ít nhất 1 lần/học kỳ để nắm bắt tình hình sinh viên trong Khoa.
**Dòng bổ sung nếu sai:** Đáp án đúng: Ít nhất 1 lần/học kỳ. (Nguồn: QĐ 1504/QĐ-ĐHAG - Điều 6, Khoản 2)

### Q02 · quy chế công tác sinh viên
**Câu hỏi:** Lớp sinh viên ở Trường ĐH An Giang được tổ chức theo những hình thức nào và nhiệm kỳ Ban Cán sự lớp chuyên ngành tính như thế nào?
**Tài liệu nguồn:** `1054-qd-dhag-2020-09-28.pdf` — Quyết định số 1504/QĐ-ĐHAG (Quy chế CTSV) - Điều 7
**Đáp án chuẩn:** Lớp sinh viên được tổ chức theo 02 hình thức: Lớp chuyên ngành và Lớp học phần. Nhiệm kỳ Ban Cán sự lớp chuyên ngành được tính theo năm học, dựa trên quyết định bổ nhiệm của Phòng Công tác Sinh viên.
**Dòng bổ sung nếu sai:** Đáp án đúng: 2 hình thức (Lớp chuyên ngành và Lớp học phần); nhiệm kỳ Ban Cán sự lớp chuyên ngành tính theo năm học. (Nguồn: QĐ 1504/QĐ-ĐHAG - Điều 7)

### Q03 · quy chế công tác sinh viên
**Câu hỏi:** Sinh viên có hoàn cảnh khó khăn được hỗ trợ gì về vay vốn và đóng học phí theo Quy chế công tác sinh viên?
**Tài liệu nguồn:** `1054-qd-dhag-2020-09-28.pdf` — Quyết định số 1504/QĐ-ĐHAG (Quy chế CTSV) - Điều 8, Khoản 5
**Đáp án chuẩn:** Sinh viên được tạo điều kiện để vay vốn ngân hàng chính sách địa phương; được gia hạn thời gian đóng học phí đối với trường hợp sinh viên có hoàn cảnh khó khăn được địa phương xác nhận.
**Dòng bổ sung nếu sai:** Đáp án đúng: Được tạo điều kiện vay vốn ngân hàng chính sách địa phương và được gia hạn thời gian đóng học phí nếu hoàn cảnh khó khăn được địa phương xác nhận. (Nguồn: QĐ 1504/QĐ-ĐHAG - Điều 8, Khoản 5)

### Q04 · khen thưởng sinh viên
**Câu hỏi:** Danh hiệu thi đua cá nhân sinh viên gồm mấy loại? Điều kiện đạt danh hiệu Sinh viên Khá và Sinh viên Giỏi là gì?
**Tài liệu nguồn:** `1054-qd-dhag-2020-09-28.pdf` — Quyết định số 1504/QĐ-ĐHAG (Quy chế CTSV) - Điều 14, Khoản 2a
**Đáp án chuẩn:** Danh hiệu thi đua cá nhân sinh viên gồm 3 loại: Khá, Giỏi, Xuất sắc. Đạt danh hiệu Sinh viên Khá: xếp loại học tập và rèn luyện từ Khá trở lên. Đạt danh hiệu Sinh viên Giỏi: xếp loại học tập từ Giỏi trở lên và xếp loại rèn luyện từ Tốt trở lên.
**Dòng bổ sung nếu sai:** Đáp án đúng: 3 loại (Khá, Giỏi, Xuất sắc); SV Khá cần học tập và rèn luyện từ Khá trở lên, SV Giỏi cần học tập từ Giỏi trở lên và rèn luyện từ Tốt trở lên. (Nguồn: QĐ 1504/QĐ-ĐHAG - Điều 14, Khoản 2a)

### Q05 · khen thưởng sinh viên
**Câu hỏi:** Lớp sinh viên muốn đạt danh hiệu Lớp sinh viên Xuất sắc cần thêm điều kiện gì ngoài các tiêu chuẩn của Lớp sinh viên Tiên tiến?
**Tài liệu nguồn:** `1054-qd-dhag-2020-09-28.pdf` — Quyết định số 1504/QĐ-ĐHAG (Quy chế CTSV) - Điều 14, Khoản 2b
**Đáp án chuẩn:** Lớp sinh viên Xuất sắc phải đạt các tiêu chuẩn của danh hiệu Lớp sinh viên Tiên tiến, đồng thời có từ 10% sinh viên đạt danh hiệu Sinh viên Giỏi trở lên, trong đó có cá nhân đạt danh hiệu Sinh viên Xuất sắc.
**Dòng bổ sung nếu sai:** Đáp án đúng: Cần có từ 10% sinh viên đạt danh hiệu SV Giỏi trở lên, trong đó có cá nhân đạt danh hiệu SV Xuất sắc. (Nguồn: QĐ 1504/QĐ-ĐHAG - Điều 14, Khoản 2b)

### Q06 · kỷ luật sinh viên
**Câu hỏi:** Sau bao lâu thì quyết định kỷ luật khiển trách và quyết định kỷ luật cảnh cáo đối với sinh viên được chấm dứt hiệu lực nếu không tái phạm?
**Tài liệu nguồn:** `1054-qd-dhag-2020-09-28.pdf` — Quyết định số 1504/QĐ-ĐHAG (Quy chế CTSV) - Điều 19, Khoản 1-2
**Đáp án chuẩn:** Với kỷ luật khiển trách: sau 03 tháng kể từ ngày có quyết định kỷ luật, nếu sinh viên không tái phạm thì đương nhiên được chấm dứt hiệu lực. Với kỷ luật cảnh cáo: thời hạn là 06 tháng kể từ ngày có quyết định kỷ luật.
**Dòng bổ sung nếu sai:** Đáp án đúng: Khiển trách chấm dứt hiệu lực sau 03 tháng, cảnh cáo sau 06 tháng kể từ ngày có quyết định nếu không tái phạm. (Nguồn: QĐ 1504/QĐ-ĐHAG - Điều 19, Khoản 1-2)

### Q07 · đánh giá rèn luyện
**Câu hỏi:** Điểm rèn luyện của sinh viên ĐHAG gồm những nội dung đánh giá nào và mức điểm tối đa của từng nội dung là bao nhiêu?
**Tài liệu nguồn:** `1059-qd-dhag-2020-09-29.pdf` — Quyết định số 1509/QĐ-ĐHAG (Quy chế Đánh giá KQRL) - Điều 3, Khoản 1
**Đáp án chuẩn:** Điểm rèn luyện gồm 5 nội dung: (1) Ý thức, thái độ tham gia học tập và nghiên cứu khoa học — tối đa 30 điểm; (2) Ý thức chấp hành nội quy, quy chế, quy định trong nhà trường — tối đa 20 điểm; (3) Ý thức tham gia các hoạt động chính trị, xã hội, văn hóa, văn nghệ, TDTT, phòng chống tội phạm và tệ nạn xã hội — tối đa 25 điểm; (4) Ý thức công dân trong quan hệ cộng đồng — tối đa 25 điểm; (5) Các nội dung cộng thêm (Điều 8) — tối đa 10 điểm.
**Dòng bổ sung nếu sai:** Đáp án đúng: 5 nội dung với điểm tối đa lần lượt 30, 20, 25, 25 và 10 điểm (tổng khung 100 điểm + điểm cộng thêm không vượt 100). (Nguồn: QĐ 1509/QĐ-ĐHAG - Điều 3, Khoản 1)

### Q08 · đánh giá rèn luyện
**Câu hỏi:** Sinh viên cần đạt bao nhiêu điểm ở tiêu chí 4 (ý thức công dân trong quan hệ cộng đồng) mới được cộng điểm thưởng, và những đối tượng nào được ngoại lệ?
**Tài liệu nguồn:** `1059-qd-dhag-2020-09-29.pdf` — Quyết định số 1509/QĐ-ĐHAG (Quy chế Đánh giá KQRL) - Điều 7, Khoản 3 và Điều 8, Khoản 4
**Đáp án chuẩn:** Sinh viên phải đạt từ 15 điểm trở lên ở tiêu chí 4 (ý thức công dân trong quan hệ cộng đồng) mới được cộng điểm thưởng. Ngoại lệ (không cần điều kiện 15 điểm): sinh viên khuyết tật, sinh viên mồ côi cả cha lẫn mẹ và sinh viên có hoàn cảnh gia đình đặc biệt khó khăn có nghị lực phấn đấu vươn lên trong học tập.
**Dòng bổ sung nếu sai:** Đáp án đúng: Phải đạt từ 15 điểm trở lên ở tiêu chí 4; ngoại lệ là SV khuyết tật, SV mồ côi cả cha mẹ, SV hoàn cảnh đặc biệt khó khăn có nỗ lực vươn lên. (Nguồn: QĐ 1509/QĐ-ĐHAG - Điều 7 Khoản 3, Điều 8 Khoản 4)

### Q09 · đánh giá rèn luyện
**Câu hỏi:** Sinh viên đang bị kỷ luật khiển trách hoặc kỷ luật cảnh cáo thì xếp loại rèn luyện học kỳ đó bị giới hạn ở mức nào?
**Tài liệu nguồn:** `1059-qd-dhag-2020-09-29.pdf` — Quyết định số 1509/QĐ-ĐHAG (Quy chế Đánh giá KQRL) - Điều 11, Khoản 1-2
**Đáp án chuẩn:** Trong thời gian bị kỷ luật khiển trách, sinh viên khi đánh giá kết quả rèn luyện không được vượt quá loại Khá. Trong thời gian bị kỷ luật cảnh cáo, không được vượt quá loại Trung bình.
**Dòng bổ sung nếu sai:** Đáp án đúng: Bị kỷ luật khiển trách thì rèn luyện không vượt quá loại Khá; bị kỷ luật cảnh cáo thì không vượt quá loại Trung bình. (Nguồn: QĐ 1509/QĐ-ĐHAG - Điều 11, Khoản 1-2)

### Q10 · đánh giá rèn luyện
**Câu hỏi:** Quy trình đánh giá kết quả rèn luyện của sinh viên trải qua những bước nào?
**Tài liệu nguồn:** `1059-qd-dhag-2020-09-29.pdf` — Quyết định số 1509/QĐ-ĐHAG (Quy chế Đánh giá KQRL) - Điều 12, Khoản 1-4
**Đáp án chuẩn:** Quy trình gồm 4 bước: (1) Sinh viên căn cứ hoạt động của bản thân, tự đánh giá theo mức điểm chi tiết của nhà trường; (2) Cố vấn học tập cùng Ban Cán sự lớp xem xét và thông qua mức điểm tự đánh giá của từng sinh viên; (3) Hội đồng cấp khoa xem xét, thống nhất, báo cáo Trưởng khoa thông qua và trình kết quả lên Hội đồng đánh giá KQRL cấp trường; (4) Hội đồng cấp trường hợp xét, thống nhất trình Hiệu trưởng xem xét và quyết định công nhận kết quả.
**Dòng bổ sung nếu sai:** Đáp án đúng: 4 bước — SV tự đánh giá, CVHT và Ban Cán sự lớp thông qua, Hội đồng cấp khoa xét, Hội đồng cấp trường xét và trình Hiệu trưởng quyết định. (Nguồn: QĐ 1509/QĐ-ĐHAG - Điều 12)

### Q11 · đánh giá rèn luyện
**Câu hỏi:** Trong khung điểm rèn luyện, vắng một buổi Sinh hoạt công dân - sinh viên đầu năm bị trừ bao nhiêu điểm và kết quả thu hoạch Tuần Sinh hoạt công dân được quy đổi thế nào?
**Tài liệu nguồn:** `1059-qd-dhag-2020-09-29.pdf` — Quyết định số 1509/QĐ-ĐHAG (Quy chế Đánh giá KQRL) - Khung đánh giá, Mục 3.1
**Đáp án chuẩn:** Trong khung điểm rèn luyện (mục 3.1 - Tuần Sinh hoạt công dân - sinh viên, tối đa 10 điểm): tham gia đầy đủ các buổi SHCD đầu năm; vắng 1 buổi bị trừ 1 điểm; phần có kết quả thu hoạch được tính bằng điểm SHCD nhân với 0.5.
**Dòng bổ sung nếu sai:** Đáp án đúng: Vắng 1 buổi trừ 1 điểm; kết quả thu hoạch Tuần SHCD được tính bằng điểm SHCD × 0.5. (Nguồn: QĐ 1509/QĐ-ĐHAG - Khung đánh giá, Mục 3.1)

### Q12 · sinh viên 5 tốt
**Câu hỏi:** Muốn đạt tiêu chuẩn 'Đạo đức tốt' của danh hiệu Sinh viên 5 tốt cấp Trường, điểm rèn luyện trung bình cả năm học phải đạt bao nhiêu?
**Tài liệu nguồn:** `118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` — Quyết định số 118/QĐ-HSV ngày 23/6/2026 (Quy chế SV 5 tốt giai đoạn 2026-2028) - Điều 5.2.1.1
**Đáp án chuẩn:** Điểm rèn luyện trung bình chung cả năm học phải đạt từ 90 điểm trở lên trên thang điểm 100 (theo quy chế đánh giá kết quả rèn luyện sinh viên hiện hành).
**Dòng bổ sung nếu sai:** Đáp án đúng: Từ 90 điểm trở lên trên thang điểm 100. (Nguồn: QĐ 118/QĐ-HSV ngày 23/6/2026 - Điều 5.2.1.1)

### Q13 · sinh viên 5 tốt
**Câu hỏi:** Tiêu chuẩn 'Học tập tốt' của danh hiệu Sinh viên 5 tốt cấp Trường yêu cầu điểm trung bình bao nhiêu và phải đạt thêm mấy tiêu chí?
**Tài liệu nguồn:** `118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` — Quyết định số 118/QĐ-HSV ngày 23/6/2026 (Quy chế SV 5 tốt) - Điều 5.2.2.1 - 5.2.2.2
**Đáp án chuẩn:** Điểm trung bình chung học tập cả năm học phải đạt từ 8.5/10 (không áp dụng thang điểm hệ 4 hoặc hệ chữ); đồng thời đạt thêm 02 trong các tiêu chí, ví dụ: tham gia sinh hoạt thường xuyên tại ít nhất 01 Câu lạc bộ học thuật trực thuộc Hội Sinh viên Trường, hoặc có đề tài nghiên cứu khoa học từ cấp Khoa trở lên.
**Dòng bổ sung nếu sai:** Đáp án đúng: ĐTBCHT cả năm học từ 8.5/10 trở lên (không dùng thang điểm 4) và đạt thêm 02 tiêu chí (CLB học thuật, đề tài NCKH từ cấp Khoa trở lên...). (Nguồn: QĐ 118/QĐ-HSV - Điều 5.2.2)

### Q14 · sinh viên 5 tốt
**Câu hỏi:** Tập thể Sinh viên 5 tốt cấp Trường cần đạt tỷ lệ sinh viên tham gia phong trào và tỷ lệ sinh viên đạt danh hiệu SV 5 tốt là bao nhiêu?
**Tài liệu nguồn:** `118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` — Quyết định số 118/QĐ-HSV ngày 23/6/2026 (Quy chế SV 5 tốt) - Điều 7.2
**Đáp án chuẩn:** Tập thể Sinh viên 5 tốt cấp Trường cần: 100% sinh viên tham gia phong trào 'Sinh viên 5 tốt'; có ít nhất 30% sinh viên đạt danh hiệu 'Sinh viên 5 tốt' cấp Trường.
**Dòng bổ sung nếu sai:** Đáp án đúng: 100% sinh viên tham gia phong trào và ít nhất 30% sinh viên đạt danh hiệu SV 5 tốt cấp Trường. (Nguồn: QĐ 118/QĐ-HSV - Điều 7.2)

### Q15 · giải thưởng sao tháng giêng
**Câu hỏi:** Đối tượng nào được xét giải thưởng 'Sao Tháng Giêng' cấp Trường và tiêu chuẩn học tập, rèn luyện yêu cầu thế nào?
**Tài liệu nguồn:** `118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` — Quyết định số 118/QĐ-HSV ngày 23/6/2026 (Quy chế SV 5 tốt) - Điều 8 và Điều 9.1 - 9.2
**Đáp án chuẩn:** Đối tượng xét giải thưởng 'Sao Tháng Giêng' cấp Trường là cán bộ Hội/Đoàn đang giữ chức vụ từ Bí thư Chi đoàn, Chi hội trưởng trở lên. Tiêu chuẩn: điểm trung bình chung học tập cả năm học từ 8.7/10 trở lên (riêng sinh viên dân tộc thiểu số từ 8.5/10 trở lên); điểm rèn luyện năm học từ 95 điểm trở lên trên thang 100; có ít nhất 02 năm làm cán bộ Đoàn Thanh niên, cán bộ Hội Sinh viên và đang giữ chức vụ từ Bí thư Chi đoàn, Chi hội trưởng trở lên.
**Dòng bổ sung nếu sai:** Đáp án đúng: Xét cho cán bộ từ Bí thư Chi đoàn, Chi hội trưởng trở lên; học tập từ 8.7/10 (DTTS 8.5/10), rèn luyện từ 95/100 điểm, ít nhất 02 năm làm cán bộ Đoàn - Hội. (Nguồn: QĐ 118/QĐ-HSV - Điều 8, Điều 9)

### Q16 · cuộc thi chính luận
**Câu hỏi:** Tác phẩm dự thi Cuộc thi chính luận về bảo vệ nền tảng tư tưởng của Đảng tỉnh An Giang năm 2026 gồm những thể loại nào và mỗi tác giả được gửi tối đa bao nhiêu tác phẩm?
**Tài liệu nguồn:** `367-QĐ-ĐU ngay 08-4-2026.pdf` — Kế hoạch số 367-KH/ĐU ngày 08/4/2026 - Mục II.2.1, II.2.2
**Đáp án chuẩn:** Tác phẩm dự thi thuộc 1 trong 5 thể loại: Tạp chí, Báo, Phát thanh, Truyền hình, Video clip. Mỗi tác giả/nhóm tác giả được gửi tối đa 05 tác phẩm cho 05 thể loại (mỗi thể loại 01 tác phẩm), gồm tối đa 02 tác phẩm dạng viết (Tạp chí, Báo) và tối đa 03 tác phẩm đa phương tiện (Phát thanh, Truyền hình, Video clip).
**Dòng bổ sung nếu sai:** Đáp án đúng: 5 thể loại (Tạp chí, Báo, Phát thanh, Truyền hình, Video clip); mỗi tác giả/nhóm tối đa 05 tác phẩm, mỗi thể loại 01. (Nguồn: Kế hoạch 367-KH/ĐU - Mục II.2)

### Q17 · cuộc thi chính luận
**Câu hỏi:** Bài viết dự thi cuộc thi chính luận có tỷ lệ trùng lặp tối đa bao nhiêu phần trăm mới đủ điều kiện chấm thi?
**Tài liệu nguồn:** `367-QĐ-ĐU ngay 08-4-2026.pdf` — Kế hoạch số 367-KH/ĐU ngày 08/4/2026 - Mục V.2
**Đáp án chuẩn:** Chỉ những bài viết có tỷ lệ trùng lặp không quá 20% (thể loại Tạp chí) hoặc không quá 25% (thể loại Báo) mới đủ điều kiện đưa vào chấm thi.
**Dòng bổ sung nếu sai:** Đáp án đúng: Tạp chí không quá 20% trùng lặp; Báo không quá 25%. (Nguồn: Kế hoạch 367-KH/ĐU - Mục V.2)

### Q18 · cuộc thi chính luận
**Câu hỏi:** Tác phẩm dự thi cuộc thi chính luận có được sử dụng trí tuệ nhân tạo (AI) không?
**Tài liệu nguồn:** `367-QĐ-ĐU ngay 08-4-2026.pdf` — Thể lệ Cuộc thi chính luận (kèm Kế hoạch số 367-KH/ĐU) - Điều 2.2
**Đáp án chuẩn:** Không. Tác phẩm dự thi không được sử dụng trí tuệ nhân tạo (AI) trong xây dựng nội dung; đối với các thể loại đa phương tiện, không được sử dụng giọng đọc/thuyết minh bằng AI.
**Dòng bổ sung nếu sai:** Đáp án đúng: Không được dùng AI xây dựng nội dung và không được dùng giọng đọc/thuyết minh AI. (Nguồn: Thể lệ Cuộc thi chính luận - Điều 2.2, kèm Kế hoạch 367-KH/ĐU)

### Q19 · thi đua khen thưởng viên chức
**Câu hỏi:** Viên chức, người lao động cần có thời gian công tác liên tục bao lâu mới được xét thi đua khen thưởng tại Trường ĐH An Giang, và tập thể thì sao?
**Tài liệu nguồn:** `888-qd-dhag-2022-08-08.pdf` — Quyết định số 888/QĐ-ĐHAG ngày 02/6/2022 (Quy định thi đua khen thưởng) - Điều 2
**Đáp án chuẩn:** Viên chức, người lao động phải có thời gian công tác liên tục từ 10 tháng trở lên mới được xét thi đua khen thưởng (riêng trường hợp khen thưởng thành tích đột xuất thì không quy định thời gian công tác); tập thể phải có thời gian thành lập từ 12 tháng trở lên.
**Dòng bổ sung nếu sai:** Đáp án đúng: Cá nhân cần công tác liên tục từ 10 tháng trở lên (đột xuất không tính), tập thể cần thành lập từ 12 tháng trở lên. (Nguồn: QĐ 888/QĐ-ĐHAG ngày 02/6/2022 - Điều 2)

### Q20 · thi đua khen thưởng viên chức
**Câu hỏi:** Các danh hiệu thi đua dành cho cá nhân và tập thể tại Trường ĐH An Giang gồm những gì?
**Tài liệu nguồn:** `888-qd-dhag-2022-08-08.pdf` — Quyết định số 888/QĐ-ĐHAG ngày 02/6/2022 (Quy định thi đua khen thưởng) - Điều 8
**Đáp án chuẩn:** Danh hiệu thi đua cá nhân gồm: Lao động tiên tiến, Chiến sĩ thi đua cơ sở, Chiến sĩ thi đua Bộ GD&ĐT, Chiến sĩ thi đua toàn quốc. Danh hiệu thi đua tập thể gồm: Tập thể Lao động tiên tiến, Tập thể Lao động xuất sắc, Cờ thi của Bộ GD&ĐT, Cờ thi của Chính phủ.
**Dòng bổ sung nếu sai:** Đáp án đúng: Cá nhân gồm Lao động tiên tiến, Chiến sĩ thi đua cơ sở/Bộ GD&ĐT/toàn quốc; tập thể gồm Tập thể LĐ tiên tiến, Tập thể LĐ xuất sắc, Cờ thi Bộ GD&ĐT và Cờ thi Chính phủ. (Nguồn: QĐ 888/QĐ-ĐHAG - Điều 8)

### Q21 · khen thưởng ĐHQG-HCM
**Câu hỏi:** Hồ sơ khen thưởng học sinh sinh viên định kỳ và đột xuất của các đơn vị phải gửi về ĐHQG-HCM trước thời điểm nào?
**Tài liệu nguồn:** `QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf` — Quyết định số 1133/QĐ-ĐHQG ngày 05/8/2022 - Điều 7.2a, 7.2b
**Đáp án chuẩn:** Khen thưởng định kỳ: các đơn vị gửi hồ sơ đề xuất khen thưởng về ĐHQG-HCM qua đơn vị thường trực (Ban Công tác Sinh viên) trước ngày 20 tháng 8 hằng năm. Khen thưởng đột xuất hoặc chuyên đề: gửi hồ sơ trước ít nhất 05 ngày làm việc trước khi đơn vị tổ chức trao thưởng.
**Dòng bổ sung nếu sai:** Đáp án đúng: Định kỳ gửi trước ngày 20/8 hằng năm; đột xuất/chuyên đề gửi trước ít nhất 05 ngày làm việc trước khi trao thưởng. (Nguồn: QĐ 1133/QĐ-ĐHQG ngày 05/8/2022 - Điều 7.2)

### Q22 · khen thưởng ĐHQG-HCM
**Câu hỏi:** Khen thưởng đột xuất đối với sinh viên theo Quy định của ĐHQG-HCM được áp dụng khi có thành tích gì?
**Tài liệu nguồn:** `QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf` — Quyết định số 1133/QĐ-ĐHQG ngày 05/8/2022 - Điều 4.3
**Đáp án chuẩn:** Khen thưởng đột xuất áp dụng cho tập thể, cá nhân có thành tích đặc biệt xuất sắc, có phát minh, sáng chế, công trình khoa học, tác phẩm cấp Nhà nước, hoặc đạt giải nhất, nhì, ba trong các cuộc thi cấp quốc tế, hoặc đạt giải nhất các cuộc thi cấp quốc gia, cấp ĐHQG-HCM.
**Dòng bổ sung nếu sai:** Đáp án đúng: Khen thưởng đột xuất áp dụng khi có phát minh, sáng chế, công trình cấp Nhà nước, hoặc giải nhất-nhì-ba cuộc thi quốc tế, hoặc giải nhất cuộc thi quốc gia/cấp ĐHQG-HCM. (Nguồn: QĐ 1133/QĐ-ĐHQG - Điều 4.3)

## Tầng 2

### Q23 · tín dụng sinh viên
**Câu hỏi:** Sinh viên vay vốn tín chấp Ngân hàng ACB theo chương trình 'ACB đồng hành cùng sinh viên ĐHQG-HCM' được vay tối thiểu và tối đa bao nhiêu tiền?
**Tài liệu nguồn:** `163-tb-ctsv-thong-bao-ve-viec-bay-von-tin-chap-tai-ngan-hang-acb-theo-ct-acb-dong-hanh-cung-sinh-vien-dhqg-hcm.pdf` — Thông báo số 163/TB-CTSV ngày 08/8/2025 - Mục 4 (Số tiền cho vay)
**Đáp án chuẩn:** Căn cứ thông báo học phí của Trường, sinh viên được vay tối thiểu 5.000.000 đồng/học kỳ/sinh viên, tối đa không vượt quá 30.000.000 đồng/học kỳ/sinh viên và không vượt quá 50.000.000 đồng/sinh viên/năm học.
**Dòng bổ sung nếu sai:** Đáp án đúng: Tối thiểu 5 triệu đồng/học kỳ; tối đa 30 triệu đồng/học kỳ và không quá 50 triệu đồng/năm học. (Nguồn: TB 163/TB-CTSV ngày 08/8/2025 - Mục 4)

### Q24 · tín dụng sinh viên
**Câu hỏi:** Lãi suất vay vốn tín chấp ACB cho sinh viên là bao nhiêu và trong thời gian ân hạn nợ gốc sinh viên phải trả lãi bao nhiêu?
**Tài liệu nguồn:** `163-tb-ctsv-thong-bao-ve-viec-bay-von-tin-chap-tai-ngan-hang-acb-theo-ct-acb-dong-hanh-cung-sinh-vien-dhqg-hcm.pdf` — Thông báo số 163/TB-CTSV ngày 08/8/2025 - Mục 6 (Lãi suất) và Mục 7 (Trả lãi vay và nợ gốc)
**Đáp án chuẩn:** Trong thời gian học tập còn lại áp dụng kỳ cố định lãi suất cho vay đầu tiên 5,5%/năm. Trong thời gian ân hạn nợ gốc, sinh viên chưa phải trả gốc, chỉ trả lãi suất 2,0%/năm; phần lãi suất còn lại do Quỹ Phát triển (QPT) ĐHQG-HCM hỗ trợ trả để bảo đảm sinh viên trả lãi đúng hạn.
**Dòng bổ sung nếu sai:** Đáp án đúng: Lãi suất 5,5%/năm; trong thời gian ân hạn gốc sinh viên chỉ trả 2,0%/năm, phần còn lại do QPT hỗ trợ. (Nguồn: TB 163/TB-CTSV - Mục 6, 7)

### Q25 · đăng ký học phần
**Câu hỏi:** Điều kiện đăng ký học phần học kỳ I năm học 2026-2027 về học phí và giới hạn số tín chỉ quy định thế nào?
**Tài liệu nguồn:** `KH To chuc HK 261 - 20260612.pdf` — Kế hoạch số 889/KH-ĐHAG ngày 15/6/2026 - Mục II.2 và Phụ lục (Quy định chung về ĐKHP)
**Đáp án chuẩn:** Sinh viên phải không nợ học phí hoặc còn trong thời gian gia hạn học phí, tính tại thời điểm trước khi bắt đầu đăng ký học phần 01 tuần. Số tín chỉ đăng ký trong học kỳ không vượt quá 30 tín chỉ.
**Dòng bổ sung nếu sai:** Đáp án đúng: Không nợ học phí (hoặc còn thời gian gia hạn, tính trước ĐKHP 01 tuần) và đăng ký không vượt quá 30 tín chỉ/học kỳ. (Nguồn: KH 889/KH-ĐHAG ngày 15/6/2026 - Mục II.2, Phụ lục)

### Q26 · đăng ký học phần
**Câu hỏi:** Sinh viên được rút bớt học phần đã đăng ký đến thời điểm nào và sau thời gian đó yêu cầu thay đổi kết quả ĐKHP còn được giải quyết không?
**Tài liệu nguồn:** `KH To chuc HK 261 - 20260612.pdf` — Kế hoạch số 889/KH-ĐHAG ngày 15/6/2026 - Mục II.1 và Mục III
**Đáp án chuẩn:** Sinh viên chỉ được rút bớt học phần đã đăng ký (bằng phiếu) trong 2 tuần đầu của học kỳ theo lịch năm học. Sau tuần học thứ hai của học kỳ, tất cả các yêu cầu liên quan kết quả ĐKHP sẽ không được giải quyết.
**Dòng bổ sung nếu sai:** Đáp án đúng: Rút học phần chỉ trong 2 tuần đầu của học kỳ; sau tuần học thứ hai mọi yêu cầu về kết quả ĐKHP không được giải quyết. (Nguồn: KH 889/KH-ĐHAG - Mục II.1, III)

### Q27 · bảo hiểm y tế
**Câu hỏi:** Mức tối thiểu sinh viên phải mua BHYT năm học 2026-2027 là bao nhiêu và được Nhà nước hỗ trợ bao nhiêu phần trăm?
**Tài liệu nguồn:** `TB tham gia BHYT SV NH 2026 - 2027.pdf` — Thông báo số 1359/TB-ĐHAG ngày 25/8/2026 - Mục I.3
**Đáp án chuẩn:** Mức tối thiểu sinh viên phải mua BHYT năm học 2026-2027 là 546.480 đồng/12 tháng/sinh viên (thời gian sử dụng 12 tháng); mức đóng này đã được Nhà nước hỗ trợ 60%.
**Dòng bổ sung nếu sai:** Đáp án đúng: 546.480 đồng/12 tháng/sinh viên (đã được Nhà nước hỗ trợ 60%). (Nguồn: TB 1359/TB-ĐHAG ngày 25/8/2026 - Mục I.3)

### Q28 · bảo hiểm y tế
**Câu hỏi:** Sinh viên có thẻ BHYT hết hạn vào tháng 10/2026 cần gia hạn khi nào, mức thu bao nhiêu và thẻ mới có giá trị đến khi nào?
**Tài liệu nguồn:** `TB tham gia BHYT SV NH 2026 - 2027.pdf` — Thông báo số 1359/TB-ĐHAG ngày 25/8/2026 - Bảng gia hạn thẻ, Mục I.3
**Đáp án chuẩn:** Với thẻ BHYT hết hạn ngày 31/10/2026: sinh viên đăng ký gia hạn từ 01/10/2026 đến 20/10/2026 với mức thu 637.560 đồng; thẻ mới có giá trị từ 01/11/2026 đến 31/12/2027 (14 tháng).
**Dòng bổ sung nếu sai:** Đáp án đúng: Gia hạn từ 01/10 đến 20/10/2026, mức thu 637.560 đồng, thẻ giá trị từ 01/11/2026 đến 31/12/2027 (14 tháng). (Nguồn: TB 1359/TB-ĐHAG - Mục I.3, bảng gia hạn)

### Q29 · chương trình đào tạo thứ hai
**Câu hỏi:** Điều kiện cơ bản và điều kiện học lực để sinh viên đăng ký học chương trình thứ hai là gì?
**Tài liệu nguồn:** `Thong bao dang ky hoc chuong trinh 2 nam hoc 2026-2027.pdf` — Thông báo số 1050/TB-ĐHAG ngày 06/7/2026 - Mục 1
**Đáp án chuẩn:** Điều kiện cơ bản: là sinh viên đang học tập tại Trường ở hình thức đào tạo chính quy; ngành đăng ký ở chương trình thứ hai phải khác với ngành đang học ở chương trình thứ nhất nhưng cùng trình độ và hình thức đào tạo; đã hoàn thành năm học đầu tiên của chương trình thứ nhất. Điều kiện học lực: học lực tính theo ĐTBCTL xếp hạng khá trở lên và đáp ứng ngưỡng đảm bảo chất lượng của chương trình thứ hai trong năm tuyển sinh; hoặc học lực trung bình và đáp ứng điều kiện trúng tuyển của chương trình thứ hai trong năm tuyển sinh.
**Dòng bổ sung nếu sai:** Đáp án đúng: SV chính quy, ngành CT2 khác ngành đang học (cùng trình độ, hình thức), hoàn thành năm đầu; học lực khá trở lên + ngưỡng ĐBCL, hoặc trung bình + điều kiện trúng tuyển CT2. (Nguồn: TB 1050/TB-ĐHAG - Mục 1)

### Q30 · chương trình đào tạo thứ hai
**Câu hỏi:** Đăng ký học chương trình thứ hai năm học 2026-2027 có mấy đợt nộp hồ sơ và thời gian cụ thể ra sao?
**Tài liệu nguồn:** `Thong bao dang ky hoc chuong trinh 2 nam hoc 2026-2027.pdf` — Thông báo số 1050/TB-ĐHAG ngày 06/7/2026 - Mục 3 (Thời gian thực hiện)
**Đáp án chuẩn:** Đăng ký học chương trình thứ hai có 2 đợt: Đợt 1 nộp hồ sơ từ 06/7/2026 đến 13/7/2026 và xét, thông báo kết quả từ 15/7 đến 17/7/2026; Đợt 2 nộp hồ sơ từ 23/11/2026 đến 29/11/2026 và xét, thông báo kết quả từ 30/11 đến 06/12/2026.
**Dòng bổ sung nếu sai:** Đáp án đúng: Đợt 1 nộp hồ sơ 06/7-13/7/2026 (kết quả 15-17/7/2026); Đợt 2 nộp 23/11-29/11/2026 (kết quả 30/11-06/12/2026). (Nguồn: TB 1050/TB-ĐHAG - Mục 3)

### Q31 · thực tập cuối khoa CNTT
**Câu hỏi:** Điểm thực tập cuối khoa của sinh viên CNTT lớp DH24TH được quy đổi thế nào và nếu không đăng ký thực hiện trong thời gian quy định thì bị xử lý ra sao?
**Tài liệu nguồn:** `ke-hoach-ttck-kltn-dh24th-2026.pdf` — Kế hoạch số 31/KH-KCNTT (TTCK-KLTN DH24TH, NH 2026-2027) - Mục III
**Đáp án chuẩn:** Điểm TTCK được xem như điểm một học phần tương đương 5 tín chỉ. Nếu trong khoảng thời gian quy định, sinh viên không đăng ký thực hiện TTCK thì bị xem như bỏ học học phần này và nhận điểm 0.
**Dòng bổ sung nếu sai:** Đáp án đúng: Điểm TTCK tương đương học phần 5 tín chỉ; không đăng ký đúng thời gian thì xem như bỏ học phần và nhận điểm 0. (Nguồn: KH 31/KH-KCNTT - Mục III)

## File bổ sung

### Q32 · khóa luận tốt nghiệp KTPM
**Câu hỏi:** Sinh viên lớp DH24PM (Kỹ thuật phần mềm) phải nộp bao nhiêu quyển báo cáo thực tập cuối khoa và bao nhiêu quyển khóa luận tốt nghiệp?
**Tài liệu nguồn:** `ke-hoach-ttck-kltn-dh24pm-2026.pdf` — Kế hoạch số 30/KH-KCNTT ngày 08/9/2026 (TTCK-KLTN DH24PM) - Lịch thực hiện TTCK và KLTN
**Đáp án chuẩn:** Sinh viên DH24PM nộp 02 quyển báo cáo TTCK đóng bìa cứng và 07 quyển khóa luận tốt nghiệp đóng bìa cứng; đều kèm file mềm gửi qua Google Drive chứa chương trình cài đặt, báo cáo, phần mềm hỗ trợ (KLTN kèm thêm tóm tắt đề tài).
**Dòng bổ sung nếu sai:** Đáp án đúng: 02 quyển báo cáo TTCK và 07 quyển khóa luận tốt nghiệp, đều đóng bìa cứng kèm file mềm qua Google Drive. (Nguồn: KH 30/KH-KCNTT ngày 08/9/2026)

## Tầng 2

### Q33 · nội quy ký túc xá
**Câu hỏi:** Việc thay đổi vị trí cổng ra vào ký túc xá Trường ĐHAG áp dụng từ khi nào và bộ phận nào chịu trách nhiệm hướng dẫn, kiểm soát việc ra vào?
**Tài liệu nguồn:** `TB16 THAY DOI CONG RA VAO KTX.pdf` — Thông báo số 16/TB-TTDVKTX ngày 16/7/2026 - Mục 2, Mục 3
**Đáp án chuẩn:** Việc thay đổi cổng ra vào ký túc xá áp dụng kể từ ngày ra thông báo (16/7/2026); bộ phận bảo vệ có trách nhiệm hướng dẫn, kiểm soát việc ra vào cổng.
**Dòng bổ sung nếu sai:** Đáp án đúng: Áp dụng kể từ ngày ra thông báo (16/7/2026); bộ phận bảo vệ hướng dẫn, kiểm soát việc ra vào. (Nguồn: TB 16/TB-TTDVKTX - Mục 2, 3)

## File bổ sung

### Q34 · miễn giảm học phí
**Câu hỏi:** Những đối tượng nào được miễn 100% học phí học kỳ I năm học 2025-2026 theo Thông báo của Phòng CTSV?
**Tài liệu nguồn:** `03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf` — Thông báo số 03/TB-CTSV ngày 11/8/2025 - Mục 1
**Đáp án chuẩn:** Đối tượng được miễn 100% học phí gồm: người có công với cách mạng và thân nhân người có công (SV là con của liệt sĩ, con thương binh, con bệnh binh, con người được hưởng chính sách như thương binh); sinh viên khuyết tật; sinh viên mồ côi cả cha và mẹ không nơi nương tựa; sinh viên là người dân tộc thiểu số có cha hoặc mẹ, hoặc ca cha và mẹ, hoặc ở với ông bà thuộc hộ nghèo và hộ cận nghèo năm 2025.
**Dòng bổ sung nếu sai:** Đáp án đúng: Con người có công với cách mạng, SV khuyết tật, SV mồ côi cả cha mẹ không nơi nương tựa, SV DTTS có cha/mẹ (hoặc ở với ông bà) thuộc hộ nghèo/cận nghèo năm 2025. (Nguồn: TB 03/TB-CTSV ngày 11/8/2025 - Mục 1)

### Q35 · miễn giảm học phí
**Câu hỏi:** Sinh viên nào được giảm 50% học phí?
**Tài liệu nguồn:** `03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf` — Thông báo số 03/TB-CTSV ngày 11/8/2025 - Mục 3.1
**Đáp án chuẩn:** Đối tượng được giảm 50% học phí là sinh viên là con của cán bộ, công chức, viên chức, công nhân mà cha hoặc mẹ bị tai nạn lao động hoặc mắc bệnh nghề nghiệp được hưởng trợ cấp thường xuyên.
**Dòng bổ sung nếu sai:** Đáp án đúng: Con cán bộ, công chức, viên chức, công nhân mà cha/mẹ bị tai nạn lao động hoặc mắc bệnh nghề nghiệp hưởng trợ cấp thường xuyên. (Nguồn: TB 03/TB-CTSV - Mục 3.1)

### Q36 · hỗ trợ chi phí học tập
**Câu hỏi:** Sinh viên dân tộc thiểu số thuộc hộ nghèo, cận nghèo được hỗ trợ chi phí học tập mức bao nhiêu?
**Tài liệu nguồn:** `05-tb-ctsv-thong-bao-ve-viec-nop-ho-so-huong-che-do-ho-tro-chi-phi-hoc-tap-hki-nam-hoc-2025-2026.pdf` — Thông báo số 05/TB-CTSV ngày 11/8/2025 - Mục 2
**Đáp án chuẩn:** Mức hỗ trợ chi phí học tập đối với sinh viên là người dân tộc thiểu số thuộc hộ nghèo, hộ cận nghèo bằng 60% mức lương tối thiểu chung, được hưởng không quá 10 tháng/năm học/sinh viên.
**Dòng bổ sung nếu sai:** Đáp án đúng: 60% mức lương tối thiểu chung, hưởng không quá 10 tháng/năm học/sinh viên. (Nguồn: TB 05/TB-CTSV ngày 11/8/2025 - Mục 2)

### Q37 · hỗ trợ chi phí học tập
**Câu hỏi:** Sinh viên khuyết tật thuộc hộ nghèo, cận nghèo được hỗ trợ chi phí học tập và mua sắm đồ dùng học tập mức bao nhiêu?
**Tài liệu nguồn:** `05-tb-ctsv-thong-bao-ve-viec-nop-ho-so-huong-che-do-ho-tro-chi-phi-hoc-tap-hki-nam-hoc-2025-2026.pdf` — Thông báo số 05/TB-CTSV ngày 11/8/2025 - Mục 2
**Đáp án chuẩn:** Sinh viên là người khuyết tật thuộc hộ nghèo, hộ cận nghèo được hỗ trợ chi phí học tập bằng 80% mức lương tối thiểu chung, không quá 10 tháng/năm học/sinh viên; đồng thời được hỗ trợ kinh phí mua sắm phương tiện, đồ dùng học tập 1.000.000 đồng/người/năm học.
**Dòng bổ sung nếu sai:** Đáp án đúng: 80% mức lương tối thiểu chung (tối đa 10 tháng/năm học) và thêm 1 triệu đồng/người/năm học mua phương tiện, đồ dùng học tập. (Nguồn: TB 05/TB-CTSV - Mục 2)

### Q38 · thu và gia hạn học phí
**Câu hỏi:** Hạn chót nộp học phí học kỳ I năm học 2026-2027 là ngày nào và sinh viên có thể nộp học phí thành mấy lần?
**Tài liệu nguồn:** `1413-HPCQ_Thong bao thu HP HKI NH(2026-2027).pdf` — Thông báo số 1413/TB-ĐHAG ngày 04/9/2026 - Mục 2
**Đáp án chuẩn:** Sinh viên nộp học phí học kỳ I năm học 2026-2027 kể từ ngày ra thông báo đến hết ngày 20/10/2026. Sinh viên chưa nộp được một lần có thể đăng ký nộp thành hai lần, lần đầu tối thiểu 50% học phí; thời gian hoàn thành nộp học phí là ngày 20/10/2026.
**Dòng bổ sung nếu sai:** Đáp án đúng: Hạn chót 20/10/2026; có thể nộp 2 lần với lần đầu tối thiểu 50% học phí. (Nguồn: TB 1413/TB-ĐHAG ngày 04/9/2026 - Mục 2)

### Q39 · thu và gia hạn học phí
**Câu hỏi:** Sinh viên xin gia hạn nộp học phí học kỳ I năm học 2026-2027 phải nộp hồ sơ ở đâu và trước ngày nào?
**Tài liệu nguồn:** `1413-HPCQ_Thong bao thu HP HKI NH(2026-2027).pdf` — Thông báo số 1413/TB-ĐHAG ngày 04/9/2026 - Mục 4.2
**Đáp án chuẩn:** Sinh viên có hoàn cảnh khó khăn xin gia hạn nộp học phí thực hiện theo Quyết định số 2542/QĐ-ĐHAG ngày 22/10/2024; hồ sơ gia hạn gửi Phòng Công tác Sinh viên (CTSV), hạn cuối gửi đơn gia hạn đến hết ngày 20/9/2026.
**Dòng bổ sung nếu sai:** Đáp án đúng: Nộp hồ sơ gia hạn tại Phòng CTSV, hạn cuối hết ngày 20/9/2026 (theo QĐ 2542/QĐ-ĐHAG ngày 22/10/2024). (Nguồn: TB 1413/TB-ĐHAG - Mục 4.2)

### Q40 · tín dụng STEM
**Câu hỏi:** Lãi suất vay tín dụng cho sinh viên các ngành STEM là bao nhiêu và lãi suất nợ quá hạn tính thế nào?
**Tài liệu nguồn:** `17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf` — Thông báo số 17/TB-CTSV ngày 12/9/2025 - Mục 4
**Đáp án chuẩn:** Lãi suất cho vay là 4,8%/năm; lãi suất nợ quá hạn được tính bằng 130% lãi suất cho vay.
**Dòng bổ sung nếu sai:** Đáp án đúng: Lãi suất cho vay 4,8%/năm; nợ quá hạn tính bằng 130% lãi suất cho vay. (Nguồn: TB 17/TB-CTSV ngày 12/9/2025 - Mục 4)

### Q41 · tín dụng STEM
**Câu hỏi:** Vốn vay tín dụng STEM bao gồm những khoản gì và tiền sinh hoạt phí, chi phí học tập khác tối đa bao nhiêu mỗi tháng?
**Tài liệu nguồn:** `17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf` — Thông báo số 17/TB-CTSV ngày 12/9/2025 - Mục 3
**Đáp án chuẩn:** Vốn vay gồm: (a) toàn bộ tiền học phí phải đóng của người học (sau khi trừ các khoản học bổng và hỗ trợ tài chính khác của nhà trường nếu có) theo xác nhận của nhà trường; (b) tiền sinh hoạt phí và chi phí học tập khác tối đa 5.000.000 đồng/tháng.
**Dòng bổ sung nếu sai:** Đáp án đúng: Toàn bộ học phí phải đóng (theo xác nhận của nhà trường) và sinh hoạt phí, chi phí học tập khác tối đa 5 triệu đồng/tháng. (Nguồn: TB 17/TB-CTSV - Mục 3)

### Q42 · mức học phí
**Câu hỏi:** Học phí mỗi tín chỉ ngành Công nghệ thông tin và Kỹ thuật phần mềm năm học 2026-2027 cho khóa tuyển sinh năm 2024 trở về trước là bao nhiêu?
**Tài liệu nguồn:** `Qui dinh muc hoc phi nam hoc 2026-2027.pdf` — Quyết định số 2100/QĐ-ĐHAG ngày 20/8/2026 - Phụ lục I.1
**Đáp án chuẩn:** Áp dụng cho khóa tuyển sinh năm 2024 trở về trước (chính quy): ngành Công nghệ thông tin 635.000 đồng/tín chỉ, ngành Kỹ thuật phần mềm 631.000 đồng/tín chỉ.
**Dòng bổ sung nếu sai:** Đáp án đúng: CNTT 635.000 đồng/tín chỉ; Kỹ thuật phần mềm 631.000 đồng/tín chỉ (khóa 2024 trở về trước). (Nguồn: QĐ 2100/QĐ-ĐHAG ngày 20/8/2026 - Phụ lục I.1)

### Q43 · mức học phí
**Câu hỏi:** Học phí mỗi tín chỉ các ngành Công nghệ thông tin, Kỹ thuật phần mềm và Khoa học dữ liệu cho khóa tuyển sinh năm 2026 là bao nhiêu?
**Tài liệu nguồn:** `Qui dinh muc hoc phi nam hoc 2026-2027.pdf` — Quyết định số 2100/QĐ-ĐHAG ngày 20/8/2026 - Phụ lục I.3.2
**Đáp án chuẩn:** Áp dụng cho khóa tuyển sinh năm 2026 (chính quy): Công nghệ thông tin 896.000 đồng/tín chỉ, Kỹ thuật phần mềm 910.000 đồng/tín chỉ, Khoa học dữ liệu 835.000 đồng/tín chỉ.
**Dòng bổ sung nếu sai:** Đáp án đúng: CNTT 896.000, KTPM 910.000, Khoa học dữ liệu 835.000 đồng/tín chỉ (khóa 2026). (Nguồn: QĐ 2100/QĐ-ĐHAG ngày 20/8/2026 - Phụ lục I.3.2)

### Q44 · khảo sát hỗ trợ học phí
**Câu hỏi:** Sinh viên tham gia khảo sát hỗ trợ học phí năm học 2026-2027 bằng hình thức nào và hạn chót là ngày nào?
**Tài liệu nguồn:** `TB_KhaoSatSinhVien_HoTroHocPhi (1).pdf` — Thông báo số 722/TB-ĐHAG ngày 22/5/2026 - Mục 3
**Đáp án chuẩn:** Sinh viên truy cập và hoàn thành đầy đủ thông tin khảo sát trực tuyến trên trang sao.agu.edu.vn (sử dụng tài khoản sinh viên do Nhà trường cấp); hạn chót đến hết ngày 31/5/2026.
**Dòng bổ sung nếu sai:** Đáp án đúng: Khảo sát trực tuyến trên sao.agu.edu.vn bằng tài khoản sinh viên; hạn chót hết ngày 31/5/2026. (Nguồn: TB 722/TB-ĐHAG ngày 22/5/2026 - Mục 3)

### Q45 · khung chương trình đào tạo
**Câu hỏi:** Ngành Công nghệ thông tin Trường ĐH An Giang có mã ngành gì, chỉ tiêu tuyển sinh bao nhiêu và xét tuyển những tổ hợp môn nào?
**Tài liệu nguồn:** `ban-mo-ta-ctdt-nganh-cntt-2021.pdf` — Bản mô tả CTĐT ngành CNTT (07/2021) - Mục 1 và Mục 3
**Đáp án chuẩn:** Ngành Công nghệ thông tin có mã ngành 7480201, trình độ đại học chính quy; dự kiến chỉ tiêu tuyển sinh 180 sinh viên/khóa; các tổ hợp môn xét tuyển là A00, A01, D01, C01.
**Dòng bổ sung nếu sai:** Đáp án đúng: Mã ngành 7480201, chỉ tiêu 180 SV/khóa, tổ hợp xét tuyển A00, A01, D01, C01. (Nguồn: Bản mô tả CTĐT CNTT 2021 - Mục 1, 3)

### Q46 · khung chương trình đào tạo
**Câu hỏi:** Học phần Thực tập cuối khóa và Khóa luận tốt nghiệp trong chương trình đào tạo ngành CNTT có mã và số tín chỉ bao nhiêu?
**Tài liệu nguồn:** `ban-mo-ta-ctdt-nganh-cntt-2021.pdf` — Bản mô tả CTĐT ngành CNTT (07/2021) - Mục 8, Khối IV
**Đáp án chuẩn:** Học phần Thực tập cuối khóa có mã TIE903, khối lượng 5 tín chỉ (thực hành); học phần Khóa luận tốt nghiệp có mã TIE913, khối lượng 10 tín chỉ — đều nằm ở học kỳ VIII của khối kiến thức thực tập, khóa luận tốt nghiệp.
**Dòng bổ sung nếu sai:** Đáp án đúng: Thực tập cuối khóa TIE903 (5 tín chỉ), Khóa luận tốt nghiệp TIE913 (10 tín chỉ), đều ở học kỳ VIII. (Nguồn: Bản mô tả CTĐT CNTT 2021 - Mục 8)

### Q47 · biểu mẫu thủ tục sinh viên
**Câu hỏi:** Đơn đăng ký học, thi cải thiện điểm được nộp cho ai và cần chữ ký duyệt của những ai?
**Tài liệu nguồn:** `don-dang-ky-hoc-thi-cai-thien.docx` — Mẫu đơn đăng ký học, thi cải thiện điểm - Trường ĐH An Giang
**Đáp án chuẩn:** Đơn đăng ký học, thi cải thiện điểm kính gửi Cố vấn học tập và Phòng Đào tạo. Đơn cần có duyệt của Cố vấn học tập, duyệt của Phòng Đào tạo và chữ ký của sinh viên đăng ký (đều ký và ghi rõ họ tên).
**Dòng bổ sung nếu sai:** Đáp án đúng: Kính gửi Cố vấn học tập và Phòng Đào tạo; cần duyệt của CVHT, duyệt của Phòng Đào tạo và ký của sinh viên. (Nguồn: Mẫu đơn đăng ký học, thi cải thiện điểm)

### Q48 · biểu mẫu thủ tục sinh viên
**Câu hỏi:** Đơn xin gia hạn đóng học phí gửi đến ai và phần tiền trong đơn phải khai báo những dòng nào?
**Tài liệu nguồn:** `don-gia-han-hoc-phi-3.docx` — Mẫu đơn xin gia hạn đóng học phí (HK I năm học 2026-2027)
**Đáp án chuẩn:** Đơn xin gia hạn đóng học phí kính gửi Ban Giám hiệu Trường Đại học An Giang. Phần tiền khai báo gồm: tổng học phí học kỳ I năm học 2026-2027; số tiền đã đóng (50%); số tiền còn lại xin gia hạn, kèm mốc ngày xin gia hạn đến và lý do. Sinh viên cam kết nộp đủ học phí đúng thời gian, nếu vi phạm chịu mọi hình thức xử lý kỷ luật của Nhà trường theo quy định.
**Dòng bổ sung nếu sai:** Đáp án đúng: Gửi Ban Giám hiệu; khai tổng học phí, số đã đóng (50%), số còn lại xin gia hạn và cam kết nộp đủ đúng hạn. (Nguồn: Mẫu đơn xin gia hạn đóng học phí)

### Q49 · biểu mẫu thủ tục sinh viên
**Câu hỏi:** Đơn xin công nhận điểm M (miễn học phần) tiếng Anh áp dụng cho những học phần nào, với lý do gì và cần nộp kèm giấy tờ gì?
**Tài liệu nguồn:** `don-xin-mien-hoc-phan-tieng-anh.docx` — Mẫu đơn xin công nhận điểm M (miễn học phần) - Trường ĐH An Giang
**Đáp án chuẩn:** Đơn xin công nhận điểm M (miễn học phần) áp dụng cho học phần Tiếng Anh 1 (ENG101) và Tiếng Anh 2 (ENG102), dành cho sinh viên đã có Chứng chỉ quốc gia Tiếng Anh do Trường Đại học An Giang cấp. Khi nộp đơn, sinh viên kèm theo bản chính và bản photo Chứng chỉ (không cần công chứng) để đối chiếu.
**Dòng bổ sung nếu sai:** Đáp án đúng: Áp dụng cho ENG101 và ENG102; lý do là có Chứng chỉ quốc gia Tiếng Anh do ĐHAG cấp; nộp kèm bản chính và bản photo chứng chỉ (không cần công chứng). (Nguồn: Mẫu đơn xin công nhận điểm M)

### Q50 · tuần sinh hoạt công dân
**Câu hỏi:** Tuần Sinh hoạt công dân - sinh viên của các khóa DH26, DH25 và DH24 năm học 2026-2027 diễn ra vào những ngày nào, hình thức nào?
**Tài liệu nguồn:** `lich-hoc-tap-tuan-shcd-sv-2026-2027-dh24-dh25-dh26.pdf` — Lịch học tập Tuần SHCD - SV khóa DH26, DH25, DH24 NH 2026-2027 (ban hành 07/9/2026)
**Đáp án chuẩn:** Tuần Sinh hoạt công dân - sinh viên năm học 2026-2027 học trực tuyến qua phần mềm Google Meet: khóa DH26 học ngày 21-22/9/2026; khóa DH25 học ngày 23-24/9/2026; khóa DH24 học ngày 25-26/9/2026.
**Dòng bổ sung nếu sai:** Đáp án đúng: Trực tuyến qua Google Meet — DH26 ngày 21-22/9/2026, DH25 ngày 23-24/9/2026, DH24 ngày 25-26/9/2026. (Nguồn: Lịch học Tuần SHCD-SV NH 2026-2027)
