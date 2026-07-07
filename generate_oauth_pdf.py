import os
import sys
import subprocess

# Ensure reportlab is installed
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ImportError:
    print("Installing reportlab for PDF generation...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_pdf():
    pdf_filename = "oauth_documentation.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CustomCode', fontName='Courier', fontSize=10, 
                              backColor=colors.lightgrey, spaceBefore=10, spaceAfter=10,
                              leftIndent=10, rightIndent=10))

    Story = []

    # Title
    Story.append(Paragraph("AgriConnect - USSD Gateway & OAuth2 Documentation", styles['Title']))
    Story.append(Spacer(1, 24))

    # Overview
    Story.append(Paragraph("Overview", styles['Heading2']))
    Story.append(Paragraph("A webhook endpoint for USSD gateway integrations (e.g., Africa's Talking) has been added. "
                           "It is secured using OAuth2. The gateway must authenticate as a Client Application and forward the user's phone number and input.", 
                           styles['Normal']))
    Story.append(Spacer(1, 12))

    # Endpoint Details
    Story.append(Paragraph("Endpoint Details", styles['Heading2']))
    Story.append(Paragraph("<b>URL:</b> POST /api/ussd/", styles['Normal']))
    Story.append(Paragraph("<b>Authentication:</b> OAuth2 Access Token required (Authorization: Bearer &lt;token&gt;).", styles['Normal']))
    Story.append(Spacer(1, 12))
    
    Story.append(Paragraph("<b>Request Body (JSON or Form URL-Encoded):</b>", styles['Normal']))
    code_text = """
    {<br/>
    &nbsp;&nbsp;"phoneNumber": "0240001111",<br/>
    &nbsp;&nbsp;"text": "1*2",<br/>
    &nbsp;&nbsp;"sessionId": "12345",<br/>
    &nbsp;&nbsp;"serviceCode": "*920*44#"<br/>
    }
    """
    Story.append(Paragraph(code_text, styles['CustomCode']))
    
    Story.append(Paragraph("<b>Response:</b> Returns plain text USSD response strings prefixed with CON (Continue) or END (End transaction).", styles['Normal']))
    Story.append(Spacer(1, 24))

    # OAuth Setup
    Story.append(Paragraph("OAuth2 Setup Instructions", styles['Heading2']))
    setup_text = """
    To connect a USSD emulator or external gateway securely:<br/><br/>
    1. Log into the Django Admin portal (/admin/).<br/>
    2. Add a new application under <b>Django OAuth Toolkit</b>.<br/>
    3. Set <b>Client Type</b> to <i>Confidential</i> and <b>Authorization Grant Type</b> to <i>Client credentials</i>.<br/>
    4. Save the application.<br/>
    5. Use the generated <i>Client ID</i> and <i>Client Secret</i> to request access tokens from /o/token/.
    """
    Story.append(Paragraph(setup_text, styles['Normal']))

    doc.build(Story)
    print(f"Successfully generated {pdf_filename} in the current directory.")

if __name__ == "__main__":
    create_pdf()
