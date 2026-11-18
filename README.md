# Hệ Thống Quản Lý Nhà Trọ và Thanh Toán Tiền Phòng (FastAPI + MySQL + HTML/CSS/JS)

Hệ thống phần mềm hoàn chỉnh đáp ứng đầy đủ nghiệp vụ văn hóa thuê trọ và quy định pháp luật Việt Nam (Bộ luật Dân sự 2015 & Luật Nhà ở 2023), được thiết kế theo kiến trúc **Modular / Service Architecture**.

---

## 🏗️ 1. Kiến Trúc Dịch Vụ (Modular / Service Architecture)

Hệ thống được chia thành 6 Service độc lập tương tác qua RESTful API (`/api/*`):
1. **Auth & Account Service** (`app/services/auth_service.py`, `app/api/auth.py`):
   - Phân quyền Chủ trọ (`LANDLORD` - `admin`) và Tài khoản Phòng (`TENANT` - `[Số tầng].[Số phòng]` từ `1.1` đến `3.5`).
   - Quản lý phiên đăng nhập bằng `token_version` trong JWT: Khi chủ trọ bấm **"Khách trả phòng / Reset tài khoản"**, hệ thống lập tức thu hồi toàn bộ thiết bị đang đăng nhập vào phòng đó.
2. **Room Service** (`app/services/room_service.py`, `app/api/rooms.py`):
   - Quản lý tầng, phòng, giá thuê cơ bản (mặc định `2.000.000 VNĐ/tháng`, tùy chỉnh theo phòng), trạng thái (`AVAILABLE`, `RENTED`, `MAINTENANCE`).
   - Quản lý phụ phí cố định tách biệt: Phí gửi xe (`100.000đ`), Phí rác/vệ sinh (`30.000đ`), Phí Wifi (`50.000đ`), Phí bảo trì điện nước (`20.000đ`).
3. **Tenant & 30-Day Archive Service** (`app/services/tenant_service.py`, `app/api/tenants.py`):
   - Khai báo hồ sơ khách thuê lần đầu (Họ tên, Giới tính, Ngày sinh, SĐT, Gmail, CCCD, Quê quán).
   - Cơ chế **Lưu trữ tạm 30 ngày (`ArchivedTenant`)**: Khi khách trả phòng, hồ sơ khách cũ được chuyển vào trạng thái `ARCHIVED` với mốc `deleted_at` và giữ đúng **30 ngày** trước khi tự động xóa sạch bằng Cronjob.
4. **Contract Service** (`app/services/contract_service.py`, `app/api/contracts.py`):
   - Hợp đồng thuê phòng chuẩn pháp luật Việt Nam (Quốc hiệu, Tiêu ngữ, căn cứ Bộ luật Dân sự & Luật Nhà ở, Bên A, Bên B, điều khoản, chữ ký).
   - Hỗ trợ xem trực tiếp, in ấn và tải xuống file **PDF chuẩn tiếng Việt** (`/api/contracts/{id}/pdf`).
5. **Billing, Payment & Debt Service** (`app/services/billing_service.py`, `app/api/invoices.py`):
   - Ghi chỉ số điện/nước hằng tháng, tự động tính tiền và phát hành hóa đơn.
   - Hạn đóng tiền cố định: **Ngày 10 hằng tháng**. Sau 5 ngày (tức từ **Ngày 15 hằng tháng**), tự động chuyển sang **`OVERDUE` (Quá hạn / Nợ)** và đánh dấu đỏ phòng đó.
   - **Phương thức 1 (Online Demo)**: Thanh toán qua **MoMo, Thẻ Visa, Ngân hàng liên kết** -> Gạch nợ ngay lập tức, gửi thông báo & Hóa đơn PDF qua Gmail.
   - **Phương thức 2 (VietQR & Upload Bill UNC)**: Hiển thị mã VietQR, khách tải ảnh chụp Bill chuyển khoản lên hệ thống -> Chủ trọ bấm **"Kiểm tra/Đối soát giao dịch Demo"** và **"Xác nhận đã thu tiền"** -> Gửi biên lai PDF qua Gmail.
6. **Feedback & Notification Service** (`app/services/feedback_service.py`, `app/services/notification_service.py`):
   - Khách gửi Feedback phân loại (Điện nước, An ninh, Vệ sinh, Góp ý chung). Phòng có Feedback mới tự động đẩy lên đầu danh sách Admin với nhãn đỏ **"Cần đọc (Chưa đọc)"**.
   - Hệ thống **Toast Notification 10 giây**: Popup trượt ra góc phải màn hình trong đúng 10 giây, sau đó tự động thu nhỏ bay vào biểu tượng **Chiếc chuông (Bell Icon)**.

---

## 🚀 2. Hướng Dẫn Chạy Nhanh (Quick Start)

### Bước 1: Khởi tạo 15 Phòng (3 Tầng) & Dữ liệu mẫu thực tế Việt Nam
```bash
cd backend
python seed_demo.py
```

### Bước 2: Khởi chạy Server (Backend + Frontend Portal)
```bash
cd backend
python run.py
```

### Bước 3: Truy cập Hệ thống
- **Giao diện Web Portal (Admin & Tenant HTML/CSS/JS)**: [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app) (hoặc mở trực tiếp file `frontend/index.html`)
- **Swagger UI API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🔑 3. Tài Khoản Demo Đã Nạp Sẵn (`seed_demo.py`)

| Vai trò / Kịch bản | Tên đăng nhập | Mật khẩu | Mô tả kịch bản |
|---|---|---|---|
| **Chủ trọ (Admin)** | `admin` | `admin123` | Quản lý toàn bộ 15 phòng 3 tầng, tính tiền, duyệt bill, kiểm tra nợ, kho lưu trữ 30 ngày |
| **Phòng 1.1** (Đã đóng tiền) | `1.1` | `123456` | Nguyễn Văn An - Đã thanh toán qua **MoMo**, có Hợp đồng PDF & phản hồi Feedback |
| **Phòng 1.2** (Đã đóng tiền) | `1.2` | `123456` | Trần Thị Bích Ngọc - Đã thanh toán qua **Thẻ Visa** |
| **Phòng 2.1** (Đã đóng tiền) | `2.1` | `123456` | Võ Thị Thanh Thảo - Đã thanh toán qua **Ngân hàng liên kết** |
| **Phòng 1.3** (Chờ duyệt Bill) | `1.3` | `123456` | Lê Hoàng Nam - Đã tải lên ảnh Bill UNC Vietcombank chờ Chủ trọ duyệt |
| **Phòng 2.2** (Chờ duyệt Bill) | `2.2` | `123456` | Đặng Quốc Khánh - Đã tải lên ảnh Bill UNC MB Bank + Có Feedback mới **"Cần đọc"** |
| **Phòng 1.4** (Quá hạn / Nợ) | `1.4` | `123456` | Phạm Minh Tuấn - **Quá hạn sau ngày 15**, nợ cả tháng `2026-10` và `2026-11` + Có Feedback mới |
| **Phòng 2.3** (Quá hạn / Nợ) | `2.3` | `123456` | Hoàng Thị Mai Hương - **Quá hạn sau ngày 15**, nợ cả tháng `2026-10` và `2026-11` |
| **Phòng 3.1** (Quá hạn / Nợ) | `3.1` | `123456` | Bùi Tiến Dũng - **Quá hạn sau ngày 15**, nợ cả tháng `2026-10` và `2026-11` |
| **Phòng 3.2, 3.3** (Đang thuê) | `3.2`, `3.3` | `123456` | Có hóa đơn tháng `2026-11` chờ thanh toán để test Cổng thanh toán Online / VietQR |
| **Phòng 1.5, 2.4, 3.4, 3.5** | `2.4` | `123456` | Phòng trống - Đăng nhập để test quy trình **Khai báo thông tin khách thuê lần đầu** |
