"""
test_integration.py - Automated End-to-End Integration Test Suite.
Verifies the complete business workflow:
1. Tenant Registration (POST /api/auth/register)
2. Landlord Login & Authentication (POST /api/auth/login, GET /api/auth/me)
3. Room Management & Creation (POST /api/rooms, GET /api/rooms/{id})
4. Rental Contract Lifecycle (POST /api/contracts, GET /api/contracts/my-contract)
5. Utility Readings Recording (POST /api/utilities, GET /api/utilities/last-reading/{room_id})
6. Automatic Monthly Billing (POST /api/invoices/generate-monthly)
7. Full Bill Payment Rule (POST /api/invoices/{id}/pay - 100% full payment, no partial)
8. Dashboard & Revenue Analytics (GET /api/stats/dashboard, GET /api/stats/revenue)
9. Contract Termination & Room Status Release (PUT /api/contracts/{id}/terminate)
10. Role-Based Access Control & Security Guards (401 Unauthorized / 403 Forbidden checks)
"""

import os
import sys
import time
from datetime import date, timedelta
from typing import Dict, Any

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.core.init_db import init_db
from app.models.user import User
from app.models.room import Room
from app.models.contract import Contract
from app.models.invoice import Invoice
from app.models.utility_reading import UtilityReading

# Test client
client = TestClient(app)

# Global test state
test_results = []
start_time = time.time()


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def record_result(test_name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    color = Colors.OKGREEN if passed else Colors.FAIL
    test_results.append({"name": test_name, "passed": passed, "detail": detail})
    prefix = f"{color}[{status}]{Colors.ENDC}"
    print(f"  {prefix} {test_name}")
    if detail:
        print(f"         {Colors.OKCYAN}-> {detail}{Colors.ENDC}")
    if not passed:
        raise AssertionError(f"Test case failed: {test_name} - {detail}")


def run_tests():
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 75}")
    print(" BẮT ĐẦU CHẠY KIỂM THỬ TỰ ĐỘNG TOÀN DIỆN (END-TO-END INTEGRATION TEST)")
    print(" HỆ THỐNG QUẢN LÝ PHÒNG TRỌ - FASTAPI + MYSQL BACKEND")
    print(f"{'=' * 75}{Colors.ENDC}\n")

    # Step 0: Ensure DB is initialized
    print(f"{Colors.BOLD}[BƯỚC 0] Khởi tạo cơ sở dữ liệu và xác nhận bảng dữ liệu...{Colors.ENDC}")
    tables = init_db()
    record_result("Init DB Tables Check", len(tables) >= 5, f"Tables verified: {tables}")

    ts = int(time.time())
    test_tenant_username = f"tenant_test_{ts}"
    test_tenant_password = "Password123!"
    test_room_number = f"E2E-{ts % 10000}"

    landlord_token = None
    tenant_token = None
    created_tenant_id = None
    created_room_id = None
    created_contract_id = None
    created_invoice_id = None

    # Step 1: Healthcheck & Root
    print(f"\n{Colors.BOLD}[BƯỚC 1] Kiểm tra API Root & Trạng thái dịch vụ...{Colors.ENDC}")
    res = client.get("/")
    record_result(
        "API Root Endpoint GET /",
        res.status_code == 200 and res.json().get("status") == "online",
        f"Status: {res.status_code}, Response: {res.json().get('message')}",
    )

    # Step 2: Tenant Registration (POST /api/auth/register)
    print(f"\n{Colors.BOLD}[BƯỚC 2] Khách thuê đăng ký tài khoản mới (POST /api/auth/register)...{Colors.ENDC}")
    reg_payload = {
        "username": test_tenant_username,
        "password": test_tenant_password,
        "full_name": "Kiểm Thử Viên Tự Động",
        "phone": "0988776655",
        "email": f"{test_tenant_username}@example.com",
    }
    res = client.post("/api/auth/register", json=reg_payload)
    record_result(
        "Tenant Register Endpoint",
        res.status_code == 201,
        f"Created user: id={res.json().get('id')}, username={res.json().get('username')}, role={res.json().get('role')}",
    )
    tenant_data = res.json()
    created_tenant_id = tenant_data["id"]

    # Verify no password hash leaked in UserResponse
    record_result(
        "Password Hash Security Exclusion",
        "password" not in tenant_data and "password_hash" not in tenant_data,
        "Confirmed password_hash is not exposed in public UserResponse",
    )

    # Verify duplicate username rejected
    res_dup = client.post("/api/auth/register", json=reg_payload)
    record_result(
        "Duplicate Username Validation",
        res_dup.status_code == 400,
        f"Correctly rejected duplicate username with 400 Bad Request: '{res_dup.json().get('detail')}'",
    )

    # Step 3: Landlord Login & Authentication
    print(f"\n{Colors.BOLD}[BƯỚC 3] Chủ trọ đăng nhập & Lấy Bearer Token (POST /api/auth/login)...{Colors.ENDC}")
    login_payload = {
        "username": "admin",
        "password": "admin123",
    }
    res = client.post("/api/auth/login", json=login_payload)
    record_result(
        "Landlord Login Endpoint",
        res.status_code == 200 and "access_token" in res.json(),
        f"JWT token acquired, token_type: {res.json().get('token_type')}",
    )
    landlord_token = res.json()["access_token"]
    landlord_headers = {"Authorization": f"Bearer {landlord_token}"}

    # Verify landlord identity GET /api/auth/me
    res_me = client.get("/api/auth/me", headers=landlord_headers)
    record_result(
        "Landlord Profile Verification (GET /api/auth/me)",
        res_me.status_code == 200 and res_me.json().get("role") == "LANDLORD",
        f"Authenticated Landlord ID: {res_me.json().get('id')}, Role: {res_me.json().get('role')}",
    )

    # Step 4: Tenant Login
    print(f"\n{Colors.BOLD}[BƯỚC 4] Khách thuê đăng nhập & Xác thực quyền (POST /api/auth/login)...{Colors.ENDC}")
    res_t_login = client.post(
        "/api/auth/login",
        json={"username": test_tenant_username, "password": test_tenant_password},
    )
    record_result(
        "Tenant Login Endpoint",
        res_t_login.status_code == 200 and "access_token" in res_t_login.json(),
        f"Tenant token acquired: {res_t_login.json().get('user', {}).get('full_name')}",
    )
    tenant_token = res_t_login.json()["access_token"]
    tenant_headers = {"Authorization": f"Bearer {tenant_token}"}

    res_t_me = client.get("/api/auth/me", headers=tenant_headers)
    record_result(
        "Tenant Profile Verification (GET /api/auth/me)",
        res_t_me.status_code == 200 and res_t_me.json().get("role") == "TENANT",
        f"Authenticated Tenant ID: {res_t_me.json().get('id')}, Role: {res_t_me.json().get('role')}",
    )

    # Step 5: Room Creation (POST /api/rooms)
    print(f"\n{Colors.BOLD}[BƯỚC 5] Chủ trọ tạo phòng trọ mới (POST /api/rooms)...{Colors.ENDC}")
    room_payload = {
        "room_number": test_room_number,
        "price": 3200000.0,
        "area": 25.5,
        "max_occupants": 3,
        "status": "AVAILABLE",
        "description": "Phòng thử nghiệm tích hợp tự động E2E",
    }
    res_room = client.post("/api/rooms", json=room_payload, headers=landlord_headers)
    record_result(
        "Create Room (Landlord Only)",
        res_room.status_code == 201,
        f"Room ID: {res_room.json().get('id')}, Room Number: {res_room.json().get('room_number')}, Status: {res_room.json().get('status')}",
    )
    created_room_id = res_room.json()["id"]

    # Verify room is listed in GET /api/rooms
    res_get_room = client.get(f"/api/rooms/{created_room_id}")
    record_result(
        "Get Room Detail (GET /api/rooms/{id})",
        res_get_room.status_code == 200 and res_get_room.json().get("room_number") == test_room_number,
        f"Price: {res_get_room.json().get('price'):,.0f}đ, Area: {res_get_room.json().get('area')}m2",
    )

    # Step 6: Create Rental Contract (POST /api/contracts)
    print(f"\n{Colors.BOLD}[BƯỚC 6] Tạo hợp đồng thuê phòng (POST /api/contracts)...{Colors.ENDC}")
    contract_payload = {
        "room_id": created_room_id,
        "tenant_id": created_tenant_id,
        "start_date": "2026-03-01",
        "end_date": "2027-03-01",
        "deposit_amount": 3200000.0,
        "monthly_rent": 3200000.0,
        "electricity_rate": 3500.0,
        "water_rate": 20000.0,
        "service_fee": 50000.0,
        "notes": "Hợp đồng thử nghiệm E2E 12 tháng",
    }
    res_contract = client.post("/api/contracts", json=contract_payload, headers=landlord_headers)
    record_result(
        "Create Contract (Landlord Only)",
        res_contract.status_code == 201,
        f"Contract Code: {res_contract.json().get('contract_code')}, Status: {res_contract.json().get('status')}",
    )
    created_contract_id = res_contract.json()["id"]

    # Verify Room status transitioned from AVAILABLE to RENTED
    res_check_room = client.get(f"/api/rooms/{created_room_id}")
    record_result(
        "Room Status Transition to RENTED",
        res_check_room.json().get("status") == "RENTED",
        f"Room {test_room_number} current status: {res_check_room.json().get('status')}",
    )

    # Verify Tenant can view their contract (GET /api/contracts/my-contract)
    res_my_contract = client.get("/api/contracts/my-contract", headers=tenant_headers)
    record_result(
        "Tenant View Own Contract (GET /api/contracts/my-contract)",
        res_my_contract.status_code == 200 and res_my_contract.json().get("id") == created_contract_id,
        f"Contract Code retrieved by Tenant: {res_my_contract.json().get('contract_code')}",
    )

    # Step 7: Record Utility Reading (POST /api/utilities)
    print(f"\n{Colors.BOLD}[BƯỚC 7] Ghi nhận chỉ số điện nước tháng (POST /api/utilities)...{Colors.ENDC}")
    utility_payload = {
        "room_id": created_room_id,
        "month_year": "2026-03",
        "recorded_date": "2026-03-31",
        "old_electricity": 100.0,
        "new_electricity": 180.0,  # 80 kWh
        "old_water": 10.0,
        "new_water": 16.0,  # 6 m3
    }
    res_utility = client.post("/api/utilities", json=utility_payload, headers=landlord_headers)
    record_result(
        "Record Utility Reading (POST /api/utilities)",
        res_utility.status_code == 201,
        f"Reading ID: {res_utility.json().get('id')}, Month: {res_utility.json().get('month_year')}, Elec Usage: {res_utility.json().get('electricity_usage')} kWh, Water Usage: {res_utility.json().get('water_usage')} m3",
    )

    # Verify GET /api/utilities/last-reading/{room_id}
    res_last_reading = client.get(f"/api/utilities/last-reading/{created_room_id}", headers=landlord_headers)
    record_result(
        "Get Last Reading for Room (GET /api/utilities/last-reading/{room_id})",
        res_last_reading.status_code == 200 and res_last_reading.json().get("new_electricity") == 180.0,
        f"Confirmed last recorded electricity: {res_last_reading.json().get('new_electricity')} kWh",
    )

    # Step 8: Automatic Monthly Invoice Generation (POST /api/invoices/generate-monthly)
    print(f"\n{Colors.BOLD}[BƯỚC 8] Tự động lập hóa đơn tháng (POST /api/invoices/generate-monthly)...{Colors.ENDC}")
    gen_payload = {
        "month_year": "2026-03",
        "issue_date": "2026-04-01",
        "due_date": "2026-04-10",
    }
    res_gen = client.post("/api/invoices/generate-monthly", json=gen_payload, headers=landlord_headers)
    record_result(
        "Auto Generate Monthly Invoices",
        res_gen.status_code == 200 and isinstance(res_gen.json(), list),
        f"Generated/updated {len(res_gen.json())} invoices for active contracts",
    )

    # Locate our specific invoice
    target_invoice = None
    for inv in res_gen.json():
        if inv.get("room_id") == created_room_id and inv.get("month_year") == "2026-03":
            target_invoice = inv
            break

    record_result(
        "Invoice Found for Target Room",
        target_invoice is not None,
        f"Invoice Code: {target_invoice.get('invoice_code') if target_invoice else 'None'}",
    )

    created_invoice_id = target_invoice["id"]

    # Verify calculation accuracy:
    # Expected:
    # Rent: 3,200,000
    # Elec: 80 kWh * 3,500 = 280,000
    # Water: 6 m3 * 20,000 = 120,000
    # Service: 50,000
    # Total = 3,200,000 + 280,000 + 120,000 + 50,000 = 3,650,000
    expected_total = 3650000.0
    actual_total = float(target_invoice["total_amount"])
    record_result(
        "Invoice Calculation Accuracy (Room + Elec + Water + Service)",
        actual_total == expected_total and target_invoice["status"] == "UNPAID",
        f"Expected: {expected_total:,.0f}đ, Actual: {actual_total:,.0f}đ, Status: {target_invoice['status']}",
    )

    # Tenant checks my-invoices
    res_tenant_invs = client.get("/api/invoices/my-invoices", headers=tenant_headers)
    found_in_tenant = any(i["id"] == created_invoice_id for i in res_tenant_invs.json())
    record_result(
        "Tenant Retrieve Invoices (GET /api/invoices/my-invoices)",
        res_tenant_invs.status_code == 200 and found_in_tenant,
        f"Tenant can view unpaid invoice {target_invoice['invoice_code']}",
    )

    # Step 9: Full Bill Payment Rule (POST /api/invoices/{id}/pay)
    print(f"\n{Colors.BOLD}[BƯỚC 9] Thanh toán 100% đầy đủ hóa đơn (POST /api/invoices/{created_invoice_id}/pay)...{Colors.ENDC}")
    pay_payload = {
        "payment_method": "BANK_TRANSFER",
        "notes": "Khách thanh toán quét mã QR qua ứng dụng ngân hàng",
    }
    res_pay = client.post(
        f"/api/invoices/{created_invoice_id}/pay",
        json=pay_payload,
        headers=tenant_headers,
    )
    paid_inv = res_pay.json()
    record_result(
        "Full Invoice Payment (100% Full Payment Rule)",
        res_pay.status_code == 200 and paid_inv.get("status") == "PAID",
        f"Invoice {paid_inv.get('invoice_code')} status changed to: {paid_inv.get('status')}, Paid date: {paid_inv.get('paid_date')}",
    )

    # Verify duplicate payment rejection (cannot pay already paid bill)
    res_pay_again = client.post(
        f"/api/invoices/{created_invoice_id}/pay",
        json=pay_payload,
        headers=tenant_headers,
    )
    record_result(
        "Prevent Duplicate Payment on Already-Paid Bill",
        res_pay_again.status_code == 400,
        f"Correctly rejected with 400: '{res_pay_again.json().get('detail')}'",
    )

    # Step 10: Dashboard & Revenue Analytics
    print(f"\n{Colors.BOLD}[BƯỚC 10] Báo cáo Thống kê & Doanh thu (GET /api/stats/dashboard & /revenue)...{Colors.ENDC}")
    res_dash = client.get("/api/stats/dashboard", headers=landlord_headers)
    dash = res_dash.json()
    record_result(
        "Landlord Dashboard Stats (GET /api/stats/dashboard)",
        res_dash.status_code == 200
        and dash.get("total_rooms", 0) >= 1
        and dash.get("rented_rooms", 0) >= 1
        and dash.get("paid_invoices_count", 0) >= 1,
        f"Total Rooms: {dash.get('total_rooms')}, Rented: {dash.get('rented_rooms')}, Paid Bills: {dash.get('paid_invoices_count')}, Month Revenue: {dash.get('monthly_actual_revenue'):,.0f}đ",
    )

    res_rev = client.get("/api/stats/revenue", headers=landlord_headers)
    rev = res_rev.json()
    record_result(
        "Revenue Analytics & Monthly Breakdown (GET /api/stats/revenue)",
        res_rev.status_code == 200
        and rev.get("total_collected_revenue", 0) >= expected_total,
        f"Total Collected Revenue: {rev.get('total_collected_revenue'):,.0f}đ, Months tracked: {len(rev.get('monthly_breakdown', []))}",
    )

    # Step 11: Contract Termination & Room Status Release
    print(f"\n{Colors.BOLD}[BƯỚC 11] Thanh lý hợp đồng & Tự động trả phòng về AVAILABLE...{Colors.ENDC}")
    res_term = client.put(
        f"/api/contracts/{created_contract_id}/terminate",
        json={"notes": "Khách trả phòng theo kế hoạch kết thúc đợt test"},
        headers=landlord_headers,
    )
    record_result(
        "Terminate Contract (PUT /api/contracts/{id}/terminate)",
        res_term.status_code == 200 and res_term.json().get("status") == "TERMINATED",
        f"Contract status: {res_term.json().get('status')}",
    )

    # Verify room is released to AVAILABLE
    res_room_released = client.get(f"/api/rooms/{created_room_id}")
    record_result(
        "Room Automatically Released to AVAILABLE",
        res_room_released.json().get("status") == "AVAILABLE",
        f"Room {test_room_number} status after termination: {res_room_released.json().get('status')}",
    )

    # Step 12: Role-Based Access Control (RBAC) & Security Guard
    print(f"\n{Colors.BOLD}[BƯỚC 12] Kiểm thử Bảo mật & Phân quyền (RBAC)...{Colors.ENDC}")

    # Tenant forbidden from creating room
    res_rbac_room = client.post(
        "/api/rooms",
        json={"room_number": "HACK-999", "price": 1000000.0},
        headers=tenant_headers,
    )
    record_result(
        "RBAC: Tenant Forbidden to Create Room",
        res_rbac_room.status_code == 403,
        f"Response status: {res_rbac_room.status_code} (Detail: {res_rbac_room.json().get('detail')})",
    )

    # Tenant forbidden from viewing landlord revenue analytics
    res_rbac_rev = client.get("/api/stats/revenue", headers=tenant_headers)
    record_result(
        "RBAC: Tenant Forbidden to View Landlord Revenue",
        res_rbac_rev.status_code == 403,
        f"Response status: {res_rbac_rev.status_code} (Detail: {res_rbac_rev.json().get('detail')})",
    )

    # Unauthenticated request rejected
    res_unauth = client.get("/api/stats/dashboard")
    record_result(
        "Security: Unauthenticated Access Blocked",
        res_unauth.status_code == 401,
        f"Response status: {res_unauth.status_code} (Detail: {res_unauth.json().get('detail')})",
    )

    # Step 13: Clean up test artifacts from database
    print(f"\n{Colors.BOLD}[BƯỚC 13] Dọn dẹp dữ liệu kiểm thử tạm thời...{Colors.ENDC}")
    db = SessionLocal()
    try:
        # Delete any test invoices generated for test month (2026-03)
        db.query(Invoice).filter(Invoice.month_year == "2026-03").delete()
        if created_invoice_id:
            db.query(Invoice).filter(Invoice.id == created_invoice_id).delete()
        # Delete test readings
        if created_room_id:
            db.query(UtilityReading).filter(UtilityReading.room_id == created_room_id).delete()
        db.query(UtilityReading).filter(UtilityReading.month_year == "2026-03").delete()
        # Delete test contract
        if created_contract_id:
            db.query(Contract).filter(Contract.id == created_contract_id).delete()
        # Delete test room
        if created_room_id:
            db.query(Room).filter(Room.id == created_room_id).delete()
        # Delete test tenant
        if created_tenant_id:
            db.query(User).filter(User.id == created_tenant_id).delete()
        db.commit()
        record_result("Clean up Test Records", True, "Successfully cleaned up temporary test records")
    except Exception as e:
        db.rollback()
        record_result("Clean up Test Records", False, f"Clean up warning: {e}")
    finally:
        db.close()

    # Final summary
    total = len(test_results)
    passed = sum(1 for t in test_results if t["passed"])
    failed = total - passed
    elapsed = time.time() - start_time

    print(f"\n{Colors.BOLD}{'=' * 75}")
    print(f" KẾT QUẢ KIỂM THỬ: {passed}/{total} TEST CASES PASSED (100%) IN {elapsed:.2f}s")
    print(f"{'=' * 75}{Colors.ENDC}")

    if failed == 0:
        print(f"\n{Colors.BOLD}{Colors.OKGREEN}>>> TẤT CẢ CÁC BÀI KIỂM THỬ TÍCH HỢP ĐỀU ĐẠT CHUẨN 100%! <<<{Colors.ENDC}\n")
        return 0
    else:
        print(f"\n{Colors.BOLD}{Colors.FAIL}>>> CÓ {failed} BÀI KIỂM THỬ THẤT BẠI! <<<{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
