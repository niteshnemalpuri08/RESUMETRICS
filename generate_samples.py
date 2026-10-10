import os
import random
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_resume(filename, name, contact, text_blocks):
    doc = SimpleDocTemplate(f"sample_resumes/{filename}", pagesize=letter)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=10)
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=10, textColor='gray', spaceAfter=20)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceAfter=6, spaceBefore=12)
    normal_style = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=11, spaceAfter=8, leading=14)
    
    story = []
    
    story.append(Paragraph(f"<b>{name}</b>", title_style))
    story.append(Paragraph(contact, contact_style))
    
    for block in text_blocks:
        if block.startswith('##'):
            story.append(Paragraph(f"<b>{block[2:].strip()}</b>", heading_style))
        else:
            story.append(Paragraph(block, normal_style))
            
    doc.build(story)

def generate_20_resumes():
    # Clear directory
    if os.path.exists('sample_resumes'):
        shutil.rmtree('sample_resumes')
    os.makedirs('sample_resumes', exist_ok=True)

    first_names = ["Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn", "Skyler", "Drew", "Sydney", "Cameron", "Jesse", "Dakota", "Logan", "Peyton", "Spencer", "Kendall", "Reese", "Parker"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

    roles = [
        ("Senior Full-Stack Engineer", ["React", "Python", "Node.js", "AWS", "SQL"]),
        ("Backend Developer", ["Python", "Django", "PostgreSQL", "Docker", "Redis", "FastAPI"]),
        ("Frontend Engineer", ["JavaScript", "TypeScript", "React", "Vue", "CSS", "Tailwind"]),
        ("Data Scientist", ["Python", "Machine Learning", "Pandas", "Scikit-Learn", "SQL", "Tableau"]),
        ("DevOps Engineer", ["AWS", "Kubernetes", "Docker", "CI/CD", "Terraform", "Linux"]),
        ("Machine Learning Engineer", ["Python", "TensorFlow", "PyTorch", "AWS", "MLOps", "NLP"]),
        ("Software Architect", ["Java", "Spring Boot", "Microservices", "Kafka", "PostgreSQL", "AWS"])
    ]
    
    companies = ["Google", "Amazon", "Startup Inc.", "Tech Solutions", "InnovateCorp", "Fintech Partners", "HealthTech Ltd"]
    
    for i in range(20):
        name = f"{first_names[i]} {last_names[i]}"
        role, skills = random.choice(roles)
        company = random.choice(companies)
        
        text_blocks = [
            "## SUMMARY",
            f"Highly motivated {role} with 5+ years of experience specializing in {', '.join(skills[:3])}. Proven track record of delivering scalable solutions and driving revenue growth through technical innovation.",
            "## SKILLS",
            f"Technologies: {', '.join(skills)}",
            "## EXPERIENCE",
            f"<b>{role}</b> | {company} | Jan 2019 - Present",
            f"Led the development of a high-performance system using {skills[0]} and {skills[1]}. Mentored junior engineers and implemented best practices in CI/CD.",
            f"<b>Software Developer</b> | Tech Solutions | Feb 2016 - Dec 2018",
            f"Developed RESTful APIs and maintained database schemas for a large user base using {skills[-1]}.",
            "## EDUCATION",
            "B.S. Computer Science | State University | Graduated 2015"
        ]
        
        filename = f"{name.replace(' ', '_')}_{role.replace(' ', '_')}.pdf"
        create_resume(filename, name, f"{name.lower().replace(' ','')}@email.com | 555-010-{i:04d}", text_blocks)
        
    print("Successfully cleared old resumes and generated 20 new high-quality sample resumes.")

if __name__ == '__main__':
    generate_20_resumes()
