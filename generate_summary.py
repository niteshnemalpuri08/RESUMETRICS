import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

def generate_project_summary_pdf(output_path="ResuMetrics_Project_Summary.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0ea5e9'),
        spaceAfter=20,
        alignment=1 # Center
    )

    h2_style = ParagraphStyle(
        'Heading2Style',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=15,
        spaceAfter=10
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#334155'),
        spaceAfter=10,
        leading=16
    )

    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#334155'),
        leading=16
    )

    elements = []

    # Title
    elements.append(Paragraph("ResuMetrics", title_style))
    elements.append(Paragraph("Project Summary & Architecture Overview", ParagraphStyle(
        'SubTitle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=30
    )))

    # Introduction
    elements.append(Paragraph("What is ResuMetrics?", h2_style))
    intro_text = (
        "ResuMetrics is a smart assistant for hiring managers. Instead of spending hours reading through "
        "hundreds of resumes, you simply upload them to ResuMetrics. The system uses Artificial Intelligence "
        "to instantly read every resume, understand the candidate's experience, and rank them based on exactly "
        "what you are looking for in a perfect hire."
    )
    elements.append(Paragraph(intro_text, body_style))

    # Core Features
    elements.append(Paragraph("Key Features (Simply Explained)", h2_style))
    
    features = [
        "<b>Smart Reading (AI Understanding):</b> Instead of just using simple 'CTRL+F' to look for exact words, the AI actually understands meaning. If you ask for 'React', it knows that 'Frontend Web Developer' is a related skill.",
        "<b>Automatic Data Extraction:</b> The system automatically reads the resume and pulls out the important stuff: University names, Degrees, Job Titles, and impressive numbers (like 'Increased sales by 30%').",
        "<b>AI Candidate Summaries:</b> You don't have to read the whole resume. The AI writes a short, easy-to-read summary of the candidate's background, highlights their best soft skills, and even tells you if they get promoted quickly.",
        "<b>One-Click Emails:</b> Found some great candidates? You can select them all and hit 'Send Emails'. The system will automatically draft and send them personalized interview invitations.",
        "<b>Custom Take-Home Tests:</b> The AI can look at a candidate's specific skills and instantly generate a unique take-home assignment to test their abilities before the interview.",
        "<b>Visual Dashboard:</b> See all your candidates on a beautiful screen. You get visual charts (like a radar graph) showing exactly where they are strong and where they are weak.",
        "<b>Secure Storage:</b> Every resume and analysis is saved safely in a secure database so you never lose track of a good candidate."
    ]
    
    feature_items = [ListItem(Paragraph(f, bullet_style)) for f in features]
    elements.append(ListFlowable(feature_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 10))

    # Tech Stack
    elements.append(Paragraph("Technology Used (Behind the Scenes)", h2_style))
    tech = [
        "<b>The Brain (Python & Flask):</b> This is the main engine running the software, handling everything from uploading files to talking to the AI.",
        "<b>The Memory (MySQL Database):</b> A highly reliable storage system where all candidate information is kept safe.",
        "<b>The AI Reader (Sentence-Transformers):</b> A powerful AI model (similar to the tech behind ChatGPT) that understands human sentences.",
        "<b>The Look and Feel (HTML, CSS, JavaScript):</b> The code that makes the website look beautiful, modern, and easy to click around.",
        "<b>The Visuals (Chart.js):</b> The tool used to draw the colorful, interactive graphs on your screen."
    ]
    tech_items = [ListItem(Paragraph(t, bullet_style)) for t in tech]
    elements.append(ListFlowable(tech_items, bulletType='bullet', start='square'))
    elements.append(Spacer(1, 10))

    # Project Structure
    elements.append(Paragraph("How the Files are Organized", h2_style))
    structure = [
        "<b>app.py:</b> The 'Traffic Controller'. It manages the web pages and connects the user to the database.",
        "<b>resume_parser.py:</b> The 'Heavy Lifter'. This is where the AI actually reads the resumes and calculates the scores.",
        "<b>static/js/main.js:</b> The 'Interactivity Engine'. This makes buttons work, charts draw, and animations play without reloading the page.",
        "<b>templates/:</b> The folder holding the visual layouts for the login screen and the main dashboard.",
    ]
    structure_items = [ListItem(Paragraph(s, bullet_style)) for s in structure]
    elements.append(ListFlowable(structure_items, bulletType='bullet', start='circle'))

    # Build PDF
    doc.build(elements)
    print(f"Successfully generated {output_path}")

if __name__ == '__main__':
    generate_project_summary_pdf()
