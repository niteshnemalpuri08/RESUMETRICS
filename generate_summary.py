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

    # 1. Overview & Purpose
    elements.append(Paragraph("1. Overview & Purpose", h2_style))
    intro_text = (
        "ResuMetrics is an AI-powered hybrid resume screening and candidate matching web application. "
        "It is designed for HR teams, hiring managers, and recruiters who need to process large volumes of resumes quickly. "
        "The primary goal is to analyze candidate resumes (PDF or DOCX) against a job description or skill list "
        "and generate a ranked leaderboard based on requirements matching."
    )
    elements.append(Paragraph(intro_text, body_style))

    # 2. Core Functionality & User Workflow
    elements.append(Paragraph("2. Core Functionality & User Workflow", h2_style))
    workflow = [
        "<b>Input:</b> Upload multiple candidate resumes via a drag-and-drop interface and paste a job description.",
        "<b>Customization:</b> Tweak the importance of different matching algorithms using weight sliders.",
        "<b>Processing:</b> Extracts text directly from files in memory, cleans the text, and runs it through multiple AI scoring algorithms in parallel.",
        "<b>Results:</b> A dashboard displays interactive cards for each candidate featuring score gauges, matched/missing skill badges, contact info, and fraud alerts.",
        "<b>Export:</b> The final leaderboard can be exported as a professional PDF report or a CSV spreadsheet."
    ]
    workflow_items = [ListItem(Paragraph(w, bullet_style)) for w in workflow]
    elements.append(ListFlowable(workflow_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 10))

    # 3. The 'AI Brain'
    elements.append(Paragraph("3. The 'AI Brain' (Scoring Algorithms)", h2_style))
    algo_text = "The hybrid scoring engine blends three independent algorithms to ensure fair and accurate candidate ranking:"
    elements.append(Paragraph(algo_text, body_style))
    algos = [
        "<b>TF-IDF Keyword Matching (40%):</b> Finds overlapping technical terms and keywords, emphasizing rare, distinct terms over common filler words.",
        "<b>Exact Skill Matching (35%):</b> A fast algorithm that checks for the binary presence of specific required skills.",
        "<b>Dense Semantic Matching (25%):</b> Utilizes SentenceTransformer (an AI neural network) to understand the meaning of the text, matching semantically similar concepts."
    ]
    algo_items = [ListItem(Paragraph(a, bullet_style)) for a in algos]
    elements.append(ListFlowable(algo_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 10))

    # 4. Advanced NLP & Smart Features
    elements.append(Paragraph("4. Advanced NLP & Smart Features", h2_style))
    nlp = [
        "<b>Timeline Fraud Detection:</b> Compares explicit years of experience claimed against actual dates in job history, raising an alert on discrepancies.",
        "<b>Named Entity Recognition (NER):</b> Automatically categorizes degrees, job roles, professional certifications, and spoken languages.",
        "<b>Behavioral & Metric Extraction:</b> Identifies soft skills, impact-driven action verbs, and quantifiable metrics (e.g., '$10M', '50%').",
        "<b>RAG AI Chatbot:</b> Integrated chatbot allows recruiters to ask semantic questions over all uploaded candidate resumes.",
        "<b>Kanban ATS Pipeline:</b> Interactive drag-and-drop board to track candidates through Applied, Shortlisted, Interviewing, and Rejected stages.",
        "<b>Automated Shortlisting:</b> Integrated SMTP mailer to bulk-email selected candidates directly from the dashboard."
    ]
    nlp_items = [ListItem(Paragraph(n, bullet_style)) for n in nlp]
    elements.append(ListFlowable(nlp_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 10))

    # 5. Architecture & Tech Stack
    elements.append(Paragraph("5. Architecture & Tech Stack", h2_style))
    tech = [
        "<b>Backend (Python):</b> Flask for web server, SQLite for data, PyPDF/python-docx for parsing, and ReportLab/Pandas for exporting.",
        "<b>AI Engines:</b> scikit-learn, sentence-transformers, PyTorch, and NumPy handle the advanced scoring and matching.",
        "<b>Frontend:</b> HTML5, CSS3, Vanilla JavaScript, and SVG for animations, featuring a responsive, modern UI."
    ]
    tech_items = [ListItem(Paragraph(t, bullet_style)) for t in tech]
    elements.append(ListFlowable(tech_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 10))
    
    # 6. Performance Optimizations
    elements.append(Paragraph("6. Performance Optimizations", h2_style))
    perf = [
        "<b>In-Memory Processing:</b> Eliminates disk I/O by reading file bytes directly.",
        "<b>Concurrency:</b> Uses ThreadPoolExecutor to parse multiple resumes simultaneously.",
        "<b>AI Model Pre-warming:</b> The SentenceTransformer model loads in a background thread at startup for instant readiness.",
        "<b>Caching:</b> Uses SHA-256 to cache semantic vectors for resumes, making repeated analyses instant.",
        "<b>Single-Pass Regex:</b> Consolidates multiple regex replacement passes into a single pass for faster text normalization."
    ]
    perf_items = [ListItem(Paragraph(p, bullet_style)) for p in perf]
    elements.append(ListFlowable(perf_items, bulletType='bullet', start='circle'))

    # Build PDF
    doc.build(elements)
    print(f"Successfully generated {output_path}")

if __name__ == '__main__':
    generate_project_summary_pdf()
