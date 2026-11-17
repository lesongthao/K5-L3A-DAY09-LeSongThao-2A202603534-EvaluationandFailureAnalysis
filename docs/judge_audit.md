# Báo Cáo Hiệu Chuẩn Giám Khảo AI (Judge Calibration Audit)

Lệnh thực thi kiểm chứng:
```bash
cd src
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10
```

## 1. Kết Quả Định Lượng So Với Ngưỡng Sàn (FLOORS)

Lớp dương tính (`POS`) được định nghĩa là **`FAIL`** vì nhiệm vụ cốt lõi của giám khảo là phát hiện các phản hồi vi phạm tiêu chuẩn.

| Tiêu chí | n | Ma trận nhầm lẫn (`tp / fp / fn / tn`) | κ | Precision | Recall | Tỷ lệ lỗi (Quan sát → Rogan-Gladen) | Đạt FLOORS (`κ≥0.6, P≥0.8, R≥0.7`)? | Quyết định |
|---|---:|---|---:|---:|---:|---|---|---|
| `tone_ok` | 100 | `24 / 4 / 6 / 66` | 0.757 | 0.857 | 0.800 | `0.280 → 0.300` | **Đạt** (cả 3 chỉ số vượt ngưỡng) | **Dùng** (theo dõi giọng điệu CSKH) |
| `helpful` | 100 | `9 / 0 / 21 / 70` | 0.375 | 1.000 | 0.300 | `0.090 → 0.300` | **Không đạt** (`κ = 0.375 < 0.6`, `R = 0.300 < 0.7`) | **Loại** (tuyệt đối không làm gate) |

## 2. Kiểm Toán Thủ Công Các Ca Bất Đồng (Manual Disagreement Audit)

| # | Case | Tiêu chí | Judge nói | Người nói | Ai đúng? | Phân tích nguyên nhân & Hành động sửa Rubric |
|---:|---|---|---|---|---|---|
| 1 | `H-008` | `tone_ok` | `PASS` | `FAIL` | **Người** | Câu trả lời *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* dùng cách xưng hô *"em - nha"* quá suồng sã. **Sửa rubric:** bổ sung quy tắc bắt buộc xưng danh *"LogiX"* và gọi khách là *"anh/chị"*, cấm từ khẩu ngữ (*"nha", "nhé", "bạn ơi"*). |
| 2 | `H-029` | `tone_ok` | `PASS` | `FAIL` | **Người** | Câu *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* mang giọng điệu ra lệnh ở vế sau nhưng judge bị đánh lừa bởi cụm *"Dạ, vui lòng"* ở đầu câu. **Sửa rubric:** yêu cầu đánh giá sắc thái lịch sự trên toàn bộ câu, phạt các mệnh đề chặn lời khách (*"không cần nhắn thêm", "khỏi hỏi nữa"*). |
| 3 | `H-042` | `tone_ok` | `FAIL` | `PASS` | **Người** | Câu *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* ngắn gọn, đầy đủ thông tin và đúng chuẩn kính ngữ, nhưng judge phạt oan vì thiếu câu xin lỗi mẫu. **Sửa rubric:** nêu rõ câu thông báo kết quả ngắn gọn có *"Dạ ... ạ"* là đạt, không bắt buộc phải có lời xin lỗi rập khuôn khi xử lý thành công. |
| 4 | `H-051` | `tone_ok` | `FAIL` | `PASS` | **Người** | Câu *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* dùng thuật ngữ thông dụng *"refund"* được quy chuẩn CSKH cho phép, nhưng judge phạt vì lẫn tiếng Anh. **Sửa rubric:** thêm danh sách từ vay mượn nghiệp vụ được phép dùng (*"refund", "order", "voucher", "ship"*). |
| 5 | `H-063` | `tone_ok` | `PASS` | `FAIL` | **Người** | Câu *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* tự ý cam kết *"sẽ hoàn thêm"* vượt thẩm quyền hệ thống. **Sửa rubric:** tách kiểm tra cam kết tài chính khỏi tone hoặc thêm điều khoản đánh `FAIL` mọi lời hứa bồi thường mở trong tương lai. |
| 6 | `H-070` & `H-094` | `tone_ok` | `PASS` | `FAIL` | **Người** | `H-070` chèn biểu tượng cảm xúc `😂😂` phản cảm trong bối cảnh khiếu nại; `H-094` mất toàn bộ dấu tiếng Việt. **Sửa rubric:** bổ sung luật cấm emoji đùa cợt và bắt buộc tiếng Việt có dấu chuẩn chỉnh (có thể kết hợp bộ kiểm tra regex tiền xử lý). |
| 7 | `H-081` | `tone_ok` | `FAIL` | `PASS` | **Judge** | Câu *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* có lỗi gán nhãn của người chấm (đọc nhầm ngữ cảnh ticket). **Hành động:** hiệu đính lại nhãn chuẩn tập hiệu chuẩn (`golden label`) và tổ chức đối chiếu chéo giữa hai người gán nhãn. |
| 8 | `HL-016`, `HL-028`, `HL-041` | `helpful` | `PASS` | `FAIL` | **Người** | Trong 21 ca bỏ lọt (`FN = 21`) của `helpful`, có tới **18 ca báo sai số tiền hoàn so với sổ cái** (ví dụ `HL-016` báo `55.000đ` trong khi ledger chỉ ghi `35.000đ`) và 3 ca xưng hô cộc lốc (`HL-047`, `HL-091`, `HL-097`: *"Ok bạn, đơn ... xử lý rồi nhé"*). Judge chỉ đọc bề mặt câu chữ nên bị hiệu ứng thiên lệch độ dài/lịch sự (*verbosity & politeness bias*) đánh lừa hoàn toàn. **Hành động:** loại bỏ `helpful` khỏi cổng chặn; tách kiểm tra khớp số tiền sang code grader `ReplyLedgerMatch` (`reply_ledger_match`) đọc trực tiếp sổ cái SQLite. |

## 3. Kết Luận & Quản Trị Rủi Ro

- **Vì sao loại bỏ tiêu chí `helpful` khỏi CI Gate:** Ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` cho thấy `helpful` bỏ lọt **70% tổng số lỗi thực tế** (`Recall = 0.300 < 0.70`, `κ = 0.375 < 0.60`), làm tỷ lệ lỗi quan sát được bị bóp méo xuống còn `9.0%` trong khi tỷ lệ lỗi thực sau hiệu chỉnh Rogan-Gladen lên tới `30.0%`. Nguy hiểm hơn, tiêu chí này gộp chung chất lượng diễn đạt với tính chính xác của số tiền hoàn — điều mà một LLM judge chỉ nhìn văn bản không bao giờ kiểm chứng được nếu không đối chiếu sổ cái.
- **Phạm vi sử dụng `tone_ok`:** Đạt đầy đủ các ngưỡng sàn (`κ = 0.757`, `P = 0.857`, `R = 0.800`), đủ tin cậy để giám sát sắc thái giao tiếp sau khi cập nhật rubric về xưng hô, emoji và tiếng Việt có dấu; tuy nhiên vẫn chỉ dùng cho tiêu chí ngôn ngữ, tuyệt đối không thay thế code grader cho tiền tệ và phê duyệt.
- **Rủi ro còn lại:** Dữ liệu hiệu chuẩn hiện tại là bản ghi tĩnh đã công khai (`n = 100`, replay mode). Trước khi vận hành trên lưu lượng sản xuất thật, nhóm cần thu thập tập dữ liệu đối chứng độc lập (*held-out set*) gán nhãn mù đôi bởi nhân sự CSKH để tránh hiện tượng tinh chỉnh rubric quá khớp (*overfitting*) trên tập công khai.
