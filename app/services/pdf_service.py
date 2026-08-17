import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from app.models.finance import Payment

class PDFService:
    @staticmethod
    def generate_receipt(payment: Payment, student_name: str, org_name: str = "EduCRM O'quv Markazi") -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1, # Center
            spaceAfter=30
        )
        
        normal_style = styles["Normal"]
        normal_style.fontSize = 12
        normal_style.leading = 14
        
        # 1. Header (Organization Name)
        elements.append(Paragraph(f"<b>{org_name}</b>", title_style))
        elements.append(Paragraph("<b>RASMIY TO'LOV Kvitansiyasi (CHEK)</b>", ParagraphStyle('SubTitle', parent=styles['Heading2'], alignment=1, spaceAfter=20)))
        
        # 2. Receipt Details
        receipt_no = payment.transaction_id if payment.transaction_id else str(payment.id)[:8].upper()
        date_str = payment.created_at.strftime("%Y-%m-%d %H:%M") if payment.created_at else datetime.now().strftime("%Y-%m-%d %H:%M")
        
        method_labels = {
            'cash': 'Naqd pul',
            'card': 'Plastik karta',
            'bank_transfer': "Bank o'tkazmasi",
            'click': 'Click',
            'payme': 'Payme'
        }
        method_str = method_labels.get(payment.method, payment.method)
        
        status_labels = {
            'confirmed': 'Tasdiqlangan',
            'pending': 'Kutilmoqda',
            'cancelled': 'Bekor qilingan'
        }
        status_str = status_labels.get(payment.status, payment.status)
        
        amount_str = f"{int(payment.amount):,} UZS".replace(",", " ")
        
        data = [
            ["Chek raqami:", receipt_no],
            ["Sana va vaqt:", date_str],
            ["To'lovchi (O'quvchi):", student_name],
            ["To'lov davri:", f"{payment.period_year}-yil, {payment.period_month}-oy"],
            ["To'lov usuli:", method_str],
            ["Holati:", status_str],
            ["Summa:", amount_str],
        ]
        
        if payment.comment:
            data.append(["Izoh:", payment.comment])
            
        # 3. Table creation
        table = Table(data, colWidths=[2.5*inch, 3.5*inch])
        
        # Table Styling
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#64748b")), # Label color
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor("#0f172a")), # Value color
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ])
        table.setStyle(table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 40))
        
        # 4. Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1, # Center
        )
        elements.append(Paragraph("Bu hujjat avtomatik tarzda tizim orqali shakllantirilgan.", footer_style))
        elements.append(Paragraph("Savollar yuzasidan markaz ma'muriyatiga murojaat qilishingiz mumkin.", footer_style))
        
        # Build the PDF
        doc.build(elements)
        buffer.seek(0)
        
        return buffer
