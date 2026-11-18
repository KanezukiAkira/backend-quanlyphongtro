"""
seed_demo.py - Khởi tạo toàn bộ Dữ liệu mẫu (Seed Data) chuẩn thực tế Việt Nam:
- 1 Tài khoản Chủ trọ: admin / admin123
- 15 phòng chia đều làm 3 tầng (Tầng 1: 1.1 -> 1.5, Tầng 2: 2.1 -> 2.5, Tầng 3: 3.1 -> 3.5), mật khẩu mặc định: 123456
- 10 phòng đang có người thuê (đầy đủ Họ tên, Giới tính, Ngày sinh, CCCD, SĐT, Gmail, Quê quán, Hợp đồng pháp lý VN)
- 3 phòng đã đóng tiền tháng này (1.1: MOMO, 1.2: VISA, 2.1: BANK_TRANSFER)
- 2 phòng đang chờ chủ trọ duyệt ảnh Bill chuyển khoản UNC (1.3, 2.2)
- 3 phòng quá hạn sau ngày 15 chưa đóng tiền - bị đánh dấu đỏ Nợ tiền phòng tháng hiện tại (2026-11) và 1 tháng trước đó (2026-10) (1.4, 2.3, 3.1)
- 3 Feedback mẫu từ các phòng (trong đó có 2 Feedback mới ở trạng thái 'Cần đọc' nằm trên đầu danh sách)
- 1 hồ sơ khách thuê cũ vừa chuyển đi cách đây 10 ngày đang nằm trong mục Lưu trữ tạm (chờ đủ 30 ngày tự xóa)
"""

import base64
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base, SessionLocal, engine, ensure_database_exists
from app.core.init_db import init_db
from app.core.security import get_password_hash
from app.models import (
    ArchivedTenant,
    Contract,
    EmailLog,
    Feedback,
    Invoice,
    Notification,
    Room,
    User,
    UtilityReading,
)


def _make_sample_unc_svg_data_url(bank_name: str, room_num: str, sender_name: str, amount_str: str, tx_code: str) -> str:
    """Tạo ảnh chụp màn hình Bill chuyển khoản ngân hàng (UNC) sắc nét dưới dạng SVG Data URL."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="540" viewBox="0 0 420 540">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#0f766e"/>
          <stop offset="100%" stop-color="#0369a1"/>
        </linearGradient>
      </defs>
      <rect width="420" height="540" rx="20" fill="#f8fafc" stroke="#cbd5e1" stroke-width="2"/>
      <rect width="420" height="115" rx="20" fill="url(#bg)"/>
      <circle cx="210" cy="50" r="24" fill="#ffffff"/>
      <path d="M198 50 l8 8 l16 -16" stroke="#0f766e" stroke-width="4" fill="none" stroke-linecap="round"/>
      <text x="210" y="96" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#ffffff" text-anchor="middle">CHUYỂN KHOẢN THÀNH CÔNG</text>
      <text x="210" y="150" font-family="Arial, sans-serif" font-size="13" fill="#64748b" text-anchor="middle">{bank_name} - Biên lai Ủy nhiệm chi (UNC)</text>
      <text x="210" y="186" font-family="Arial, sans-serif" font-size="28" font-weight="bold" fill="#0f766e" text-anchor="middle">{amount_str} VNĐ</text>
      <line x1="30" y1="210" x2="390" y2="210" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="5,5"/>
      <g font-family="Arial, sans-serif" font-size="13">
        <text x="34" y="245" fill="#64748b">Người chuyển:</text>
        <text x="386" y="245" fill="#0f172a" font-weight="bold" text-anchor="end">{sender_name}</text>
        <text x="34" y="285" fill="#64748b">Tài khoản nhận:</text>
        <text x="386" y="285" fill="#0f172a" font-weight="bold" text-anchor="end">1029384756 (Vietcombank)</text>
        <text x="34" y="325" fill="#64748b">Chủ TK nhận:</text>
        <text x="386" y="325" fill="#0f172a" font-weight="bold" text-anchor="end">NGUYEN MINH HOANG</text>
        <text x="34" y="365" fill="#64748b">Nội dung CK:</text>
        <text x="386" y="365" fill="#0f766e" font-weight="bold" text-anchor="end">PHONG {room_num} TT 2026-11</text>
        <text x="34" y="405" fill="#64748b">Mã giao dịch:</text>
        <text x="386" y="405" fill="#0f172a" font-weight="bold" text-anchor="end">{tx_code}</text>
        <text x="34" y="445" fill="#64748b">Thời gian GD:</text>
        <text x="386" y="445" fill="#0f172a" text-anchor="end">08/11/2026 19:42:15</text>
      </g>
      <rect x="34" y="472" width="352" height="42" rx="10" fill="#f0fdfa" stroke="#99f6e4"/>
      <text x="210" y="498" font-family="Arial, sans-serif" font-size="12" fill="#0f766e" font-weight="bold" text-anchor="middle">✓ Đã xác thực chữ ký số Ngân hàng Điện tử</text>
    </svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


def seed_demo_data():
    print("=" * 78)
    print(" KHỞI TẠO DỮ LIỆU MẪU (SEED DATA) - HỆ THỐNG QUẢN LÝ NHÀ TRỌ & THANH TOÁN")
    print("=" * 78)

    ensure_database_exists()
    # Drop & recreate all tables so the demo seed state is 100% clean and exact
    Base.metadata.drop_all(bind=engine)
    init_db()

    db = SessionLocal()
    try:
        # 1. Chủ trọ: admin / admin123
        admin = db.query(User).filter(User.username == "admin").first()
        admin.full_name = "Nguyễn Minh Hoàng"
        admin.phone = "0901234567"
        admin.email = "admin@phongtro.vn"
        admin.cccd = "079085001234"
        admin.hometown = "Quận 5, TP. Hồ Chí Minh"
        admin.gender = "Nam"
        admin.birth_date = date(1985, 5, 15)
        admin.is_profile_completed = True
        db.commit()
        print(f"[1/7] Đã khởi tạo tài khoản Chủ trọ: admin / admin123 ({admin.full_name})")

        # 2. Khởi tạo 15 phòng chia đều làm 3 tầng (1.1 -> 3.5) & tài khoản tương ứng (mật khẩu 123456)
        print("[2/7] Khởi tạo 15 phòng trên 3 tầng (1.1 -> 3.5) kèm 15 tài khoản độc lập...")

        tenant_profiles = {
            "1.1": {
                "full_name": "Nguyễn Văn An",
                "gender": "Nam",
                "birth_date": date(1998, 3, 12),
                "phone": "0987111222",
                "email": "nguyenvanan.p11@gmail.com",
                "cccd": "038098001234",
                "hometown": "TP. Thanh Hóa, Tỉnh Thanh Hóa",
                "price": 2000000.0,
                "status": "RENTED",
            },
            "1.2": {
                "full_name": "Trần Thị Bích Ngọc",
                "gender": "Nữ",
                "birth_date": date(2000, 8, 24),
                "phone": "0912333444",
                "email": "bichngoc.p12@gmail.com",
                "cccd": "079300005678",
                "hometown": "TP. Vinh, Tỉnh Nghệ An",
                "price": 2000000.0,
                "status": "RENTED",
            },
            "1.3": {
                "full_name": "Lê Hoàng Nam",
                "gender": "Nam",
                "birth_date": date(1997, 11, 5),
                "phone": "0905555666",
                "email": "hoangnam.p13@gmail.com",
                "cccd": "048097009101",
                "hometown": "Quận Hải Châu, TP. Đà Nẵng",
                "price": 2200000.0,
                "status": "RENTED",
            },
            "1.4": {
                "full_name": "Phạm Minh Tuấn",
                "gender": "Nam",
                "birth_date": date(1999, 1, 19),
                "phone": "0978777888",
                "email": "minhtuan.p14@gmail.com",
                "cccd": "036099002345",
                "hometown": "Huyện Hải Hậu, Tỉnh Nam Định",
                "price": 2000000.0,
                "status": "RENTED",
            },
            "2.1": {
                "full_name": "Võ Thị Thanh Thảo",
                "gender": "Nữ",
                "birth_date": date(2001, 4, 30),
                "phone": "0939888999",
                "email": "thanhthao.p21@gmail.com",
                "cccd": "082301003456",
                "hometown": "TP. Mỹ Tho, Tỉnh Tiền Giang",
                "price": 2200000.0,
                "status": "RENTED",
            },
            "2.2": {
                "full_name": "Đặng Quốc Khánh",
                "gender": "Nam",
                "birth_date": date(1996, 9, 2),
                "phone": "0966123789",
                "email": "quockhanh.p22@gmail.com",
                "cccd": "075096004567",
                "hometown": "TP. Biên Hòa, Tỉnh Đồng Nai",
                "price": 2000000.0,
                "status": "RENTED",
            },
            "2.3": {
                "full_name": "Hoàng Thị Mai Hương",
                "gender": "Nữ",
                "birth_date": date(2002, 6, 15),
                "phone": "0944567123",
                "email": "maihuong.p23@gmail.com",
                "cccd": "040302005678",
                "hometown": "Huyện Hương Sơn, Tỉnh Hà Tĩnh",
                "price": 2000000.0,
                "status": "RENTED",
            },
            "3.1": {
                "full_name": "Bùi Tiến Dũng",
                "gender": "Nam",
                "birth_date": date(1995, 12, 10),
                "phone": "0983456789",
                "email": "tiendung.p31@gmail.com",
                "cccd": "034095006789",
                "hometown": "Huyện Đông Hưng, Tỉnh Thái Bình",
                "price": 2000000.0,
                "status": "RENTED",
            },
            "3.2": {
                "full_name": "Ngô Phương Linh",
                "gender": "Nữ",
                "birth_date": date(2001, 7, 8),
                "phone": "0918234567",
                "email": "phuonglinh.p32@gmail.com",
                "cccd": "001301007890",
                "hometown": "Quận Cầu Giấy, TP. Hà Nội",
                "price": 2300000.0,
                "status": "RENTED",
            },
            "3.3": {
                "full_name": "Trương Gia Huy",
                "gender": "Nam",
                "birth_date": date(2000, 2, 28),
                "phone": "0909345678",
                "email": "giahuy.p33@gmail.com",
                "cccd": "092200008901",
                "hometown": "Quận Ninh Kiều, TP. Cần Thơ",
                "price": 2000000.0,
                "status": "RENTED",
            },
        }

        rooms_map = {}
        users_map = {}
        default_pw_hash = get_password_hash("123456")

        for floor in range(1, 4):
            for seq in range(1, 6):
                r_num = f"{floor}.{seq}"
                prof = tenant_profiles.get(r_num)
                r_status = prof["status"] if prof else ("MAINTENANCE" if r_num == "2.5" else "AVAILABLE")
                r_price = prof["price"] if prof else 2000000.0
                r_desc = (
                    f"Phòng {r_num} (Tầng {floor}) khép kín, ban công thoáng mát, kệ bếp, WC riêng"
                    if r_status != "MAINTENANCE"
                    else f"Phòng {r_num} (Tầng {floor}) đang bảo trì máy lạnh và sơn mới"
                )

                room = Room(
                    room_number=r_num,
                    floor=floor,
                    room_seq=seq,
                    price=r_price,
                    area=22.0 if seq <= 3 else 24.0,
                    max_occupants=2,
                    status=r_status,
                    electricity_rate=3500.0,
                    water_rate=20000.0,
                    parking_fee=100000.0,
                    trash_fee=30000.0,
                    wifi_fee=50000.0,
                    maintenance_fee=20000.0,
                    description=r_desc,
                )
                db.add(room)
                db.commit()
                db.refresh(room)
                rooms_map[r_num] = room

                if prof:
                    user = User(
                        username=r_num,
                        password_hash=default_pw_hash,
                        full_name=prof["full_name"],
                        gender=prof["gender"],
                        birth_date=prof["birth_date"],
                        phone=prof["phone"],
                        email=prof["email"],
                        cccd=prof["cccd"],
                        hometown=prof["hometown"],
                        role="TENANT",
                        room_id=room.id,
                        is_profile_completed=True,
                        token_version=1,
                    )
                else:
                    user = User(
                        username=r_num,
                        password_hash=default_pw_hash,
                        full_name=f"Phòng {r_num} (Chưa khai báo hồ sơ)",
                        role="TENANT",
                        room_id=room.id,
                        is_profile_completed=False,
                        token_version=1,
                    )
                db.add(user)
                db.commit()
                db.refresh(user)
                users_map[r_num] = user

        # 3. Tạo 10 Hợp đồng thuê phòng chuẩn pháp luật Việt Nam cho 10 phòng đang thuê
        print("[3/7] Khởi tạo 10 Hợp đồng thuê trọ chuẩn pháp luật Việt Nam...")
        contracts_map = {}
        for r_num, prof in tenant_profiles.items():
            room = rooms_map[r_num]
            tenant = users_map[r_num]
            contract = Contract(
                contract_code=f"HD-{r_num}-2026",
                room_id=room.id,
                tenant_id=tenant.id,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                deposit_amount=room.price,
                monthly_rent=room.price,
                electricity_rate=3500.0,
                water_rate=20000.0,
                parking_fee=100000.0,
                trash_fee=30000.0,
                wifi_fee=50000.0,
                maintenance_fee=20000.0,
                service_fee=200000.0,
                payment_due_day=10,
                landlord_name="Nguyễn Minh Hoàng",
                landlord_cccd="079085001234",
                landlord_phone="0901234567",
                landlord_address="Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh",
                status="ACTIVE",
                notes=f"Hợp đồng thuê Phòng {r_num} thời hạn 12 tháng, đóng tiền ngày 10 hằng tháng.",
            )
            db.add(contract)
            db.commit()
            db.refresh(contract)
            contracts_map[r_num] = contract

        # 4. Khởi tạo Chỉ số điện nước & Hóa đơn theo đúng kịch bản:
        # - 3 phòng ĐÃ ĐÓNG TIỀN tháng này (2026-11): 1.1 (MOMO), 1.2 (VISA), 2.1 (BANK_TRANSFER)
        # - 2 phòng CHỜ DUYỆT BILL chuyển khoản (2026-11): 1.3, 2.2
        # - 3 phòng QUÁ HẠN SAU NGÀY 15 (OVERDUE - Nợ cả tháng 2026-10 và 2026-11): 1.4, 2.3, 3.1
        # - 2 phòng đang thuê còn lại (3.2, 3.3): 2026-10 đã đóng, 2026-11 chờ đóng (UNPAID)
        print("[4/7] Khởi tạo Chỉ số điện nước & Hóa đơn (Đủ kịch bản: Đã đóng, Chờ duyệt Bill, Nợ quá hạn sau ngày 15)...")

        def _create_reading_and_invoice(
            r_num: str,
            month_year: str,
            old_e: float,
            new_e: float,
            old_w: float,
            new_w: float,
            inv_status: str,
            payment_method: str = None,
            paid_date_val: date = None,
            tx_ref: str = None,
            bill_img: str = None,
            notes_val: str = None,
        ):
            room = rooms_map[r_num]
            tenant = users_map[r_num]
            contract = contracts_map[r_num]

            y_int, m_int = map(int, month_year.split("-"))
            issue_dt = date(y_int, m_int, 1)
            due_dt = date(y_int, m_int, 10)  # Hạn đóng cố định: Ngày 10 hằng tháng
            overdue_dt = date(y_int, m_int, 15)  # Sau 5 ngày kể từ hạn đóng: Ngày 15 hằng tháng

            reading = UtilityReading(
                room_id=room.id,
                month_year=month_year,
                recorded_date=issue_dt,
                old_electricity=old_e,
                new_electricity=new_e,
                old_water=old_w,
                new_water=new_w,
                recorded_by=admin.id,
            )
            db.add(reading)

            e_usage = new_e - old_e
            e_charge = e_usage * 3500.0
            w_usage = new_w - old_w
            w_charge = w_usage * 20000.0
            service_fee = 200000.0  # 100k gửi xe + 30k rác + 50k wifi + 20k bảo trì
            total = room.price + e_charge + w_charge + service_fee

            clean_m = month_year.replace("-", "")
            inv = Invoice(
                invoice_code=f"INV-{r_num}-{clean_m}",
                room_id=room.id,
                contract_id=contract.id,
                tenant_id=tenant.id,
                month_year=month_year,
                issue_date=issue_dt,
                due_date=due_dt,
                overdue_date=overdue_dt,
                room_charge=room.price,
                old_electricity=old_e,
                new_electricity=new_e,
                electricity_usage=e_usage,
                electricity_rate=3500.0,
                electricity_charge=e_charge,
                old_water=old_w,
                new_water=new_w,
                water_usage=w_usage,
                water_rate=20000.0,
                water_charge=w_charge,
                parking_fee=100000.0,
                trash_fee=30000.0,
                wifi_fee=50000.0,
                maintenance_fee=20000.0,
                service_charge=service_fee,
                other_charge=0.0,
                discount=0.0,
                total_amount=total,
                status=inv_status,
                paid_date=paid_date_val,
                paid_at=datetime.now(timezone.utc) if inv_status == "PAID" else None,
                payment_method=payment_method,
                transaction_ref=tx_ref,
                bill_image_url=bill_img,
                bill_uploaded_at=datetime.now(timezone.utc) if bill_img else None,
                is_reconciled=(inv_status == "PAID"),
                email_sent=(inv_status == "PAID"),
                email_sent_at=datetime.now(timezone.utc) if inv_status == "PAID" else None,
                notes=notes_val,
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)
            return inv

        # --- Kịch bản Nhóm 1: 3 phòng ĐÃ ĐÓNG TIỀN tháng này (1.1, 1.2, 2.1) ---
        _create_reading_and_invoice("1.1", "2026-10", 120, 200, 15, 19, "PAID", "MOMO", date(2026, 10, 6), "MOMO-20261006-11", notes_val="Đã thanh toán qua Ví MoMo")
        _create_reading_and_invoice("1.1", "2026-11", 200, 285, 19, 24, "PAID", "MOMO", date(2026, 11, 5), "MOMO-20261105-11", notes_val="Đã thanh toán online qua Ví MoMo")

        _create_reading_and_invoice("1.2", "2026-10", 90, 160, 10, 14, "PAID", "VISA", date(2026, 10, 7), "VISA-20261007-12", notes_val="Đã thanh toán qua Thẻ Quốc tế Visa")
        _create_reading_and_invoice("1.2", "2026-11", 160, 240, 14, 18, "PAID", "VISA", date(2026, 11, 6), "VISA-20261106-12", notes_val="Đã thanh toán online qua Thẻ Visa")

        _create_reading_and_invoice("2.1", "2026-10", 150, 230, 20, 25, "PAID", "BANK_TRANSFER", date(2026, 10, 8), "VCB-20261008-21", notes_val="Đã chuyển khoản VietQR")
        _create_reading_and_invoice("2.1", "2026-11", 230, 320, 25, 30, "PAID", "LINKED_BANK", date(2026, 11, 7), "BANK-20261107-21", notes_val="Đã thanh toán qua Ngân hàng liên kết")

        # --- Kịch bản Nhóm 2: 2 phòng CHỜ CHỦ TRỌ DUYỆT ẢNH BILL CHUYỂN KHOẢN (1.3, 2.2) ---
        _create_reading_and_invoice("1.3", "2026-10", 100, 175, 12, 16, "PAID", "BANK_TRANSFER", date(2026, 10, 9), "VCB-20261009-13")
        bill_svg_13 = _make_sample_unc_svg_data_url("Vietcombank DigiBank", "1.3", "LE HOANG NAM", "2.795.000", "VCB992837461")
        _create_reading_and_invoice(
            "1.3", "2026-11", 175, 265, 16, 20,
            "PENDING_APPROVAL", "BANK_TRANSFER",
            bill_img=bill_svg_13,
            notes_val="Khách thuê Lê Hoàng Nam đã tải lên ảnh chụp màn hình Bill chuyển khoản Vietcombank (Chờ chủ trọ duyệt)",
        )

        _create_reading_and_invoice("2.2", "2026-10", 80, 150, 10, 13, "PAID", "MOMO", date(2026, 10, 8), "MOMO-20261008-22")
        bill_svg_22 = _make_sample_unc_svg_data_url("MB Bank App", "2.2", "DANG QUOC KHANH", "2.540.000", "FT26312998877")
        _create_reading_and_invoice(
            "2.2", "2026-11", 150, 230, 13, 16,
            "PENDING_APPROVAL", "BANK_TRANSFER",
            bill_img=bill_svg_22,
            notes_val="Khách thuê Đặng Quốc Khánh đã tải lên ảnh Bill chuyển khoản MB Bank (Chờ chủ trọ duyệt)",
        )

        # --- Kịch bản Nhóm 3: 3 phòng QUÁ HẠN SAU NGÀY 15 - ĐANG NỢ 2 THÁNG (1.4, 2.3, 3.1) ---
        # Phòng 1.4: Nợ tháng 2026-10 và 2026-11
        _create_reading_and_invoice(
            "1.4", "2026-10", 210, 300, 18, 23,
            "OVERDUE",
            notes_val="Quá hạn sau ngày 15/10/2026 chưa thanh toán (Đang nợ tháng 10/2026)",
        )
        _create_reading_and_invoice(
            "1.4", "2026-11", 300, 390, 23, 28,
            "OVERDUE",
            notes_val="Quá hạn sau ngày 15/11/2026 chưa thanh toán (Đang nợ tháng 11/2026)",
        )

        # Phòng 2.3: Nợ tháng 2026-10 và 2026-11
        _create_reading_and_invoice(
            "2.3", "2026-10", 140, 220, 14, 18,
            "OVERDUE",
            notes_val="Quá hạn sau ngày 15/10/2026 chưa thanh toán (Đang nợ tháng 10/2026)",
        )
        _create_reading_and_invoice(
            "2.3", "2026-11", 220, 310, 18, 23,
            "OVERDUE",
            notes_val="Quá hạn sau ngày 15/11/2026 chưa thanh toán (Đang nợ tháng 11/2026)",
        )

        # Phòng 3.1: Nợ tháng 2026-10 và 2026-11
        _create_reading_and_invoice(
            "3.1", "2026-10", 110, 190, 11, 15,
            "OVERDUE",
            notes_val="Quá hạn sau ngày 15/10/2026 chưa thanh toán (Đang nợ tháng 10/2026)",
        )
        _create_reading_and_invoice(
            "3.1", "2026-11", 190, 270, 15, 19,
            "OVERDUE",
            notes_val="Quá hạn sau ngày 15/11/2026 chưa thanh toán (Đang nợ tháng 11/2026)",
        )

        # --- Kịch bản Nhóm 4: 2 phòng còn lại đang thuê (3.2, 3.3) ---
        _create_reading_and_invoice("3.2", "2026-10", 60, 130, 8, 12, "PAID", "MOMO", date(2026, 10, 9), "MOMO-20261009-32")
        # 3.2 và 3.3 kỳ 2026-11 đặt hạn đóng cuối tháng để ở trạng thái UNPAID (chờ thanh toán trong hạn)
        inv_32 = _create_reading_and_invoice("3.2", "2026-11", 130, 200, 12, 16, "UNPAID", notes_val="Hóa đơn tháng 11/2026 chờ thanh toán")
        inv_32.due_date = date.today() + timedelta(days=5)
        inv_32.overdue_date = date.today() + timedelta(days=10)

        inv_33 = _create_reading_and_invoice("3.3", "2026-11", 50, 110, 5, 8, "UNPAID", notes_val="Hóa đơn tháng 11/2026 chờ thanh toán")
        inv_33.due_date = date.today() + timedelta(days=5)
        inv_33.overdue_date = date.today() + timedelta(days=10)
        db.commit()

        # 5. Khởi tạo 3 Feedback mẫu (2 Feedback mới ở trạng thái 'Cần đọc' nằm trên đầu danh sách, 1 Feedback đã phản hồi)
        print("[5/7] Khởi tạo 3 Feedback mẫu (2 Feedback mới 'Cần đọc' đẩy lên đầu danh sách)...")
        now_utc = datetime.now(timezone.utc)

        fb_1 = Feedback(
            room_id=rooms_map["1.1"].id,
            tenant_id=users_map["1.1"].id,
            category="HYGIENE",
            title="Đề xuất đặt thêm thùng rác phân loại ở khu nhà xe tầng 1",
            content="Chào anh chủ trọ, khu vực để xe tầng 1 hiện có khá nhiều bưu phẩm và chai nhựa. Em góp ý đặt thêm 1 thùng rác phân loại ở góc sân để giữ vệ sinh chung ạ.",
            status="RESOLVED",
            is_read_by_admin=True,
            is_reply_read_by_tenant=True,
            admin_reply="Cảm ơn góp ý rất hữu ích của phòng 1.1! Anh đã trang bị thêm 2 thùng rác có nắp đậy ở góc nhà xe tầng 1 từ sáng nay rồi nhé.",
            replied_at=now_utc - timedelta(days=2),
            created_at=now_utc - timedelta(days=3),
        )
        fb_2 = Feedback(
            room_id=rooms_map["1.4"].id,
            tenant_id=users_map["1.4"].id,
            category="ELECTRIC_WATER",
            title="Báo hỏng vòi nước bồn rửa mặt bị rò rỉ nước",
            content="Anh Hoàng ơi, van khóa nước dưới bồn rửa mặt Phòng 1.4 bị rỉ nước từ tối qua làm ướt sàn nhà vệ sinh. Nhờ anh cho thợ kiểm tra thay gioăng giúp em với ạ.",
            status="UNREAD",
            is_read_by_admin=False,
            is_reply_read_by_tenant=True,
            created_at=now_utc - timedelta(hours=3),
        )
        fb_3 = Feedback(
            room_id=rooms_map["2.2"].id,
            tenant_id=users_map["2.2"].id,
            category="SECURITY",
            title="Đèn cảm biến hành lang tầng 2 bị chập chờn lúc tối muộn",
            content="Bóng đèn cảm biến ngay đầu cầu thang lên tầng 2 bị nhấp nháy liên tục vào ban đêm, mong chủ trọ kiểm tra sửa sớm để mọi người đi làm về muộn an toàn.",
            status="UNREAD",
            is_read_by_admin=False,
            is_reply_read_by_tenant=True,
            created_at=now_utc - timedelta(hours=1),
        )
        db.add_all([fb_1, fb_2, fb_3])
        db.commit()

        # 6. Khởi tạo 1 hồ sơ khách thuê cũ vừa chuyển đi cách đây 10 ngày đang nằm trong mục Lưu trữ tạm (chờ đủ 30 ngày tự xóa)
        print("[6/7] Khởi tạo 1 hồ sơ khách thuê cũ chuyển đi cách đây 10 ngày trong mục Lưu trữ tạm (30 ngày)...")
        deleted_10_days_ago = now_utc - timedelta(days=10)
        archived_tenant = ArchivedTenant(
            original_user_id=999,
            room_id=rooms_map["1.5"].id,
            room_number="1.5",
            username="1.5",
            full_name="Đỗ Văn Hùng",
            gender="Nam",
            birth_date=date(1997, 4, 18),
            phone="0933112233",
            email="dovanhung.old@gmail.com",
            cccd="031097009988",
            hometown="Quận Lê Chân, TP. Hải Phòng",
            contract_code="HD-1.5-2026-OLD",
            check_in_date=date(2025, 11, 1),
            check_out_date=(now_utc - timedelta(days=10)).date(),
            checkout_reason="Chuyển công tác về chi nhánh Hải Phòng, đã thanh lý hợp đồng & thu hồi phiên đăng nhập.",
            status="ARCHIVED",
            deleted_at=deleted_10_days_ago,
            expire_at=deleted_10_days_ago + timedelta(days=30),  # Còn đúng 20 ngày nữa sẽ tự xóa
        )
        db.add(archived_tenant)
        db.commit()

        # 7. Khởi tạo các Thông báo mẫu (Notification Bell & Toast) và Email Logs
        print("[7/7] Khởi tạo hệ thống Thông báo mẫu (Chuông thông báo) & Lịch sử Gmail...")
        sample_notifs = [
            Notification(
                recipient_role="LANDLORD",
                room_id=rooms_map["2.2"].id,
                title="Phòng 2.2 gửi Góp ý/Phản ánh mới [Cần đọc]",
                message="[SECURITY] Đèn cảm biến hành lang tầng 2 bị chập chờn lúc tối muộn.",
                type="FEEDBACK_NEW",
                related_id=fb_3.id,
                is_read=False,
            ),
            Notification(
                recipient_role="LANDLORD",
                room_id=rooms_map["1.4"].id,
                title="Phòng 1.4 gửi Góp ý/Phản ánh mới [Cần đọc]",
                message="[ELECTRIC_WATER] Báo hỏng vòi nước bồn rửa mặt bị rò rỉ nước.",
                type="FEEDBACK_NEW",
                related_id=fb_2.id,
                is_read=False,
            ),
            Notification(
                recipient_role="LANDLORD",
                room_id=rooms_map["1.3"].id,
                title="Phòng 1.3 vừa gửi ảnh Bill chuyển khoản (Chờ duyệt)",
                message="Khách thuê Lê Hoàng Nam (Phòng 1.3) đã tải lên ảnh UNC chuyển khoản Vietcombank 2.795.000đ.",
                type="BILL_UPLOADED",
                is_read=False,
            ),
            Notification(
                recipient_role="LANDLORD",
                room_id=rooms_map["2.2"].id,
                title="Phòng 2.2 vừa gửi ảnh Bill chuyển khoản (Chờ duyệt)",
                message="Khách thuê Đặng Quốc Khánh (Phòng 2.2) đã tải lên ảnh UNC chuyển khoản MB Bank 2.540.000đ.",
                type="BILL_UPLOADED",
                is_read=False,
            ),
            Notification(
                recipient_role="LANDLORD",
                room_id=rooms_map["1.4"].id,
                title="Cảnh báo Công nợ: 3 phòng quá hạn sau ngày 15",
                message="Các phòng 1.4, 2.3, 3.1 đang nợ quá hạn tiền phòng tháng 10/2026 và 11/2026.",
                type="OVERDUE_ALERT",
                is_read=False,
            ),
            # Thông báo cho các phòng khách thuê
            Notification(
                recipient_role="TENANT",
                recipient_user_id=users_map["1.4"].id,
                room_id=rooms_map["1.4"].id,
                title="Cảnh báo Quá hạn (Nợ) - Phòng 1.4",
                message="Phòng 1.4 hiện có 2 hóa đơn quá hạn sau ngày 15 (Tháng 10/2026 và 11/2026). Vui lòng vào mục 'Thanh toán nợ' để đóng tiền.",
                type="OVERDUE_ALERT",
                is_read=False,
            ),
            Notification(
                recipient_role="TENANT",
                recipient_user_id=users_map["1.1"].id,
                room_id=rooms_map["1.1"].id,
                title="Chủ trọ đã phản hồi góp ý của Phòng 1.1",
                message="Chủ trọ đã trang bị thêm 2 thùng rác phân loại ở góc nhà xe tầng 1.",
                type="FEEDBACK_REPLY",
                related_id=fb_1.id,
                is_read=False,
            ),
        ]
        db.add_all(sample_notifs)
        db.commit()

        print("\n" + "=" * 78)
        print(" HOÀN TẤT KHỞI TẠO DỮ LIỆU MẪU DEMO (15 PHÒNG - 3 TẦNG)")
        print("=" * 78)
        print("1. Tài khoản Chủ trọ (Admin):  admin / admin123")
        print("2. Tài khoản 15 Phòng (3 tầng): 1.1 -> 1.5, 2.1 -> 2.5, 3.1 -> 3.5 (Mật khẩu: 123456)")
        print("   - Đã đóng tiền tháng này (3 phòng):  1.1 (MoMo), 1.2 (Visa), 2.1 (Ngân hàng)")
        print("   - Chờ duyệt ảnh Bill UNC (2 phòng):  1.3, 2.2")
        print("   - Quá hạn sau ngày 15 / Nợ (3 phòng): 1.4, 2.3, 3.1 (Nợ cả tháng 10 & tháng 11)")
        print("   - Đang thuê chờ đóng trong hạn:      3.2, 3.3")
        print("   - Phòng trống / Bảo trì (5 phòng):   1.5, 2.4, 3.4, 3.5 (Trống), 2.5 (Bảo trì)")
        print("3. Feedback mẫu: 3 phản ánh (2 phản ánh 'Cần đọc' từ Phòng 1.4 & 2.2 nằm đầu danh sách)")
        print("4. Lưu trữ tạm 30 ngày: 1 hồ sơ khách cũ (Đỗ Văn Hùng - P.1.5, chuyển đi 10 ngày trước)")
        print("=" * 78)

    except Exception as e:
        db.rollback()
        print(f"[LỖI SEED DATA]: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
