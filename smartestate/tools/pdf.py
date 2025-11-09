from typing import List, Dict, Any
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_summary_pdf(title: str, sections: List[Dict[str, Any]]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for sec in sections:
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, sec.get("heading", "Section"))
        y -= 18
        c.setFont("Helvetica", 10)
        for line in sec.get("lines", []):
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
            c.drawString(50, y, str(line))
            y -= 14
        y -= 8
    c.showPage()
    c.save()
    return buf.getvalue()

