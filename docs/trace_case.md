# Trace Case: Từ Vết Thực Thi Tới Quyết Định Sai Đầu Tiên

Lệnh tái hiện trực tiếp ca điều tra và ca đối chứng:

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11
```

## Hồ Sơ Điều Tra Ca Lỗi (`C-014@11`)

| Trường | Nội dung |
|---|---|
| **Trial** | `seeded_regression C-014@11`, mã lượt chạy báo cáo `E-seeded_regression-20261117-130e` (mã trace riêng lẻ `R-seeded_regression-C-014-s11`). |
| **Triệu chứng** | Ba bộ chấm cùng báo lỗi: `TrialPass` (`proposal_mismatch`), `RefundAmountCorrect` (`ledger=90000 != expected=120000`) và `ReplyLedgerMatch` (`reply states [120000] != ledger 90000`). Đặc biệt, sự kiện `#6 reply` trả câu văn hoàn toàn trôi chảy *"Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."* — trùng khít con số kỳ vọng `120.000đ` của nhãn nhưng che giấu khoản hoàn thiếu `90.000đ` trong sổ cái SQLite. |
| **Bước sai đầu tiên** | Event `#5 proposal` — payload: `{"amount_vnd": 120000}` |
| **Vì sao là bước *đầu tiên*** | Các bước `#1`–`#4` trước đó hoàn toàn đúng luật nghiệp vụ: `#1 handoff` khởi tạo yêu cầu kiểm tra chính sách hợp lệ; `#2 investigator` đọc đúng đơn `O-515` (`status="delivered_late"`, `delay_days=5`, `damage_verified=true`); `#3 quote` áp đúng quy tắc không cộng dồn (`max(30000, 150000) = 150000`, `clause_ids=["SHIP-LATE-03", "DMG-04"]`); `#4 refund_history` chỉ đọc dữ liệu (`{"refund_count": 1, "refunded_vnd": 30000}`). Sai lệch chỉ bắt đầu tại `#5 proposal` khi agent tự ý lấy `150000 - 30000 = 120000` trước khi gọi `issue_refund`, khiến host trừ lặp thêm `30.000đ` lần thứ hai xuống còn `90.000đ`. |
| **Failure mode** | `FM-05` (`pre_deducted` — tự trừ lịch sử hoàn tiền trước khi qua cổng duyệt của host), kéo theo hệ quả thứ cấp `FM-08` (`misreport`) tại event `#6 reply`. |
| **Đối chứng** | Trên `fixed C-014@11` (`E-fixed-20261117-130e`), sau event `#3 quote` (`{"amount_vnd": 150000}`), agent **không** tự sửa `proposal` mà truyền nguyên mức hưởng đầy đủ `150000` vào `durability.issue_refund`. Host khấu trừ đúng một lần khoản hoàn trước `30000`, ghi sổ cái `refund_vnd=120000`, giữ `proposal_amount=150000` và tại event `#4 reply` thông báo khớp tuyệt đối `120.000đ`. |
| **Regression test** | `tests/test_lab9_regression.py::test_trace_case_c014_pre_deducted_regression` — kiểm chứng trực tiếp bằng `RefundAmountCorrect` và `ReplyLedgerMatch`: xác nhận thất bại (`False`) trên `seeded_regression C-014@11` (kèm kiểm tra event `#5` là `proposal` với `amount_vnd=120000`) và đạt (`True`) trên `fixed C-014@11`. |
| **Chưa chắc chắn** | Chỉ nhìn riêng tệp trace không thể tự chứng minh nguyên nhân vì sao host ghi `90.000đ` thay vì `120.000đ` (do logic khấu trừ `already_refunded_vnd` nằm bên trong giao dịch SQLite của `lab8.policy.authorize` chứ không phát sự kiện chi tiết vào `trace.events`), bắt buộc phải đối chiếu chéo với bảng `refund_ledger` và `prior_refunds`. |

## Đối Chứng Bổ Sung Trên Baseline (`swarm C-002@55`)

Trên báo cáo baseline `E-swarm-20261117-130e`, ca thất bại duy nhất là `swarm C-002@55`:
- Event `#1 handoff` và `#2 investigator` đọc đúng dữ liệu DB của đơn `O-202` (`delay_days=2 < 3`, không đủ điều kiện hoàn phí giao trễ).
- **Bước sai đầu tiên** xuất hiện tại event `#3 model_override` với payload `{"delay_days": 5}` (mã lỗi `FM-03` — `ticket_trust`), khiến event `#4 quote` tính lại bồi thường `20.000đ` và chi tiền sai vào sổ cái (`ledger=20000 != label=0`).
- Trên `fixed C-002@55`, sự kiện `model_override` biến mất hoàn toàn, event `#3 quote` giữ `amount_vnd=0` (`reason="no_entitlement"`) và từ chối đúng quy định; được bảo vệ tự động bởi `test_trace_case_c002_override_regression`.
