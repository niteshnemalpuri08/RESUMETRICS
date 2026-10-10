import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

def generate_workflow_pdf(output_path="ResuMetrics_Workflow.pdf"):
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
        spaceAfter=15,
        alignment=1 # Center
    )

    h2_style = ParagraphStyle(
        'Heading2Style',
        parent=styles['Heading2'],
        fontSize=14,
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

    step_style = ParagraphStyle(
        'StepStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#334155'),
        leading=16
    )

    elements = []

    # Title
    elements.append(Paragraph("ResuMetrics Workflow Architecture", title_style))
    elements.append(Paragraph("Step-by-Step Data Flow and AI Processing Pipeline", ParagraphStyle(
        'SubTitle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=25
    )))

    elements.append(Paragraph("How ResuMetrics Works", h2_style))
    intro_text = (
        "This document outlines the complete lifecycle of a resume as it travels through the "
        "ResuMetrics pipeline—from initial user upload to final AI-driven insights and recruiter actions."
    )
    elements.append(Paragraph(intro_text, body_style))

    # The Steps
    workflow_steps = [
        "<b>Step 1: Uploading Resumes</b><br/>"
        "The recruiter logs into the website, types in the skills they are looking for, and uploads a batch of resumes (like PDFs). The system immediately starts reading them all at the same time.",
        
        "<b>Step 2: Reading the Text</b><br/>"
        "The system opens each file, extracts the text, and cleans it up by removing extra spaces or weird symbols. This makes it very easy for the AI to read.",
        
        "<b>Step 3: Spotting Important Details</b><br/>"
        "The system scans the text to find specific, important things. It acts like a digital highlighter, picking out University Names, Job Titles, and impressive numbers (like 'increased sales by 30%').",

        "<b>Step 4: AI Matchmaking</b><br/>"
        "The AI compares the resume against the job requirements in two ways: First, it looks for exact word matches. Second, it uses deep learning to understand the <i>meaning</i> of the words. It combines both methods to give a final 'Match Percentage'.",

        "<b>Step 5: Smart Insights</b><br/>"
        "The AI looks deeper to write a quick summary of the candidate. It checks if they are a fast learner (like being promoted quickly) and lists exactly which requested skills they have and which ones they are missing.",

        "<b>Step 6: Showing the Results</b><br/>"
        "The system sends all this information back to your screen, drawing beautiful interactive charts (like radar graphs) so you can visually compare the candidates.",

        "<b>Step 7: Taking Action & Shortlisting</b><br/>"
        "You can immediately send automated interview emails to the best candidates, or ask the AI to generate a custom take-home test for them, right from the dashboard.",
        
        "<b>Step 8: Pipeline Management & Conversational AI</b><br/>"
        "Drag and drop candidates across an interactive Kanban board (Applied -> Shortlisted -> Interviewing -> Rejected) and use the built-in RAG Chatbot to ask natural language questions about your candidate pool."
    ]

    for idx, step in enumerate(workflow_steps, start=1):
        elements.append(Paragraph(step, step_style))
        elements.append(Spacer(1, 10))
        
    elements.append(Paragraph("Data Persistence", h2_style))
    elements.append(Paragraph("Throughout this entire process, all resumes and final scores are permanently saved in a secure database so you can always review them later.", body_style))

    # Technology Stack Justification & Implementation
    elements.append(Paragraph("The Technology Explained Simply", h2_style))
    
    tech_stack = [
        "<b>1. The Engine (Flask & Python)</b><br/>"
        "<i>What it does:</i> Think of this as the traffic cop. It directs your clicks on the website to the right places and makes sure the heavy lifting (reading resumes) happens smoothly in the background without freezing your screen.",
        
        "<b>2. The AI Brain (Sentence-Transformers)</b><br/>"
        "<i>What it does:</i> Instead of just looking for exact words, this AI model acts like a human reader. It knows that 'Frontend Developer' is closely related to 'React', allowing it to find great candidates even if they didn't use the exact right buzzwords.",
        
        "<b>3. The Detail Spotter (NLP)</b><br/>"
        "<i>What it does:</i> This is a set of rules that acts like a highlighter pen. It is specifically designed to highlight emails, universities, and action verbs so they can be shown neatly as tags on the candidate's card.",
        
        "<b>4. The Filing Cabinet (MySQL Database)</b><br/>"
        "<i>What it does:</i> A highly secure and organized digital filing cabinet where all candidate information, resumes, and AI scores are saved permanently.",
        
        "<b>5. The Interactivity (JavaScript)</b><br/>"
        "<i>What it does:</i> This is the magic that makes the website feel alive. It handles the smooth animations, opening menus, and switching tabs instantly without making you wait for a loading screen.",
        
        "<b>6. The Artist (Chart.js)</b><br/>"
        "<i>What it does:</i> A drawing tool that takes raw numbers (like a candidate's 80% match score) and instantly paints them into beautiful, easy-to-understand visual graphs on your dashboard."
    ]

    for t in tech_stack:
        elements.append(Paragraph(t, step_style))
        elements.append(Spacer(1, 10))

    # Build PDF
    doc.build(elements)
    print(f"Successfully generated {output_path}")

if __name__ == '__main__':
    generate_workflow_pdf()
