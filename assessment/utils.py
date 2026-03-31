import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from django.utils import timezone

def generate_certificate_pdf(user, skill, certificate_id):
    """
    Generates a professional PDF certificate for a skill completion.
    Returns a FileResponse or BytesIO buffer.
    """
    buffer = io.BytesIO()
    
    # Create the PDF object, using landscape A4
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # --- Background & Border ---
    p.setFillColor(HexColor('#F9FAFB')) # Light gray bg
    p.rect(0, 0, width, height, fill=1)
    
    p.setStrokeColor(HexColor('#4F46E5')) # Indigo border
    p.setLineWidth(15)
    p.rect(20, 20, width-40, height-40)
    
    p.setStrokeColor(HexColor('#EEF2FF')) # Inner border
    p.setLineWidth(2)
    p.rect(40, 40, width-80, height-80)
    
    # --- Content ---
    p.setFillColor(HexColor('#111827')) # Dark gray text
    
    # Logo / Brand
    p.setFont("Helvetica-Bold", 32)
    p.drawCentredString(width/2, height - 120, "SkillLoop")
    
    p.setFont("Helvetica", 14)
    p.drawCentredString(width/2, height - 150, "BEYOND LEARNING. TOWARDS EARNING.")
    
    # Title
    p.setFont("Helvetica-Bold", 42)
    p.drawCentredString(width/2, height/2 + 60, "Certificate of Completion")
    
    p.setFont("Helvetica", 18)
    p.drawCentredString(width/2, height/2 + 20, "This is to certify that")
    
    # User Name
    p.setFont("Times-BoldItalic", 48)
    p.setFillColor(HexColor('#4F46E5'))
    p.drawCentredString(width/2, height/2 - 40, f"{user.first_name} {user.last_name}" if user.first_name else user.username)
    
    p.setFillColor(HexColor('#111827'))
    p.setFont("Helvetica", 18)
    p.drawCentredString(width/2, height/2 - 90, f"has successfully mastered the skill of")
    
    # Skill Name
    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(width/2, height/2 - 140, skill.name.upper())
    
    # Date & ID
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, 120, f"Issued on {timezone.now().strftime('%B %d, %Y')}")
    p.drawCentredString(width/2, 100, f"Certificate ID: {certificate_id}")
    
    # Signatures (Placeholders)
    p.setLineWidth(1)
    p.line(width/2 - 200, 150, width/2 - 50, 150)
    p.line(width/2 + 50, 150, width/2 + 200, 150)
    
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width/2 - 125, 135, "Academic Director")
    p.drawCentredString(width/2 + 125, 135, "Platform Head")

    # Finalize
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return buffer
