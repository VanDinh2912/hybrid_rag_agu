# Review gán `question_type` cho 100 câu — benchmark v2

> Ngày 2026-10-20 · Nguồn: `data/evaluation/benchmark_100_questions_v2.json` (v2.1) · Căn cứ: `TAXONOMY.md` v1.0 (đã duyệt ngày 2026-10-20).
> Trạng thái: **đã duyệt 2026-10-20** — bảng này là nguồn nhãn chính thức của `benchmark_100_questions_v3.json`.

Nhãn được rà thủ công từng câu theo thứ tự luật C.1 → C.4 của TAXONOMY.md; không dùng đề xuất từ khóa tự động. `raw_query` trong bảng đã rút gọn để dễ đọc, bản đầy đủ nằm trong v2.

| ID | raw_query (ngắn) | question_type đề xuất | Lý do 1 dòng |
|---|---|---|---|
| Q01 | Môn học 'Thiết kế và cài đặt mạng' có mã môn học là gì, khối lượng mấy tín chỉ… | `TRA_CUU` | Một môn: mã, tín chỉ, học kỳ, môn trước — thuộc tính cùng đối tượng. |
| Q02 | Chuẩn đầu ra ELO 6, ELO 7, ELO 8 và ELO 9 của chương trình đào tạo ngành Công… | `SO_SANH` | Tổng hợp 4 chuẩn đầu ra ELO 6–9 (nhiều đối tượng). |
| Q03 | Tổng số tín chỉ của toàn chương trình đào tạo ngành CNTT là bao nhiêu và bao… | `TRA_CUU` | Các con số trong cùng cơ cấu tín chỉ của một CTĐT. |
| Q04 | Khối kiến thức đại cương (Mục I) trong chương trình đào tạo ngành CNTT có bao… | `TRA_CUU` | Tín chỉ và tỷ lệ của cùng một khối kiến thức. |
| Q05 | Môn 'Giới thiệu ngành – ĐH CNTT' có mã môn học là gì, mấy tín chỉ và học vào… | `TRA_CUU` | Một môn: mã, tín chỉ, học kỳ. |
| Q06 | Để học môn 'Lập trình hướng đối tượng' (COS102), sinh viên bắt buộc phải học… | `TRA_CUU` | Một điều kiện tiên quyết của một môn. |
| Q07 | Môn học 'Thực tập tốt nghiệp' (CON401) có khối lượng bao nhiêu tín chỉ và sinh… | `TRA_CUU` | Một môn: tín chỉ và học kỳ dự kiến. |
| Q08 | Sinh viên không làm Khóa luận tốt nghiệp phải chọn các môn học thay thế nào… | `TRA_CUU` | Danh sách môn thay thế của một khối. |
| Q09 | Chuẩn đầu ra ELO 1 và ELO 2 của chương trình đào tạo ngành Công nghệ thông tin… | `SO_SANH` | Tổng hợp 2 chuẩn đầu ra ELO 1–2. |
| Q10 | Môn học 'Toán rời rạc' có mã môn học là gì, bao nhiêu tín chỉ và được phân bổ… | `TRA_CUU` | Một môn: mã, tín chỉ, học kỳ. |
| Q11 | Khối kiến thức Chuyên ngành (Mục III) có tổng cộng bao nhiêu tín chỉ, trong đó… | `TRA_CUU` | Các con số trong cùng cơ cấu tín chỉ của một khối. |
| Q12 | Để đăng ký môn 'Đồ án ngành CNTT' (COS308), sinh viên cần đáp ứng điều kiện môn… | `TRA_CUU` | Điều kiện tiên quyết của một môn, không phải thủ tục. |
| Q13 | Các môn học Giáo dục thể chất có tính tín chỉ tích lũy vào tổng số 140 tín chỉ… | `TRA_CUU` | Câu hỏi có/không về tín chỉ GDTC. |
| Q14 | Môn học 'Cấu trúc dữ liệu và giải thuật' có mã môn học là gì, bao nhiêu tín chỉ… | `TRA_CUU` | Một môn: mã, tín chỉ, học kỳ. |
| Q15 | Môn 'Hệ quản trị cơ sở dữ liệu' (COS205) yêu cầu sinh viên phải hoàn thành môn… | `TRA_CUU` | Một môn học trước. |
| Q16 | Khối kiến thức Cơ sở ngành (Mục II) trong chương trình đào tạo gồm bao nhiêu… | `TRA_CUU` | Các con số trong cùng cơ cấu tín chỉ của một khối. |
| Q17 | Chuẩn đầu ra ELO 10 và ELO 11 quy định thái độ và năng lực học tập suốt đời của… | `SO_SANH` | Tổng hợp 2 chuẩn đầu ra ELO 10–11. |
| Q18 | Môn 'Hệ điều hành' có mã môn học là gì và có mấy tín chỉ lý thuyết, thực hành? | `TRA_CUU` | Một môn: mã, tín chỉ lý thuyết/thực hành. |
| Q19 | Môn 'Kiến trúc máy tính và Hợp ngữ' (CON201) học ở học kỳ nào và có môn học… | `TRA_CUU` | Một môn: học kỳ và môn trước. |
| Q20 | Thời gian đào tạo chuẩn theo kế hoạch của chương trình cử nhân Công nghệ thông… | `TRA_CUU` | Một con số thời gian đào tạo. |
| Q21 | Môn 'Trí tuệ nhân tạo' có mã môn học là gì, mấy tín chỉ và học vào học kỳ mấy? | `TRA_CUU` | Một môn: mã, tín chỉ, học kỳ. |
| Q22 | Môn 'Lập trình Web' (COS303) yêu cầu môn học trước là môn nào? | `TRA_CUU` | Một môn học trước. |
| Q23 | Tiêu chí xếp loại kết quả rèn luyện học kỳ đối với các mức Xuất sắc, Tốt, Khá… | `SO_SANH` | Đối chiếu thang điểm của 6 mức xếp loại. |
| Q24 | Sinh viên bị xếp loại rèn luyện Yếu, Kém trong 2 học kỳ liên tiếp sẽ bị xử lý… | `TRA_CUU` | Một quy tắc xử lý khi Yếu/Kém 2 học kỳ liên tiếp. |
| Q25 | Khung điểm đánh giá kết quả rèn luyện sinh viên gồm mấy tiêu chí chính và tổng… | `TRA_CUU` | Số tiêu chí và điểm tối đa của cùng một khung điểm. |
| Q26 | Tiêu chí 1 về 'Đánh giá về ý thức học tập' có điểm tối đa là bao nhiêu và gồm… | `TRA_CUU` | Điểm tối đa và nội dung cộng/trừ của cùng một tiêu chí. |
| Q27 | Sinh viên đạt kết quả học tập trong học kỳ có điểm trung bình chung học kỳ đạt… | `TRA_CUU` | Một mức điểm rèn luyện theo ĐTBCHK. |
| Q28 | Tiêu chí 2 về 'Ý thức chấp hành quy chế, quy định trong Nhà trường' có điểm… | `TRA_CUU` | Điểm khung tối đa của một tiêu chí. |
| Q29 | Sinh viên vi phạm quy chế thi bị kỷ luật ở hình thức Cảnh cáo thi bị trừ bao… | `TRA_CUU` | Một mức trừ điểm cho một hình thức kỷ luật. |
| Q30 | Tiêu chí 3 về 'Ý thức tham gia các hoạt động chính trị, xã hội, văn hóa, văn… | `TRA_CUU` | Điểm tối đa của một tiêu chí. |
| Q31 | Tiêu chí 4 về 'Ý thức công dân trong quan hệ cộng đồng' quy định mức điểm tối… | `TRA_CUU` | Điểm tối đa của một tiêu chí. |
| Q32 | Tiêu chí 5 về 'Ý thức và kết quả tham gia công tác cán bộ lớp, đoàn thể' có… | `TRA_CUU` | Điểm tối đa của một tiêu chí. |
| Q33 | Kết quả rèn luyện toàn khóa học của sinh viên được xác định dựa trên công thức… | `TRA_CUU` | Một công thức/quy tắc tính điểm toàn khóa. |
| Q34 | Danh hiệu thi đua 'Sinh viên Giỏi' năm học yêu cầu sinh viên đạt điểm trung… | `TRA_CUU` | Ngưỡng điểm của một danh hiệu. |
| Q35 | Danh hiệu 'Sinh viên Xuất sắc' năm học đòi hỏi tiêu chuẩn điểm học tập và điểm… | `TRA_CUU` | Ngưỡng điểm của một danh hiệu. |
| Q36 | Sinh viên bị kỷ luật từ mức hình thức nào trở lên trong năm học thì không được… | `TRA_CUU` | Một mức kỷ luật làm mất điều kiện xét. |
| Q37 | Tập thể 'Lớp sinh viên Tiên tiến' cần đáp ứng tiêu chuẩn tỷ lệ sinh viên đạt… | `TRA_CUU` | Một tỷ lệ của một danh hiệu tập thể. |
| Q38 | Tập thể 'Lớp sinh viên Xuất sắc' yêu cầu tiêu chuẩn về tỷ lệ sinh viên Giỏi… | `TRA_CUU` | Một tỷ lệ của một danh hiệu tập thể. |
| Q39 | Mức tiền thưởng kèm theo Giấy khen của Hiệu trưởng cho danh hiệu 'Sinh viên… | `TRA_CUU` | Một mức tiền thưởng. |
| Q40 | Thẩm quyền quyết định trao tặng danh hiệu thi đua cá nhân và tập thể sinh viên… | `TRA_CUU` | Một cơ quan có thẩm quyền. |
| Q41 | Sinh viên đạt giải Nhất cuộc thi Nghiên cứu khoa học sinh viên cấp Trường được… | `TRA_CUU` | Một hình thức khen thưởng cho một giải. |
| Q42 | Điều kiện về điểm học phần khi học lại để cải thiện điểm là sinh viên phải đạt… | `TRA_CUU` | Một ngưỡng điểm học lại cải thiện. |
| Q43 | Quy trình đề nghị khen thưởng năm học đối với sinh viên do đơn vị nào chủ trì… | `TRA_CUU` | Chỉ hỏi đơn vị chủ trì, không hỏi các bước. |
| Q44 | Sinh viên nghỉ học tạm thời vì lý do cá nhân phải hoàn thành tối thiểu bao… | `TRA_CUU` | Một số học kỳ tối thiểu. |
| Q45 | Thời gian nghỉ học tạm thời vì lý do cá nhân được tính vào thời gian tối đa… | `TRA_CUU` | Câu hỏi có/không về thời gian nghỉ tính vào khóa học. |
| Q46 | Sinh viên bị xử lý kỷ luật ở mức buộc thôi học có được xem xét xin nhập học lại… | `TRA_CUU` | Câu hỏi có/không về nhập học lại. |
| Q47 | Nhiệm vụ của Cố vấn học tập trong việc hỗ trợ sinh viên đăng ký học tập đầu mỗi… | `TRA_CUU` | Nhiệm vụ của một chủ thể, không hỏi quy trình. |
| Q48 | Sinh viên có nghĩa vụ gì về việc đeo thẻ sinh viên khi đến Trường học tập và… | `TRA_CUU` | Một nghĩa vụ cụ thể. |
| Q49 | Hành vi gian lận trong thi cử, kiểm tra bị xử lý kỷ luật như thế nào ở lần vi… | `TRA_CUU` | Một mức kỷ luật cho lần vi phạm đầu. |
| Q50 | Danh hiệu 'Sinh viên 5 tốt' cấp Trường đòi hỏi sinh viên phải hoàn thành mấy… | `TRA_CUU` | Một con số tiêu chuẩn. |
| Q51 | Tiêu chuẩn 'Học tập tốt' trong xét chọn 'Sinh viên 5 tốt' cấp Trường yêu cầu… | `TRA_CUU` | Một ngưỡng điểm của một tiêu chuẩn. |
| Q52 | Tiêu chuẩn 'Đạo đức tốt' đối với danh hiệu 'Sinh viên 5 tốt' yêu cầu điểm rèn… | `TRA_CUU` | Một ngưỡng điểm của một tiêu chuẩn. |
| Q53 | Giải thưởng 'Sao Tháng Giêng' dành cho đối tượng sinh viên nào trong Nhà trường? | `TRA_CUU` | Đối tượng của một giải thưởng. |
| Q54 | Tiêu chuẩn điểm rèn luyện để ứng tuyển Giải thưởng 'Sao Tháng Giêng' quy định… | `TRA_CUU` | Một ngưỡng điểm. |
| Q55 | Hồ sơ cá nhân đăng ký danh hiệu 'Sinh viên 5 tốt' bao gồm những tài liệu chứng… | `THU_TUC` | Hỏi thành phần hồ sơ/tài liệu chứng minh. |
| Q56 | Thời gian thực tập thực tế của sinh viên ngành Công nghệ thông tin khóa DH24TH… | `TRA_CUU` | Một con số tuần thực tập. |
| Q57 | Điều kiện để sinh viên ngành CNTT được đăng ký làm Khóa luận tốt nghiệp là gì? | `TRA_CUU` | Điều kiện đăng ký, không phải các bước. |
| Q58 | Nộp báo cáo Thực tập tốt nghiệp chậm so với thời hạn quy định bị xử lý như thế… | `TRA_CUU` | Hệ quả khi nộp báo cáo trễ. |
| Q59 | Điểm đánh giá Thực tập tốt nghiệp gồm những thành phần điểm nào? | `TRA_CUU` | Các thành phần của cùng một thang điểm. |
| Q60 | Sinh viên làm Khóa luận tốt nghiệp phải bảo vệ trước Hội đồng chấm gồm bao… | `TRA_CUU` | Một con số thành viên hội đồng. |
| Q61 | Hình thức trình bày báo cáo Khóa luận tốt nghiệp tuân thủ theo quy chuẩn định… | `TRA_CUU` | Một quy chuẩn định dạng. |
| Q62 | Đối tượng sinh viên thuộc diện hộ nghèo, hộ cận nghèo được miễn giảm bao nhiêu… | `TRA_CUU` | Một tỷ lệ miễn giảm. |
| Q63 | Hồ sơ đề nghị miễn giảm học phí đối với sinh viên khuyết tật gồm những giấy tờ… | `THU_TUC` | Hỏi thành phần hồ sơ/giấy tờ. |
| Q64 | Thời hạn nộp hồ sơ miễn giảm học phí đầu mỗi học kỳ quy định đến ngày nào? | `TRA_CUU` | Một mốc thời hạn. |
| Q65 | Sinh viên thuộc đối tượng mồ côi cả cha lẫn mẹ được hỗ trợ học phí theo văn bản… | `TRA_CUU` | Một văn bản áp dụng. |
| Q66 | Sinh viên bị tạm ngưng học tập có được hưởng chính sách miễn giảm học phí trong… | `TRA_CUU` | Câu hỏi có/không về chính sách. |
| Q67 | Trường hợp sinh viên nộp hồ sơ miễn giảm học phí quá thời hạn quy định sẽ được… | `TRA_CUU` | Hệ quả khi nộp hồ sơ quá hạn. |
| Q68 | Mức thu học phí đối với nhóm ngành Công nghệ thông tin được tính theo công thức… | `TRA_CUU` | Một công thức tính học phí. |
| Q69 | Học phí các môn học lại, học cải thiện điểm được tính theo đơn giá nào? | `TRA_CUU` | Một đơn giá cho học lại/cải thiện. |
| Q70 | Sinh viên nộp học phí trễ hạn không có lý do chính đáng sẽ bị xử lý ra sao? | `TRA_CUU` | Hệ quả khi nộp học phí trễ. |
| Q71 | Thời gian gia hạn nộp học phí tối đa khi sinh viên có đơn xin gia hạn được phê… | `TRA_CUU` | Một thời hạn gia hạn tối đa. |
| Q72 | Đơn giá học phí cho 1 tín chỉ thực hành so với tín chỉ lý thuyết được quy định… | `SO_SANH` | So sánh trực tiếp đơn giá thực hành và lý thuyết. |
| Q73 | Hình thức thanh toán học phí chính thức của Nhà trường qua các kênh giao dịch… | `TRA_CUU` | Danh sách kênh thanh toán. |
| Q74 | Nội dung Cuộc thi Chính luận bảo vệ nền tảng tư tưởng của Đảng năm 2026 tập… | `TRA_CUU` | Danh sách chủ đề của một cuộc thi. |
| Q75 | Các thể loại tác phẩm dự thi trong Cuộc thi Chính luận năm 2026 bao gồm những… | `TRA_CUU` | Danh sách thể loại tác phẩm. |
| Q76 | Đối tượng tham gia Cuộc thi Chính luận năm 2026 trong Nhà trường bao gồm những… | `TRA_CUU` | Danh sách đối tượng tham gia. |
| Q77 | Dung lượng quy định đối với tác phẩm dự thi dạng bài viết Báo in/Báo điện tử là… | `TRA_CUU` | Một giới hạn dung lượng. |
| Q78 | Thời hạn chót nhận bài dự thi Cuộc thi Chính luận năm 2026 cấp Trường là ngày… | `TRA_CUU` | Một mốc thời hạn. |
| Q79 | Cơ cấu giải thưởng Cuộc thi Chính luận cấp Trường gồm những giải thưởng nào? | `TRA_CUU` | Danh sách giải thưởng. |
| Q80 | Tác phẩm dự thi Cuộc thi Chính luận có được trùng lặp với các bài báo đã đăng… | `TRA_CUU` | Câu hỏi có/không về trùng lặp. |
| Q81 | Trách nhiệm của Đoàn Thanh niên - Hội Sinh viên Trường trong tổ chức Cuộc thi… | `TRA_CUU` | Nhiệm vụ của một đơn vị. |
| Q82 | Tiêu chí chấm điểm tác phẩm dự thi Cuộc thi Chính luận đánh giá dựa trên những… | `TRA_CUU` | Danh sách tiêu chí chấm. |
| Q83 | Các tác phẩm xuất sắc tại Cuộc thi cấp Trường sẽ được gửi tham dự cuộc thi ở… | `TRA_CUU` | Một cấp thi tiếp theo. |
| Q84 | Một tác giả hoặc nhóm tác giả được gửi tối đa bao nhiêu tác phẩm tham dự Cuộc… | `TRA_CUU` | Một giới hạn số tác phẩm. |
| Q85 | Đơn vị nào tại Trường ĐHAG là đầu mối thường trực tiếp nhận bài dự thi Cuộc thi… | `TRA_CUU` | Một đầu mối tiếp nhận. |
| Q86 | Kế hoạch Thực tập chuyên đề đối với sinh viên ngành Ngôn ngữ Phần mềm (DH24PM)… | `TRA_CUU` | Một học kỳ triển khai. |
| Q87 | Sinh viên lớp DH24PM khi thực tập chuyên đề tại doanh nghiệp phải nộp tài liệu… | `THU_TUC` | Hỏi tài liệu nghiệm thu phải nộp. |
| Q88 | Trường hợp sinh viên tự liên hệ cơ sở thực tập ngoài danh sách liên kết của… | `THU_TUC` | Hỏi thủ tục khi tự liên hệ cơ sở. |
| Q89 | Tiêu chuẩn xét chọn danh hiệu 'Sinh viên Xuất sắc' toàn khóa học cấp ĐHQG-HCM… | `TRA_CUU` | Điều kiện điểm của một danh hiệu. |
| Q90 | Mức tiền thưởng cho sinh viên đạt danh hiệu Khen thưởng cấp ĐHQG-HCM do cơ quan… | `TRA_CUU` | Một cơ quan chi trả. |
| Q91 | Sinh viên nội trú Ký túc xá Trường ĐHAG có trách nhiệm tuân thủ quy định giờ… | `TRA_CUU` | Quy định giờ giấc nội trú. |
| Q92 | Hành vi sử dụng các thiết bị điện đun nấu trong phòng ở Ký túc xá bị xử lý kỷ… | `TRA_CUU` | Một hình thức xử lý kỷ luật. |
| Q93 | Chương trình tín dụng ưu đãi vay vốn học tập ACB yêu cầu sinh viên cung cấp các… | `THU_TUC` | Hỏi tài liệu xác thực phải cung cấp. |
| Q94 | Lãi suất ưu đãi và thời gian bắt đầu trả nợ gốc chương trình vay vốn học tập… | `TRA_CUU` | Hai thuộc tính của cùng một chương trình vay. |
| Q95 | Mẫu đơn xác nhận hoàn cảnh gia đình sinh viên khó khăn cần có xác nhận của cơ… | `TRA_CUU` | Hỏi một cơ quan xác nhận — thực thể đơn, theo tiền lệ Q64. |
| Q96 | Kế hoạch tổ chức đánh giá Thực tập chuyên đề cấp Khoa do đơn vị nào phê duyệt… | `NGOAI_PHAM_VI` | in_corpus=false — không có căn cứ trong corpus. |
| Q97 | Sinh viên không hoàn thành đủ số giờ thực tập tại doanh nghiệp có được xem xét… | `NGOAI_PHAM_VI` | in_corpus=false — chính sách không có trong corpus. |
| Q98 | Hình thức kỷ luật đối với sinh viên bị phát hiện đạo văn trong báo cáo Khóa… | `NGOAI_PHAM_VI` | in_corpus=false — quy định không có trong corpus. |
| Q99 | Theo thông báo về Bảo hiểm y tế (BHYT) do Phó Hiệu trưởng Nguyễn Hữu Trí ký, Cố… | `TRA_CUU` | Hỏi nhiệm vụ của CVHT/lớp trưởng — nhiệm vụ một chủ thể, theo tiền lệ Q47. |
| Q100 | Tại sao sinh viên tham gia BHYT bắt buộc phải cài đặt ứng dụng VssID-BHXH số và… | `TRA_CUU` | Hỏi lý do của một yêu cầu. |

## Phân bố 4 loại

| Nhãn | Số câu | Tỷ lệ |
|---|---:|---:|
| `TRA_CUU` | 87 | 87% |
| `SO_SANH` | 5 | 5% |
| `THU_TUC` | 5 | 5% |
| `NGOAI_PHAM_VI` | 3 | 3% |
| **Tổng** | **100** | **100%** |

**Lưu ý phân bố:** sau duyệt, `TRA_CUU` chiếm 87% (87/100). Cổng P2.3 đã được nâng (chốt 2026-10-20) thành accuracy tổng ≥ 80% **và** recall từng lớp `SO_SANH`/`THU_TUC`/`NGOAI_PHAM_VI` ≥ 50%, kèm per-class recall/F1 và macro-F1; không thêm câu mới để cân bằng tập trong P1.2.

**Ghi chú cách gán các ca nhiều vế:**

- Các câu tổng hợp nhiều chuẩn đầu ra ELO (Q02, Q09, Q17) và thang điểm 6 mức xếp loại (Q23) xếp `SO_SANH` theo luật C.2 vì phải đối chiếu nhiều đối tượng/mốc.
- Các câu hỏi nhiều thuộc tính của **cùng một đối tượng** (một môn học, một khung điểm, một chương trình vay, một cơ cấu tín chỉ) giữ `TRA_CUU` theo chú giải C — không tính là ghép nhiều nơi.
- Q43 có chữ "quy trình" nhưng chỉ hỏi đơn vị chủ trì, không hỏi các bước → `TRA_CUU`.
- Câu hỏi **"cơ quan nào"** / **"nhiệm vụ của chủ thể"** = `TRA_CUU` dù ngữ cảnh là hồ sơ/thông báo (Q95 theo tiền lệ Q64; Q99 theo tiền lệ Q47).

## Quyết định của người dùng — P1.2 (2026-10-20)

1. **Bảng nhãn:** duyệt 100 nhãn, sửa Q95 và Q99 từ `THU_TUC` → `TRA_CUU`; phân bố chốt: `TRA_CUU=87`, `SO_SANH=5`, `THU_TUC=5`, `NGOAI_PHAM_VI=3`.
2. **Q96–Q98: giữ trống GT.** Đáp án đúng của câu ngoài corpus là **lời từ chối**, đã được đo qua `in_corpus=false`; không cần GT đáp án. Bổ sung GT từ văn bản ngoài corpus sẽ mâu thuẫn nguyên tắc **corpus là biên tri thức** của hệ thống.
   - Lưu ý P4: `skipped_no_gt` chỉ bỏ chấm generation theo GT; phép đo **từ chối/ảo giác** của 3 câu này vẫn phải chạy (đã ghi trong `dev/prompts/archive/P4_1_evaluation_ab_mode.md`).
3. **Per-class:** chấp nhận. Cổng P2.3 (đã nâng trong `dev/prompts/archive/P2_3_classifier_accuracy.md`) gồm accuracy tổng ≥ 80% **và** recall từng lớp `SO_SANH`/`THU_TUC`/`NGOAI_PHAM_VI` ≥ 50%; báo cáo thêm per-class recall/F1 và macro-F1. Không thêm câu mới để cân bằng tập trong P1.2.

