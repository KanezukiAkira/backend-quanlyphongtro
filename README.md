# Hệ Thống Quản Lý Phòng Trọ - Backend (FastAPI + MySQL)

Dự án Backend quản lý phòng trọ chuyên nghiệp, đầy đủ các tính năng cơ bản và nâng cao theo đúng yêu cầu đề bài.

## 🚀 Công Nghệ Sử Dụng
- **Ngôn ngữ**: Python 3.10+
- **Framework**: FastAPI (RESTful API, Async, Swagger UI)
- **Database**: MySQL 8.0 (kết nối qua SQLAlchemy 2.0 & PyMySQL)
- **Xác thực & Bảo mật**: JWT Bearer Token, Bcrypt Password Hashing, RBAC (Landlord & Tenant)
- **Kiểm thử tự động**: 30/30 Test Cases tích hợp (Pass 100%)

---

## 📋 Các Chức Năng Chính
1. **Quản lý Tài khoản & Phân quyền**:
   - Tài khoản **Chủ trọ (Landlord)**: Cố định mặc định (`admin` / `admin123`).
   - Tài khoản **Khách thuê (Tenant)**: Tự đăng ký tài khoản (họ tên, số điện thoại, mật khẩu).
   - Chủ trọ có API lọc danh sách khách thuê chưa ký hợp đồng để thêm vào phòng.
2. **Quản lý Phòng trọ (Room Service)**:
   - Thêm, sửa, xóa, tìm kiếm phòng, giá thuê, diện tích, sức chứa.
   - Trạng thái tự động: `AVAILABLE` (Trống), `RENTED` (Đang thuê), `MAINTENANCE` (Bảo trì).
3. **Quản lý Hợp đồng (Contract Service)**:
   - Ký hợp đồng gán khách thuê vào phòng $\rightarrow$ Tự động chuyển phòng sang `RENTED`.
   - Quy định tiền cọc, đơn giá điện (đ/kWh), nước (đ/m3), phí dịch vụ (rác, wifi).
   - Khi thanh lý hợp đồng $\rightarrow$ Tự động trả phòng về `AVAILABLE`.
4. **Ghi chỉ số Điện, Nước theo tháng (Utility Service)**:
   - Ghi chỉ số định kỳ theo tháng `YYYY-MM`.
   - Tự động lấy chỉ số cuối của tháng trước làm chỉ số đầu tháng này.
5. **Tự động Lập Hóa Đơn (Billing Service)**:
   - Lập hóa đơn hàng loạt hoặc đơn lẻ cho tất cả phòng có hợp đồng hiệu lực.
   - Công thức tính tự động:
     $$\text{Tổng tiền} = \text{Tiền phòng} + (\Delta \text{Điện} \times \text{Đơn giá}) + (\Delta \text{Nước} \times \text{Đơn giá}) + \text{Phí dịch vụ}$$
6. **Thanh toán & Công nợ (Payment Tracking)**:
   - **Quy tắc**: Chỉ chấp nhận thanh toán đủ 100% (`PAID`), không hỗ trợ thanh toán một phần.
   - Ghi nhận ngày giờ thanh toán, hình thức (Tiền mặt / Chuyển khoản), ngăn thanh toán trùng lặp.
7. **Thống kê & Báo cáo (Stats Service)**:
   - Doanh thu theo tháng, biểu đồ lịch sử, tổng nợ chưa thu, tỷ lệ lấp đầy phòng.

---

## 🛠️ Hướng Dẫn Cài Đặt & Chạy Server

### 1. Chuẩn bị môi trường
- Python 3.10 trở lên
- MySQL Server đang chạy trên cổng `3306`

### 2. Cài đặt thư viện
```bash
cd backend
python -m venv venv
# Kích hoạt venv (Windows):
.\venv\Scripts\activate
# Cài đặt requirements:
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường
Tạo file `backend/.env` (tham khảo `backend/.env.example`):
```env
PROJECT_NAME="Quản Lý Phòng Trọ"
DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/quanlyphongtro_db
SECRET_KEY=your_secret_jwt_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### 4. Khởi chạy Server
```bash
python run.py
```
Server sẽ tự động:
- Kiểm tra và tạo database `quanlyphongtro_db` trên MySQL nếu chưa có.
- Sinh đầy đủ tất cả các bảng quan hệ.
- Nạp sẵn tài khoản Chủ trọ cố định: `admin` / `admin123`.

### 5. Khởi tạo dữ liệu mẫu Demo (Tùy chọn)
Để có sẵn dữ liệu 4 phòng trọ, 2 khách thuê, hợp đồng, chỉ số điện nước và hóa đơn phục vụ thuyết trình:
```bash
python seed_demo.py
```

### 6. Chạy Kiểm Thử Tự Động (Integration Tests)
```bash
python test_integration.py
```

---

## 📖 Tài Liệu API Trực Quan (Swagger UI)
Sau khi bật server, truy cập:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
