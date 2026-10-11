import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

def generate_workflow_pdf(output_path="ResuMetrics_Workflow.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0ea5e9'),
        spaceAfter=15,
        alignment=1 # Center
    )

    h2_style = ParagraphStyle(
        'Heading2Style',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=12,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8,
        leading=14
    )

    step_style = ParagraphStyle(
        'StepStyle',
        parent=styles['Normal'],
        fontSize=9.5,
        textColor=colors.HexColor('#334155'),
        leading=14
    )

    elements = []

    # Title
    elements.append(Paragraph("ResuMetrics Workflow Architecture", title_style))
    elements.append(Paragraph("End-to-End Data Lifecycle, AI Pipeline & Cloud Infrastructure", ParagraphStyle(
        'SubTitle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=20
    )))

    elements.append(Paragraph("System Data Flow Overview", h2_style))
    intro_text = (
        "This architectural guide traces the complete operational lifecycle of a job screening request through "
        "ResuMetrics—from client-side authentication and file ingestion, across parallelized NLP extraction, "
        "hybrid AI matchmaking, relational database persistence, to actionable recruiter workflows and cloud edge serving."
    )
    elements.append(Paragraph(intro_text, body_style))

    # The Steps
    workflow_steps = [
        "<b>Phase 1: Ingestion & Session Orchestration</b><br/>"
        "Users authenticate via registered credentials or 1-Click Instant Demo Access (Recruiter or Applicant). The client securely posts candidate resumes (PDF/DOCX) alongside job requirements. Flask streams file payloads directly into memory without disk bottlenecks.",

        "<b>Phase 2: Multi-Threaded Text Extraction & Cleaning</b><br/>"
        "A ThreadPoolExecutor processes files concurrently. PyPDF and python-docx extract raw document strings. A single-pass regex normalization engine standardizes technology phrases ('C++' -> 'cpp', 'Node.js' -> 'nodejs'), purges formatting artifacts, and strips stop words.",

        "<b>Phase 3: Information Extraction & Timeline Auditing</b><br/>"
        "Pattern matchers identify contact parameters (emails, phone numbers), academic degrees, institutions, and quantifiable business achievements. A timeline verification algorithm cross-checks self-reported years of experience against actual employment dates to detect timeline fraud.",

        "<b>Phase 4: Hybrid AI Matchmaking & RRF Scoring</b><br/>"
        "The extracted text is evaluated across three decoupled scoring dimensions: (1) TF-IDF vectorization with cosine similarity, (2) Exact skill n-gram extraction, and (3) Dense semantic sentence embeddings. Reciprocal Rank Fusion (RRF) harmonizes all metrics into a normalized 0-100% match index.",

        "<b>Phase 5: Relational Persistence (MySQL & Hybrid Fallback)</b><br/>"
        "Extracted profiles, user sessions, and comprehensive analysis history payloads are committed directly to the user's MySQL database (`resumetrics` on localhost:3306). When operating in serverless environments, the self-healing SQLiteConnectionProxy maintains uninterrupted data persistence.",

        "<b>Phase 6: Interactive Recruiter & Applicant Dashboards</b><br/>"
        "Results render immediately in the responsive UI. Recruiters view sorted candidate cards, comparative radar charts, and skill badges. Applicants receive targeted keyword insights, missing skill roadmaps, and resume optimization advice.",

        "<b>Phase 7: Actionable ATS Pipeline & Automated Outreach</b><br/>"
        "Recruiters move applicants across a dynamic Kanban board (Applied, Shortlisted, Interviewing, Rejected), trigger bulk shortlist notification emails via SMTP, and export executive PDF summaries or CSV spreadsheets."
    ]

    for step in workflow_steps:
        elements.append(Paragraph(step, step_style))
        elements.append(Spacer(1, 6))

    elements.append(Paragraph("Underlying Infrastructure & Technology Stack", h2_style))
    
    tech_stack = [
        "<b>Flask & WSGI Middleware:</b> Powers backend routing, session management, and Vercel serverless integration via ProxyFix and VercelRoutingMiddleware.",
        "<b>Hybrid Database Layer:</b> Primary enterprise MySQL storage backed by an adaptive SQLite proxy for high availability across environments.",
        "<b>Machine Learning Stack:</b> Scikit-learn, SentenceTransformers, PyTorch, and NumPy executing vectorized similarity computations.",
        "<b>Frontend & Visualizations:</b> Modern CSS design system, responsive UI components, Chart.js radar analytics, and real-time DOM updates."
    ]

    for t in tech_stack:
        elements.append(Paragraph(t, step_style))
        elements.append(Spacer(1, 5))

    # Build PDF
    doc.build(elements)
    print(f"Successfully generated {output_path}")

if __name__ == '__main__':
    generate_workflow_pdf()
