import io
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.contract import Contract
from app.models.email_log import EmailLog
from app.models.invoice import Invoice

# Register Vietnamese Unicode TrueType Fonts (Times New Roman / Arial on Windows, fallback to Helvetica)
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

_FONT_REGISTERED = False


def _ensure_fonts():
    global FONT_REGULAR, FONT_BOLD, FONT_ITALIC, _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    try:
        times_reg = "C:/Windows/Fonts/times.ttf"
        times_bold = "C:/Windows/Fonts/timesbd.ttf"
        times_italic = "C:/Windows/Fonts/timesi.ttf"
        arial_reg = "C:/Windows/Fonts/arial.ttf"
        arial_bold = "C:/Windows/Fonts/arialbd.ttf"

        if os.path.exists(times_reg) and os.path.exists(times_bold):
            pdfmetrics.registerFont(TTFont("VN-Regular", times_reg))
            pdfmetrics.registerFont(TTFont("VN-Bold", times_bold))
            if os.path.exists(times_italic):
                pdfmetrics.registerFont(TTFont("VN-Italic", times_italic))
            else:
                pdfmetrics.registerFont(TTFont("VN-Italic", times_reg))
            FONT_REGULAR = "VN-Regular"
            FONT_BOLD = "VN-Bold"
            FONT_ITALIC = "VN-Italic"
        elif os.path.exists(arial_reg) and os.path.exists(arial_bold):
            pdfmetrics.registerFont(TTFont("VN-Regular", arial_reg))
            pdfmetrics.registerFont(TTFont("VN-Bold", arial_bold))
            FONT_REGULAR = "VN-Regular"
            FONT_BOLD = "VN-Bold"
            FONT_ITALIC = "VN-Regular"
    except Exception:
        pass
    _FONT_REGISTERED = True


def _fmt_vnd(amount: Optional[float]) -> str:
    val = float(amount or 0.0)
    return f"{val:,.0f} VNĐ".replace(",", ".")


def generate_contract_pdf(contract: Contract) -> bytes:
    """
    Xuất file PDF Hợp đồng thuê nhà trọ chuẩn pháp luật Việt Nam:
    - Quốc hiệu, Tiêu ngữ
    - Căn cứ Bộ luật Dân sự 2015 & Luật Nhà ở 2023
    - Thông tin Bên A (Chủ trọ) & Bên B (Khách thuê)
    - Chi tiết phòng, giá thuê, tiền cọc, điện, nước, phụ phí cố định, ngày đóng tiền (ngày 10 hằng tháng)
    - Quyền & nghĩa vụ hai bên, chữ ký
    """
    _ensure_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Hop-Dong-Thue-Tro-{contract.contract_code}",
    )

    styles = getSampleStyleSheet()
    style_center_bold = ParagraphStyle(
        "CenterBold",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
    )
    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=15,
        leading=20,
        alignment=TA_CENTER,
        spaceBefore=8,
        spaceAfter=4,
    )
    style_sub = ParagraphStyle(
        "SubTitle",
        parent=styles["Normal"],
        fontName=FONT_ITALIC,
        fontSize=10.5,
        leading=14,
        alignment=TA_CENTER,
    )
    style_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=11.5,
        leading=16,
        spaceBefore=8,
        spaceAfter=4,
    )
    style_body = ParagraphStyle(
        "BodyVN",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=3,
    )
    style_italic = ParagraphStyle(
        "ItalicVN",
        parent=styles["Normal"],
        fontName=FONT_ITALIC,
        fontSize=10.5,
        leading=15,
        spaceAfter=2,
    )

    room = contract.room
    tenant = contract.tenant
    room_num = room.room_number if room else str(contract.room_id)
    floor_num = room.floor if room else 1
    area_val = room.area if (room and room.area) else 22.0

    tenant_name = tenant.full_name if tenant else "........................................"
    tenant_cccd = (tenant.cccd if tenant and tenant.cccd else "........................")
    tenant_phone = (tenant.phone if tenant and tenant.phone else "........................")
    tenant_email = (tenant.email if tenant and tenant.email else "........................")
    tenant_hometown = (tenant.hometown if tenant and tenant.hometown else "................................................")
    tenant_gender = (tenant.gender if tenant and tenant.gender else "Nam/Nữ")
    tenant_dob = tenant.birth_date.strftime("%d/%m/%Y") if (tenant and tenant.birth_date) else "../../...."

    story = []

    # Quốc hiệu & Tiêu ngữ
    story.append(Paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", style_center_bold))
    story.append(Paragraph("Độc lập - Tự do - Hạnh phúc", style_center_bold))
    story.append(Paragraph("--------------------o0o--------------------", style_sub))
    story.append(Spacer(1, 4 * mm))

    # Tên hợp đồng
    story.append(Paragraph("HỢP ĐỒNG THUÊ PHÒNG TRỌ", style_title))
    story.append(Paragraph(f"Số hợp đồng: <b>{contract.contract_code}</b>", style_sub))
    story.append(Spacer(1, 4 * mm))

    # Căn cứ pháp lý
    story.append(Paragraph("- Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24/11/2015 của Quốc hội nước CHXHCN Việt Nam;", style_italic))
    story.append(Paragraph("- Căn cứ Luật Nhà ở số 27/2023/QH15 và các văn bản hướng dẫn thi hành;", style_italic))
    story.append(Paragraph("- Căn cứ vào nhu cầu thực tế và sự thỏa thuận tự nguyện của hai bên.", style_italic))
    story.append(Spacer(1, 2 * mm))

    today_str = contract.start_date.strftime("ngày %d tháng %m năm %Y") if contract.start_date else "ngày ... tháng ... năm 2026"
    story.append(Paragraph(f"Hôm nay, {today_str}, tại địa chỉ: {contract.landlord_address}, chúng tôi gồm có:", style_body))

    # BÊN A
    story.append(Paragraph("I. BÊN CHO THUÊ PHÒNG TRỌ (Gọi tắt là Bên A - Chủ trọ):", style_heading))
    story.append(Paragraph(f"- Họ và tên: <b>{contract.landlord_name}</b>", style_body))
    story.append(Paragraph(f"- Số CCCD/CMND: <b>{contract.landlord_cccd}</b> &nbsp;&nbsp;&nbsp;&nbsp; Số điện thoại: <b>{contract.landlord_phone}</b>", style_body))
    story.append(Paragraph(f"- Địa chỉ thường trú / Tòa nhà: {contract.landlord_address}", style_body))

    # BÊN B
    story.append(Paragraph("II. BÊN THUÊ PHÒNG TRỌ (Gọi tắt là Bên B - Khách thuê):", style_heading))
    story.append(Paragraph(f"- Họ và tên: <b>{tenant_name}</b> &nbsp;&nbsp;&nbsp;&nbsp; Giới tính: {tenant_gender} &nbsp;&nbsp;&nbsp;&nbsp; Ngày sinh: {tenant_dob}", style_body))
    story.append(Paragraph(f"- Số CCCD/Định danh: <b>{tenant_cccd}</b> &nbsp;&nbsp;&nbsp;&nbsp; Số điện thoại: <b>{tenant_phone}</b>", style_body))
    story.append(Paragraph(f"- Địa chỉ Email (Gmail): {tenant_email}", style_body))
    story.append(Paragraph(f"- Quê quán / Thường trú: {tenant_hometown}", style_body))

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Sau khi bàn bạc, hai bên thống nhất ký kết Hợp đồng thuê phòng trọ với các điều khoản sau:", style_body))

    # ĐIỀU 1
    story.append(Paragraph("ĐIỀU 1: ĐỐI TƯỢNG VÀ THỜI HẠN CHO THUÊ", style_heading))
    story.append(Paragraph(
        f"1.1. Bên A đồng ý cho Bên B thuê phòng trọ số: <b>Phòng {room_num} (Tầng {floor_num})</b>, diện tích sử dụng: <b>{area_val:.1f} m²</b> tại địa chỉ {contract.landlord_address} để sử dụng làm nơi ở sinh hoạt hợp pháp.",
        style_body,
    ))
    story.append(Paragraph(
        f"1.2. Thời hạn thuê: Từ ngày <b>{contract.start_date.strftime('%d/%m/%Y')}</b> đến ngày <b>{contract.end_date.strftime('%d/%m/%Y')}</b>.",
        style_body,
    ))

    # ĐIỀU 2
    story.append(Paragraph("ĐIỀU 2: GIÁ THUÊ PHÒNG, ĐƠN GIÁ ĐIỆN NƯỚC, PHỤ PHÍ VÀ HẠN THANH TOÁN", style_heading))
    story.append(Paragraph(f"2.1. Giá thuê phòng cơ bản: <b>{_fmt_vnd(contract.monthly_rent)}/tháng</b>.", style_body))
    story.append(Paragraph(f"2.2. Tiền đặt cọc giữ phòng: <b>{_fmt_vnd(contract.deposit_amount)}</b> (Hoàn trả khi kết thúc hợp đồng và thanh toán hết công nợ).", style_body))
    story.append(Paragraph(f"2.3. Đơn giá điện sinh hoạt: <b>{_fmt_vnd(contract.electricity_rate)}/kWh</b> (Tính theo chỉ số công tơ điện riêng của phòng: Chỉ số mới - Chỉ số cũ).", style_body))
    story.append(Paragraph(f"2.4. Đơn giá nước sinh hoạt: <b>{_fmt_vnd(contract.water_rate)}/m³</b> (Tính theo đồng hồ nước của phòng: Chỉ số mới - Chỉ số cũ).", style_body))
    story.append(Paragraph(
        f"2.5. Phụ phí dịch vụ cố định hằng tháng: Tiền gửi xe: <b>{_fmt_vnd(contract.parking_fee)}</b>; "
        f"Tiền Wifi: <b>{_fmt_vnd(contract.wifi_fee)}</b>; Tiền rác/vệ sinh: <b>{_fmt_vnd(contract.trash_fee)}</b>; "
        f"Tiền bảo trì điện nước: <b>{_fmt_vnd(contract.maintenance_fee)}</b>. "
        f"Tổng phụ phí cố định: <b>{_fmt_vnd(contract.service_fee)}/tháng</b>.",
        style_body,
    ))
    story.append(Paragraph(
        f"2.6. Hạn thanh toán cố định: Bên B có trách nhiệm thanh toán đầy đủ 100% tiền thuê phòng và các khoản phí trước hoặc vào <b>Ngày {contract.payment_due_day:02d} hằng tháng</b> bằng hình thức Chuyển khoản ngân hàng (VietQR) hoặc Cổng thanh toán trực tuyến. Quá 05 ngày kể từ hạn đóng (tức từ <b>Ngày 15 hằng tháng</b>), nếu chưa thanh toán sẽ bị tính vào danh sách <b>Quá hạn (Nợ)</b>.",
        style_body,
    ))

    # ĐIỀU 3
    story.append(Paragraph("ĐIỀU 3: QUYỀN VÀ NGHĨA VỤ CỦA BÊN A (CHỦ TRỌ)", style_heading))
    story.append(Paragraph("- Bàn giao phòng trọ và trang thiết bị điện, nước hoạt động tốt cho Bên B đúng thời hạn.", style_body))
    story.append(Paragraph("- Đảm bảo quyền sử dụng phòng trọ độc lập, an toàn, bảo mật thông tin cá nhân của Bên B.", style_body))
    story.append(Paragraph("- Ghi chỉ số điện nước minh bạch, phát hành hóa đơn chi tiết hằng tháng và gửi về tài khoản/Gmail của Bên B.", style_body))
    story.append(Paragraph("- Tiếp nhận và xử lý kịp thời các phản ánh (Feedback) về điện nước, an ninh, vệ sinh từ Bên B.", style_body))

    # ĐIỀU 4
    story.append(Paragraph("ĐIỀU 4: QUYỀN VÀ NGHĨA VỤ CỦA BÊN B (KHÁCH THUÊ)", style_heading))
    story.append(Paragraph("- Khai báo đầy đủ, trung thực thông tin nhân thân (CCCD, Quê quán, SĐT) để phục vụ đăng ký tạm trú theo quy định pháp luật Việt Nam.", style_body))
    story.append(Paragraph("- Thanh toán đúng hạn vào ngày 10 hằng tháng; giữ gìn vệ sinh chung, phòng cháy chữa cháy, an ninh trật tự khu nhà trọ.", style_body))
    story.append(Paragraph("- Không tự ý sang nhượng phòng, không tàng trữ chất cấm hoặc tổ chức hoạt động vi phạm pháp luật.", style_body))
    story.append(Paragraph("- Khi chấm dứt hợp đồng chuyển đi, bàn giao lại phòng và thanh toán dứt điểm các khoản công nợ tồn đọng.", style_body))

    # ĐIỀU 5
    story.append(Paragraph("ĐIỀU 5: CAM KẾT CHUNG", style_heading))
    story.append(Paragraph(
        "Hai bên cam kết thực hiện đúng các điều khoản đã ghi trong hợp đồng. Hợp đồng được lập thành 02 bản có giá trị pháp lý như nhau, mỗi bên giữ 01 bản và được lưu trữ điện tử trên Hệ thống Quản lý Nhà trọ.",
        style_body,
    ))
    story.append(Spacer(1, 8 * mm))

    # Chữ ký 2 bên
    sig_data = [
        [
            Paragraph("<b>ĐẠI DIỆN BÊN A (CHỦ TRỌ)</b><br/><i>(Ký và ghi rõ họ tên)</i>", style_center_bold),
            Paragraph("<b>ĐẠI DIỆN BÊN B (KHÁCH THUÊ)</b><br/><i>(Ký và ghi rõ họ tên)</i>", style_center_bold),
        ],
        [Spacer(1, 20 * mm), Spacer(1, 20 * mm)],
        [
            Paragraph(f"<b>{contract.landlord_name}</b>", style_center_bold),
            Paragraph(f"<b>{tenant_name}</b>", style_center_bold),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[85 * mm, 85 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Xuất Hóa đơn / Biên lai Tiền phòng Trọ chuẩn Việt Nam (PDF).
    Tách mục rõ ràng: Tiền phòng, Tiền điện, Tiền nước, Tiền gửi xe, Tiền bảo trì điện nước, Wifi, Rác.
    """
    _ensure_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Hoa-Don-{invoice.invoice_code}",
    )

    styles = getSampleStyleSheet()
    style_header = ParagraphStyle(
        "HeaderVN",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=15,
        leading=20,
        alignment=TA_CENTER,
    )
    style_sub = ParagraphStyle(
        "SubVN",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=10.5,
        leading=15,
        alignment=TA_CENTER,
    )
    style_body = ParagraphStyle(
        "BodyInv",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=10.5,
        leading=15,
    )
    style_bold = ParagraphStyle(
        "BoldInv",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=10.5,
        leading=15,
    )
    style_right = ParagraphStyle(
        "RightInv",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=10.5,
        leading=15,
        alignment=TA_RIGHT,
    )
    style_right_bold = ParagraphStyle(
        "RightBoldInv",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=11,
        leading=15,
        alignment=TA_RIGHT,
    )

    room = invoice.room
    tenant = invoice.tenant
    room_num = room.room_number if room else str(invoice.room_id)
    floor_num = room.floor if room else 1
    tenant_name = tenant.full_name if tenant else "Khách thuê phòng"
    tenant_phone = tenant.phone if (tenant and tenant.phone) else "—"
    tenant_email = tenant.email if (tenant and tenant.email) else "—"

    status_map = {
        "PAID": "ĐÃ THANH TOÁN (PAID)",
        "UNPAID": "CHỜ THANH TOÁN (UNPAID)",
        "PENDING_APPROVAL": "CHỜ DUYỆT BILL CHUYỂN KHOẢN",
        "OVERDUE": "QUÁ HẠN THANH TOÁN - ĐANG NỢ (OVERDUE)",
    }
    status_label = status_map.get(invoice.status, invoice.status)

    story = []
    story.append(Paragraph("HỆ THỐNG NHÀ TRỌ MINH HOÀNG - TP. HỒ CHÍ MINH", style_sub))
    story.append(Paragraph("Địa chỉ: Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh | Hotline: 0901.234.567", style_sub))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"HÓA ĐƠN TIỀN THUÊ PHÒNG & DỊCH VỤ KỲ {invoice.month_year}", style_header))
    story.append(Paragraph(f"Mã hóa đơn: <b>{invoice.invoice_code}</b> | Trạng thái: <b>{status_label}</b>", style_sub))
    story.append(Spacer(1, 5 * mm))

    info_data = [
        [
            Paragraph(f"<b>Phòng:</b> Phòng {room_num} (Tầng {floor_num})", style_body),
            Paragraph(f"<b>Ngày lập hóa đơn:</b> {invoice.issue_date.strftime('%d/%m/%Y')}", style_body),
        ],
        [
            Paragraph(f"<b>Khách thuê:</b> {tenant_name}", style_body),
            Paragraph(f"<b>Hạn thanh toán cố định:</b> {invoice.due_date.strftime('%d/%m/%Y')} (Ngày 10 hằng tháng)", style_body),
        ],
        [
            Paragraph(f"<b>Số điện thoại:</b> {tenant_phone}", style_body),
            Paragraph(f"<b>Gmail nhận hóa đơn:</b> {tenant_email}", style_body),
        ],
    ]
    info_table = Table(info_data, colWidths=[87 * mm, 87 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 4 * mm))

    # Bảng chi tiết các khoản thu
    elec_detail = f"Số cũ: {invoice.old_electricity:.0f} - Số mới: {invoice.new_electricity:.0f} ({invoice.electricity_usage:.0f} kWh x {_fmt_vnd(invoice.electricity_rate)})"
    water_detail = f"Số cũ: {invoice.old_water:.0f} - Số mới: {invoice.new_water:.0f} ({invoice.water_usage:.0f} m³ x {_fmt_vnd(invoice.water_rate)})"

    rows = [
        [
            Paragraph("<b>STT</b>", style_bold),
            Paragraph("<b>Khoản mục chi phí</b>", style_bold),
            Paragraph("<b>Chi tiết / Diễn giải cách tính</b>", style_bold),
            Paragraph("<b>Thành tiền</b>", style_right_bold),
        ],
        [
            Paragraph("1", style_body),
            Paragraph("Tiền thuê phòng cơ bản", style_body),
            Paragraph(f"Tiền phòng kỳ {invoice.month_year} (Phòng {room_num})", style_body),
            Paragraph(_fmt_vnd(invoice.room_charge), style_right),
        ],
        [
            Paragraph("2", style_body),
            Paragraph("Tiền điện sinh hoạt", style_body),
            Paragraph(elec_detail, style_body),
            Paragraph(_fmt_vnd(invoice.electricity_charge), style_right),
        ],
        [
            Paragraph("3", style_body),
            Paragraph("Tiền nước sinh hoạt", style_body),
            Paragraph(water_detail, style_body),
            Paragraph(_fmt_vnd(invoice.water_charge), style_right),
        ],
        [
            Paragraph("4", style_body),
            Paragraph("Phụ phí gửi xe", style_body),
            Paragraph("Phí gửi xe máy cố định theo tháng", style_body),
            Paragraph(_fmt_vnd(invoice.parking_fee), style_right),
        ],
        [
            Paragraph("5", style_body),
            Paragraph("Phụ phí bảo trì điện nước", style_body),
            Paragraph("Bảo trì hệ thống điện, nước, chiếu sáng hành lang", style_body),
            Paragraph(_fmt_vnd(invoice.maintenance_fee), style_right),
        ],
        [
            Paragraph("6", style_body),
            Paragraph("Phụ phí Internet / Wifi", style_body),
            Paragraph("Internet cáp quang tốc độ cao theo phòng", style_body),
            Paragraph(_fmt_vnd(invoice.wifi_fee), style_right),
        ],
        [
            Paragraph("7", style_body),
            Paragraph("Phụ phí vệ sinh / rác", style_body),
            Paragraph("Thu gom rác sinh hoạt & vệ sinh khu vực chung", style_body),
            Paragraph(_fmt_vnd(invoice.trash_fee), style_right),
        ],
    ]

    if invoice.other_charge and invoice.other_charge > 0:
        rows.append(
            [
                Paragraph("8", style_body),
                Paragraph("Phụ phí khác", style_body),
                Paragraph("Chi phí phát sinh khác trong tháng", style_body),
                Paragraph(_fmt_vnd(invoice.other_charge), style_right),
            ]
        )

    if invoice.discount and invoice.discount > 0:
        rows.append(
            [
                Paragraph("-", style_body),
                Paragraph("Giảm trừ / Khuyến mãi", style_body),
                Paragraph("Khoản giảm trừ trực tiếp trên hóa đơn", style_body),
                Paragraph(f"-{_fmt_vnd(invoice.discount)}", style_right),
            ]
        )

    rows.append(
        [
            Paragraph("", style_bold),
            Paragraph("<b>TỔNG CỘNG PHẢI THANH TOÁN</b>", style_bold),
            Paragraph("", style_bold),
            Paragraph(f"<b>{_fmt_vnd(invoice.total_amount)}</b>", style_right_bold),
        ]
    )

    detail_table = Table(rows, colWidths=[12 * mm, 48 * mm, 76 * mm, 38 * mm])
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F0FDFA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(detail_table)
    story.append(Spacer(1, 5 * mm))

    # Thông tin thanh toán / ngân hàng
    if invoice.status == "PAID":
        paid_date_str = invoice.paid_date.strftime("%d/%m/%Y") if invoice.paid_date else datetime.now().strftime("%d/%m/%Y")
        story.append(
            Paragraph(
                f"<b>XÁC NHẬN ĐÃ THU TIỀN:</b> Hóa đơn đã được thanh toán đủ 100% vào ngày <b>{paid_date_str}</b> "
                f"qua phương thức <b>{invoice.payment_method or 'ONLINE'}</b> "
                f"(Mã giao dịch: <b>{invoice.transaction_ref or 'GD-' + invoice.invoice_code}</b>).",
                style_body,
            )
        )
    else:
        story.append(
            Paragraph(
                "<b>HƯỚNG DẪN THANH TOÁN:</b><br/>"
                "- Cổng thanh toán trực tuyến trên Portal Phòng: Ví MoMo, Thẻ Quốc tế Visa, Ngân hàng liên kết.<br/>"
                "- Hoặc Chuyển khoản VietQR: Ngân hàng <b>Vietcombank (VCB)</b> - Số TK: <b>1029384756</b> - Chủ TK: <b>NGUYEN MINH HOANG</b> - "
                f"Nội dung CK: <b>PHONG {room_num} TT {invoice.month_year}</b>.<br/>"
                "- Lưu ý: Sau ngày 15 hằng tháng (quá hạn 5 ngày so với hạn đóng ngày 10), hóa đơn chưa thanh toán sẽ tự động chuyển sang trạng thái <b>Quá hạn (Nợ)</b>.",
                style_body,
            )
        )

    story.append(Spacer(1, 8 * mm))
    sig_table = Table(
        [
            [
                Paragraph("<b>NGƯỜI LẬP HÓA ĐƠN (CHỦ TRỌ)</b>", style_sub),
                Paragraph("<b>KHÁCH THUÊ PHÒNG</b>", style_sub),
            ],
            [Spacer(1, 16 * mm), Spacer(1, 16 * mm)],
            [
                Paragraph("<b>Nguyễn Minh Hoàng</b>", style_sub),
                Paragraph(f"<b>{tenant_name}</b>", style_sub),
            ],
        ],
        colWidths=[87 * mm, 87 * mm],
    )
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()


def send_invoice_email(
    db: Session,
    invoice: Invoice,
    email_type: str = "INVOICE_ISSUED",  # 'INVOICE_ISSUED', 'PAYMENT_RECEIPT', 'OVERDUE_REMINDER'
) -> EmailLog:
    """
    Gửi Hóa đơn / Biên lai PDF vào đúng Gmail của phòng đó (đảm bảo cô lập dữ liệu tuyệt đối).
    - Nếu cấu hình SMTP_USER & SMTP_PASSWORD trong môi trường (.env), gửi email thật kèm file PDF đính kèm.
    - Đồng thời luôn lưu bản ghi EmailLog vào MySQL để tra cứu và xem trực tiếp nội dung Gmail trên giao diện.
    """
    room = invoice.room
    tenant = invoice.tenant
    room_num = room.room_number if room else str(invoice.room_id)
    recipient_email = (tenant.email if (tenant and tenant.email) else f"phong{room_num}@gmail.com")
    recipient_name = (tenant.full_name if tenant else f"Khách thuê Phòng {room_num}")

    if email_type == "PAYMENT_RECEIPT":
        subject = f"[Nhà Trọ Minh Hoàng] Biên lai xác nhận ĐÃ THANH TOÁN tiền phòng {room_num} kỳ {invoice.month_year}"
        heading = f"XÁC NHẬN ĐÃ THANH TOÁN HÓA ĐƠN PHÒNG {room_num}"
        intro = (
            f"Cảm ơn <b>{recipient_name}</b> (Phòng <b>{room_num}</b>) đã hoàn tất thanh toán hóa đơn kỳ <b>{invoice.month_year}</b>. "
            f"Hệ thống đã gạch nợ thành công và đính kèm Biên lai PDF chi tiết bên dưới."
        )
    elif email_type == "OVERDUE_REMINDER":
        subject = f"[CẢNH BÁO QUÁ HẠN] Nhắc thanh toán nợ tiền phòng {room_num} kỳ {invoice.month_year}"
        heading = f"THÔNG BÁO QUÁ HẠN THANH TOÁN PHÒNG {room_num}"
        intro = (
            f"Kính gửi <b>{recipient_name}</b> (Phòng <b>{room_num}</b>), hóa đơn tiền phòng kỳ <b>{invoice.month_year}</b> "
            f"(Hạn đóng: ngày 10 hằng tháng) hiện đã quá hạn sau ngày 15 và chuyển sang trạng thái <b>Quá hạn (Nợ)</b>. "
            f"Vui lòng đăng nhập vào hệ thống mục 'Thanh toán nợ' để hoàn tất thanh toán."
        )
    else:
        subject = f"[Nhà Trọ Minh Hoàng] Thông báo Hóa đơn tiền phòng {room_num} kỳ {invoice.month_year}"
        heading = f"THÔNG BÁO HÓA ĐƠN TIỀN TRỌ PHÒNG {room_num} - KỲ {invoice.month_year}"
        intro = (
            f"Xin chào <b>{recipient_name}</b> (Phòng <b>{room_num}</b>), Chủ trọ vừa phát hành hóa đơn tiền phòng và điện nước kỳ <b>{invoice.month_year}</b>. "
            f"Hạn đóng tiền cố định là <b>Ngày 10 hằng tháng ({invoice.due_date.strftime('%d/%m/%Y')})</b>."
        )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 640px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
        <div style="background: #0f766e; color: #ffffff; padding: 18px 24px;">
            <h2 style="margin: 0; font-size: 18px;">{heading}</h2>
            <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">Mã hóa đơn: {invoice.invoice_code} | Phòng: {room_num}</p>
        </div>
        <div style="padding: 20px 24px; color: #1e293b; font-size: 14px; line-height: 1.6;">
            <p>{intro}</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px;">
                <tr style="background: #f8fafc; border-bottom: 1px solid #cbd5e1;">
                    <th style="text-align: left; padding: 8px;">Khoản mục</th>
                    <th style="text-align: right; padding: 8px;">Thành tiền</th>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">1. Tiền thuê phòng cơ bản</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.room_charge)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">2. Tiền điện ({invoice.electricity_usage:.0f} kWh x {_fmt_vnd(invoice.electricity_rate)})</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.electricity_charge)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">3. Tiền nước ({invoice.water_usage:.0f} m³ x {_fmt_vnd(invoice.water_rate)})</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.water_charge)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">4. Phụ phí gửi xe</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.parking_fee)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">5. Phụ phí bảo trì điện nước</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.maintenance_fee)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">6. Phụ phí Internet / Wifi</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.wifi_fee)}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px;">7. Phụ phí vệ sinh / rác</td>
                    <td style="text-align: right; padding: 8px;">{_fmt_vnd(invoice.trash_fee)}</td>
                </tr>
                <tr style="background: #f0fdfa; font-weight: bold; font-size: 15px;">
                    <td style="padding: 10px 8px; color: #0f766e;">TỔNG CỘNG</td>
                    <td style="text-align: right; padding: 10px 8px; color: #0f766e;">{_fmt_vnd(invoice.total_amount)}</td>
                </tr>
            </table>
            <p style="font-size: 12.5px; color: #475569;">
                📎 <b>Đính kèm:</b> File PDF Hóa đơn chuẩn <code>{invoice.invoice_code}.pdf</code>.<br/>
                Email này được gửi tự động từ Hệ thống Quản lý Nhà trọ & Thanh toán Tiền phòng. Tuyệt đối bảo mật và cô lập theo đúng Phòng {room_num}.
            </p>
        </div>
    </div>
    """

    attachment_filename = f"{invoice.invoice_code}.pdf"
    delivery_status = "SENT"

    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if smtp_user and smtp_password:
        try:
            pdf_bytes = generate_invoice_pdf(invoice)
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = recipient_email
            msg.set_content(f"Hóa đơn tiền phòng {room_num} kỳ {invoice.month_year} - Tổng tiền: {_fmt_vnd(invoice.total_amount)}")
            msg.add_alternative(body_html, subtype="html")
            msg.add_attachment(
                pdf_bytes,
                maintype="application",
                subtype="pdf",
                filename=attachment_filename,
            )
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            delivery_status = "SENT_SMTP"
        except Exception:
            delivery_status = "SENT_SIMULATED"
    else:
        delivery_status = "SENT_SIMULATED"

    invoice.email_sent = True
    invoice.email_sent_at = datetime.now(timezone.utc)

    log_entry = EmailLog(
        room_id=invoice.room_id,
        invoice_id=invoice.id,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        body_html=body_html,
        attachment_name=attachment_filename,
        status=delivery_status,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
