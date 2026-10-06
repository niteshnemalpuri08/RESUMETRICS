import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_resume(filename, name, contact, text_blocks):
    os.makedirs('sample_resumes', exist_ok=True)
    doc = SimpleDocTemplate(f"sample_resumes/{filename}", pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=10)
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=10, textColor='gray', spaceAfter=20)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceAfter=6, spaceBefore=12)
    normal_style = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=11, spaceAfter=8, leading=14)
    
    story = []
    
    # Header
    story.append(Paragraph(f"<b>{name}</b>", title_style))
    story.append(Paragraph(contact, contact_style))
    
    # Sections
    for block in text_blocks:
        if block.startswith('##'):
            story.append(Paragraph(f"<b>{block[2:].strip()}</b>", heading_style))
        else:
            story.append(Paragraph(block, normal_style))
            
    doc.build(story)

# Resume 1: The Perfect Match (Senior ML Engineer)
r1_text = [
    "## SUMMARY",
    "Results-driven Senior AI Architect and Machine Learning Engineer with 8 years of experience building scalable data pipelines and deploying deep learning models. Highly collaborative and team-oriented leader who mentors junior developers and drives cross-functional initiatives to increase revenue.",
    "## SKILLS",
    "Programming: Python, SQL, Java, C++",
    "Frameworks: PyTorch, Keras, Scikit-Learn, Pandas",
    "Infrastructure: AWS, GCP, Docker, Kubernetes",
    "## EXPERIENCE",
    "<b>Senior AI Architect</b> | Google | Jan 2018 - Present",
    "Led a cross-functional team to deploy a massive deep learning recommendation engine using PyTorch and Kubernetes on AWS, resulting in a 15% increase in user engagement.",
    "Innovated a novel data pipeline utilizing SQL and Apache Spark to process terabytes of data daily.",
    "<b>Machine Learning Engineer</b> | Startup Inc. | Feb 2015 - Dec 2017",
    "Developed predictive models using Python and Scikit-Learn. Collaborated with product managers to deliver data-driven solutions.",
    "## EDUCATION",
    "B.S. Computer Science | MIT | Graduated May 2014"
]
create_resume("Elena_Rostova_Senior_AI.pdf", "Elena Rostova", "elena.rostova@email.com | 555-019-2837", r1_text)

# Resume 2: The Timeline Fraud (Junior but claiming Senior)
r2_text = [
    "## SUMMARY",
    "Senior Data Scientist with 8 years of extensive industry experience in Python and SQL. Fast-paced, adaptable, and flexible professional looking for a leadership role.",
    "## SKILLS",
    "Python, SQL, Tableau, Data Analysis, Excel",
    "## EXPERIENCE",
    "<b>Data Scientist</b> | Tech Corp | Jan 2022 - Present",
    "Created data visualization dashboards. Analyzed business metrics using SQL.",
    "<b>Data Analyst</b> | Local Business | Mar 2021 - Dec 2021",
    "Cleaned datasets using Python and pandas.",
    "## EDUCATION",
    "B.A. Economics | State University | Graduated 2020"
]
create_resume("John_Doe_Data_Scientist.pdf", "John Doe", "john.doe@email.com | 555-123-4567", r2_text)

# Resume 3: The Generalist / Non-Tech Culture Fit
r3_text = [
    "## SUMMARY",
    "Dynamic and agile Product Manager with a passion for designing innovative and creative solutions. Extremely adaptable and collaborative team player who excels in fast-paced startup environments. Focuses on bringing people together to brainstorm novel ideas.",
    "## SKILLS",
    "Product Management, Agile, Scrum, Jira, Figma, Cross-functional Leadership, Communication",
    "## EXPERIENCE",
    "<b>Product Manager</b> | InnovateTech | Jun 2019 - Present",
    "Collaborated with engineering and design teams to launch 3 major SaaS products. Spearheaded brainstorming sessions and designed user-centric workflows.",
    "<b>Scrum Master</b> | AgileWorks | Jan 2017 - May 2019",
    "Mentored teams on Agile methodologies. Supported cross-functional delivery.",
    "## EDUCATION",
    "B.S. Business Administration | NYU | Graduated 2016"
]
create_resume("Sarah_Jenkins_Product_Manager.pdf", "Sarah Jenkins", "sarah.j@email.com | 555-987-6543", r3_text)

print("Generated 3 high-quality sample resumes in 'sample_resumes' folder.")
