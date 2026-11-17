"""
seed_demo.py - Populates realistic sample data for university presentation demo.
Data created:
- 4 rooms (101: RENTED, 102: AVAILABLE, 201: AVAILABLE, 202: MAINTENANCE)
- 2 registered tenants (nguyenvana, tranthib)
- 1 active contract (Room 101 with Tenant 1)
- Utility readings (2 months: 2026-10 and 2026-11)
- 1 paid bill (2026-10: 2,910,000 VND, PAID via BANK_TRANSFER)
- 1 unpaid bill (2026-11: 2,965,000 VND, UNPAID, due 2026-11-30)
"""

import os
import sys
from datetime import date, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, engine, Base, ensure_database_exists
from app.core.init_db import init_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.room import Room
from app.models.contract import Contract
from app.models.utility_reading import UtilityReading
from app.models.invoice import Invoice


def seed_demo_data():
    print("=" * 70)
    print(" KHỞI TẠO DỮ LIỆU MẪU DEMO CHO BÁO CÁO ĐỒ ÁN / DEMO THUYẾT TRÌNH")
    print("=" * 70)

    # 1. Initialize DB tables and admin landlord
    print("\n[1/6] Kiểm tra cấu trúc CSDL và tài khoản Chủ trọ (Admin)...")
    init_db()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                full_name="Quản Trị Viên",
                phone="0901234567",
                email="admin@phongtro.vn",
                role="LANDLORD",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        print(f"  -> Chủ trọ: {admin.full_name} (username: {admin.username})")

        # 2. Seed 2 Registered Tenants
        print("\n[2/6] Khởi tạo 2 tài khoản Khách thuê (Tenants)...")
        tenants_data = [
            {
                "username": "nguyenvana",
                "password": "password123",
                "full_name": "Nguyễn Văn A",
                "phone": "0987654321",
                "email": "vana@gmail.com",
            },
            {
                "username": "tranthib",
                "password": "password123",
                "full_name": "Trần Thị B",
                "phone": "0912345678",
                "email": "thib@gmail.com",
            },
        ]

        tenant_users = {}
        for t_data in tenants_data:
            existing = db.query(User).filter(User.username == t_data["username"]).first()
            if existing:
                existing.full_name = t_data["full_name"]
                existing.phone = t_data["phone"]
                existing.email = t_data["email"]
                existing.role = "TENANT"
                tenant_users[t_data["username"]] = existing
                print(f"  -> Đã cập nhật khách thuê: {existing.full_name} ({existing.username})")
            else:
                new_t = User(
                    username=t_data["username"],
                    password_hash=get_password_hash(t_data["password"]),
                    full_name=t_data["full_name"],
                    phone=t_data["phone"],
                    email=t_data["email"],
                    role="TENANT",
                )
                db.add(new_t)
                db.commit()
                db.refresh(new_t)
                tenant_users[t_data["username"]] = new_t
                print(f"  -> Đã tạo mới khách thuê: {new_t.full_name} ({new_t.username})")

        # 3. Seed 4 Rooms
        print("\n[3/6] Khởi tạo 4 phòng trọ với trạng thái thực tế...")
        rooms_data = [
            {
                "room_number": "101",
                "price": 2500000.0,
                "area": 20.0,
                "max_occupants": 2,
                "status": "RENTED",
                "description": "Phòng tầng 1 khép kín, có gác lửng, ban công thoáng mát",
            },
            {
                "room_number": "102",
                "price": 2800000.0,
                "area": 22.0,
                "max_occupants": 2,
                "status": "AVAILABLE",
                "description": "Phòng tầng 1 đầy đủ nội thất: giường tủ, điều hòa, bình nóng lạnh",
            },
            {
                "room_number": "201",
                "price": 3200000.0,
                "area": 25.0,
                "max_occupants": 3,
                "status": "AVAILABLE",
                "description": "Phòng tầng 2 ban công hướng đông, cửa sổ lớn, máy lạnh inverter",
            },
            {
                "room_number": "202",
                "price": 2200000.0,
                "area": 18.0,
                "max_occupants": 2,
                "status": "MAINTENANCE",
                "description": "Phòng đang bảo trì thiết bị vệ sinh và sơn sửa lại tường",
            },
        ]

        rooms = {}
        for r_data in rooms_data:
            r = db.query(Room).filter(Room.room_number == r_data["room_number"]).first()
            if r:
                r.price = r_data["price"]
                r.area = r_data["area"]
                r.max_occupants = r_data["max_occupants"]
                r.status = r_data["status"]
                r.description = r_data["description"]
                rooms[r_data["room_number"]] = r
                print(f"  -> Đã cập nhật Phòng {r.room_number}: {r.price:,.0f}đ/tháng [{r.status}]")
            else:
                r = Room(**r_data)
                db.add(r)
                db.commit()
                db.refresh(r)
                rooms[r_data["room_number"]] = r
                print(f"  -> Đã tạo mới Phòng {r.room_number}: {r.price:,.0f}đ/tháng [{r.status}]")

        db.commit()

        # 4. Seed 1 Active Contract (Room 101 + Tenant 1)
        print("\n[4/6] Khởi tạo 1 hợp đồng thuê phòng hiệu lực (Phòng 101 - Nguyễn Văn A)...")
        room_101 = rooms["101"]
        tenant_1 = tenant_users["nguyenvana"]

        contract = (
            db.query(Contract)
            .filter(
                Contract.room_id == room_101.id,
                Contract.tenant_id == tenant_1.id,
                Contract.status == "ACTIVE",
            )
            .first()
        )

        if not contract:
            contract_code = "HD-101-2026-DEMO"
            old_c = db.query(Contract).filter(Contract.contract_code == contract_code).first()
            if old_c:
                contract = old_c
                contract.status = "ACTIVE"
                contract.monthly_rent = 2500000.0
                contract.deposit_amount = 2500000.0
                contract.electricity_rate = 3500.0
                contract.water_rate = 20000.0
                contract.service_fee = 50000.0
            else:
                contract = Contract(
                    contract_code=contract_code,
                    room_id=room_101.id,
                    tenant_id=tenant_1.id,
                    start_date=date(2026, 1, 1),
                    end_date=date(2027, 1, 1),
                    deposit_amount=2500000.0,
                    monthly_rent=2500000.0,
                    electricity_rate=3500.0,
                    water_rate=20000.0,
                    service_fee=50000.0,
                    status="ACTIVE",
                    notes="Hợp đồng mẫu demo: Thời hạn 1 năm, cọc 1 tháng tiền phòng",
                )
                db.add(contract)
                db.commit()
                db.refresh(contract)

            # Ensure room status is RENTED
            room_101.status = "RENTED"
            db.commit()

        print(f"  -> Hợp đồng mã: {contract.contract_code} | Phòng {room_101.room_number} | Khách: {tenant_1.full_name} | Giá thuê: {contract.monthly_rent:,.0f}đ/tháng")

        # 5. Clean up old extraneous invoices & readings for room_101 to ensure exact counts
        db.query(Invoice).filter(Invoice.room_id == room_101.id).delete()
        db.query(UtilityReading).filter(UtilityReading.room_id == room_101.id).delete()
        db.commit()

        # Seed Utility Readings (2 months for Room 101: 2026-10 and 2026-11)
        print("\n[5/6] Khởi tạo các bản ghi chỉ số điện nước...")
        readings_data = [
            {
                "room_id": room_101.id,
                "month_year": "2026-10",
                "recorded_date": date(2026, 10, 31),
                "old_electricity": 100.0,
                "new_electricity": 180.0,  # 80 kWh
                "old_water": 10.0,
                "new_water": 14.0,  # 4 m3
                "recorded_by": admin.id,
            },
            {
                "room_id": room_101.id,
                "month_year": "2026-11",
                "recorded_date": date(2026, 11, 15),
                "old_electricity": 180.0,
                "new_electricity": 270.0,  # 90 kWh
                "old_water": 14.0,
                "new_water": 19.0,  # 5 m3
                "recorded_by": admin.id,
            },
        ]

        for rd in readings_data:
            new_rd = UtilityReading(**rd)
            db.add(new_rd)
            print(f"  -> Đã ghi chỉ số {rd['month_year']} Phòng 101: Điện {(rd['new_electricity'] - rd['old_electricity']):.0f} kWh, Nước {(rd['new_water'] - rd['old_water']):.0f} m3")

        db.commit()

        # 6. Seed Invoices (1 PAID bill for 2026-10, 1 UNPAID bill for 2026-11)
        print("\n[6/6] Khởi tạo hóa đơn: 1 hóa đơn ĐÃ THANH TOÁN (tháng 10/2026) và 1 hóa đơn CHƯA THANH TOÁN (tháng 11/2026)...")

        # Invoice 1: 2026-10 (PAID)
        # Room: 2,500,000 | Elec: 80 * 3,500 = 280,000 | Water: 4 * 20,000 = 80,000 | Service: 50,000 | Total: 2,910,000
        inv_01 = Invoice(
            invoice_code="INV-101-202610",
            room_id=room_101.id,
            contract_id=contract.id,
            tenant_id=tenant_1.id,
            month_year="2026-10",
            issue_date=date(2026, 11, 1),
            due_date=date(2026, 11, 10),
            room_charge=2500000.0,
            electricity_usage=80.0,
            electricity_rate=3500.0,
            electricity_charge=280000.0,
            water_usage=4.0,
            water_rate=20000.0,
            water_charge=80000.0,
            service_charge=50000.0,
            other_charge=0.0,
            discount=0.0,
            total_amount=2910000.0,
            status="PAID",
            paid_date=date(2026, 11, 5),
            payment_method="BANK_TRANSFER",
            notes="Đã thanh toán đủ 100% qua chuyển khoản ngân hàng Vietcombank",
        )
        db.add(inv_01)

        # Invoice 2: 2026-11 (UNPAID) - Due date set in future (2026-11-30) so status remains UNPAID
        # Room: 2,500,000 | Elec: 90 * 3,500 = 315,000 | Water: 5 * 20,000 = 100,000 | Service: 50,000 | Total: 2,965,000
        inv_02 = Invoice(
            invoice_code="INV-101-202611",
            room_id=room_101.id,
            contract_id=contract.id,
            tenant_id=tenant_1.id,
            month_year="2026-11",
            issue_date=date(2026, 11, 15),
            due_date=date(2026, 11, 30),
            room_charge=2500000.0,
            electricity_usage=90.0,
            electricity_rate=3500.0,
            electricity_charge=315000.0,
            water_usage=5.0,
            water_rate=20000.0,
            water_charge=100000.0,
            service_charge=50000.0,
            other_charge=0.0,
            discount=0.0,
            total_amount=2965000.0,
            status="UNPAID",
            paid_date=None,
            payment_method=None,
            notes="Hóa đơn tiền phòng & điện nước tháng 11/2026 (Chờ thanh toán)",
        )
        db.add(inv_02)
        db.commit()

        print(f"  -> Hóa đơn 1 ({inv_01.month_year}): {inv_01.invoice_code} | Tổng: {inv_01.total_amount:,.0f}đ | Trạng thái: [{inv_01.status}] (Phương thức: {inv_01.payment_method})")
        print(f"  -> Hóa đơn 2 ({inv_02.month_year}): {inv_02.invoice_code} | Tổng: {inv_02.total_amount:,.0f}đ | Trạng thái: [{inv_02.status}] (Hạn thanh toán: {inv_02.due_date})")

        print("\n" + "=" * 70)
        print(" TỔNG HỢP DỮ LIỆU MẪU ĐÃ KHỞI TẠO THÀNH CÔNG")
        print("=" * 70)
        print("1. Tài khoản Chủ trọ:")
        print("   - Username: admin / Mật khẩu: admin123")
        print("2. Tài khoản Khách thuê:")
        print("   - Khách 1: nguyenvana / Mật khẩu: password123 (Đang thuê P101)")
        print("   - Khách 2: tranthib   / Mật khẩu: password123 (Chưa có phòng)")
        print("3. Danh sách phòng (4 phòng):")
        print("   - P101: 2,500,000đ | [RENTED]       (Nguyễn Văn A thuê)")
        print("   - P102: 2,800,000đ | [AVAILABLE]    (Phòng trống sẵn sàng)")
        print("   - P201: 3,200,000đ | [AVAILABLE]    (Phòng trống sẵn sàng)")
        print("   - P202: 2,200,000đ | [MAINTENANCE]  (Đang sửa chữa bảo trì)")
        print("4. Hợp đồng đang hiệu lực:")
        print(f"   - Mã {contract.contract_code}: P101 - Nguyễn Văn A (01/01/2026 -> 01/01/2027)")
        print("5. Chỉ số điện nước (Phòng 101):")
        print("   - Tháng 10/2026: Điện 80 kWh, Nước 4 m3")
        print("   - Tháng 11/2026: Điện 90 kWh, Nước 5 m3")
        print("6. Hóa đơn (Invoices):")
        print(f"   - {inv_01.invoice_code}: 2,910,000đ -> [PAID] (Đã thanh toán)")
        print(f"   - {inv_02.invoice_code}: 2,965,000đ -> [UNPAID] (Chưa thanh toán)")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n[LỖI] Có lỗi xảy ra trong quá trình seed dữ liệu: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
