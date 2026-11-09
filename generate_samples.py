import os
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_resume(filename, name, contact, text_blocks):
    doc = SimpleDocTemplate(f"sample_resumes/{filename}", pagesize=letter)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=8)
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'], fontSize=9, textColor='gray', spaceAfter=14)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=12, spaceAfter=4, spaceBefore=10)
    normal_style = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=10, spaceAfter=6, leading=13)
    
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
    if os.path.exists('sample_resumes'):
        shutil.rmtree('sample_resumes')
    os.makedirs('sample_resumes', exist_ok=True)

    candidates = [
        {
            "name": "Alex Smith",
            "role": "Senior Full-Stack Engineer",
            "email": "alex.smith@techcorp.com",
            "phone": "555-010-0001",
            "blocks": [
                "## PROFESSIONAL SUMMARY",
                "Senior Full-Stack Engineer with 8+ years building enterprise SaaS platforms. Led architectural modernization resulting in 45% faster page rendering and $1.2M annual cloud cost reduction. Expert in React, Node.js, Python, and AWS.",
                "## TECHNICAL SKILLS",
                "Languages & Frameworks: React, TypeScript, Node.js, Python, FastAPI, Next.js, HTML5, CSS3, Tailwind",
                "Databases & Cloud: PostgreSQL, Redis, AWS, Docker, Kubernetes, CI/CD, Git",
                "## PROFESSIONAL EXPERIENCE",
                "<b>Lead Full-Stack Engineer</b> | TechCorp Inc. | Jan 2021 - Present",
                "Spearheaded redesign of customer analytics portal serving 3.5M daily active users. Migrated legacy monolith to decoupled React microfrontends and Node.js microservices. Reduced p99 latency by 60% and increased sprint throughput by 35%.",
                "<b>Senior Software Engineer</b> | CloudScale Systems | Mar 2017 - Dec 2020",
                "Architected multi-tenant RESTful APIs using Python, FastAPI, and PostgreSQL. Integrated Redis caching layer saving 40% database roundtrips during peak traffic spikes.",
                "## CERTIFICATIONS",
                "AWS Certified Solutions Architect - Professional | Certified Kubernetes Administrator (CKA)",
                "## EDUCATION",
                "M.S. in Computer Science | Stanford University | Graduated 2016"
            ]
        },
        {
            "name": "Jordan Johnson",
            "role": "Lead Backend Architect",
            "email": "jordan.johnson@datastream.io",
            "phone": "555-010-0002",
            "blocks": [
                "## SUMMARY",
                "High-throughput backend engineer and distributed systems specialist with 7 years architecting fault-tolerant microservices handling 20,000+ RPS. Proficient in Go, Python, Kafka, and PostgreSQL.",
                "## CORE COMPETENCIES",
                "Backend: Python, Django, Go, gRPC, RESTful APIs, Spring Boot",
                "Data & Infrastructure: PostgreSQL, Redis, Apache Kafka, Elasticsearch, Docker, AWS",
                "## EXPERIENCE",
                "<b>Staff Backend Engineer</b> | DataStream IO | Feb 2020 - Present",
                "Designed and launched distributed event streaming pipeline using Kafka and Go, processing 50M daily events with 99.99% uptime. Reduced infrastructure costs by $350K per year.",
                "<b>Backend Developer</b> | NexaSoft | Jun 2017 - Jan 2020",
                "Built asynchronous worker clusters with Python, Celery, and Redis to process large-scale background ETL pipelines.",
                "## EDUCATION",
                "B.Tech in Computer Engineering | Massachusetts Institute of Technology | Graduated 2017"
            ]
        },
        {
            "name": "Taylor Williams",
            "role": "Frontend Specialist",
            "email": "taylor.williams@designsync.org",
            "phone": "555-010-0003",
            "blocks": [
                "## PROFESSIONAL SUMMARY",
                "UI/UX-focused Frontend Engineer with 6 years experience crafting responsive, accessible, and performant web applications. Passionate about Web Vitals, microfrontends, and accessible component libraries.",
                "## SKILLS",
                "Frontend: React, TypeScript, JavaScript, Vue.js, Next.js, Redux, Tailwind CSS, Jest, Cypress",
                "Tooling: Webpack, Vite, Git, Figma, Storybook, CI/CD",
                "## EXPERIENCE",
                "<b>Senior Frontend Engineer</b> | DesignSync | Aug 2020 - Present",
                "Engineered scalable design system adopted across 8 cross-functional product teams. Improved Lighthouse performance score from 62 to 98 across core web flows.",
                "<b>Frontend Developer</b> | PixelCraft | May 2018 - Jul 2020",
                "Delivered dynamic single-page applications using Vue.js and TypeScript, increasing user session retention by 28%.",
                "## EDUCATION",
                "B.S. in Software Engineering | University of California Berkeley | Graduated 2018"
            ]
        },
        {
            "name": "Casey Brown",
            "role": "DevOps Engineer",
            "email": "casey.brown@infrawave.net",
            "phone": "555-010-0004",
            "blocks": [
                "## SUMMARY",
                "DevOps and SRE practitioner with focus on infrastructure automation, container orchestration, and multi-region resilience. Experience running production Kubernetes clusters on AWS and GCP.",
                "## TECHNICAL SKILLS",
                "Cloud & DevOps: AWS, Kubernetes, Terraform, Docker, Helm, CI/CD, GitHub Actions, Prometheus, Grafana",
                "Scripting: Python, Bash, Go, Linux",
                "## EXPERIENCE",
                "<b>DevOps Lead</b> | InfraWave Solutions | Jan 2022 - Present",
                "Provisioned zero-downtime infrastructure across 3 AWS regions using Terraform and Kubernetes. Automated CI/CD deployment pipelines cutting lead time from 4 days to 25 minutes.",
                "<b>Systems Engineer</b> | LegacyNet Corp | Jan 2018 - Mar 2024",
                "Maintained hybrid cloud infrastructure, automated backup policies, and resolved high-severity production incidents.",
                "## EDUCATION",
                "Associate Degree in Information Technology | City College | Graduated 2017"
            ]
        },
        {
            "name": "Morgan Jones",
            "role": "Machine Learning Engineer",
            "email": "morgan.jones@deepmindset.ai",
            "phone": "555-010-0005",
            "blocks": [
                "## SUMMARY",
                "ML Engineer with 6 years specializing in Natural Language Processing, Transformer architectures, and scalable model inference deployment. Published researcher in deep learning.",
                "## TECHNICAL EXPERTISE",
                "Machine Learning: PyTorch, TensorFlow, Scikit-Learn, Hugging Face, Transformers, NLP, Computer Vision, MLOps",
                "Engineering: Python, FastAPI, Docker, Ray, Triton Inference Server, AWS SageMaker",
                "## EXPERIENCE",
                "<b>Senior ML Engineer</b> | DeepMindset AI | Sep 2020 - Present",
                "Built and deployed real-time semantic document search engine using sentence embeddings and FAISS vector database. Handled 15M monthly queries with sub-30ms p95 latency.",
                "<b>Machine Learning Specialist</b> | DataSphere | Jun 2018 - Aug 2020",
                "Trained gradient boosting and deep learning models for churn prediction, increasing retention by 18% and generating $800K in preserved recurring revenue.",
                "## EDUCATION",
                "Ph.D. in Computer Science | Carnegie Mellon University | Graduated 2018"
            ]
        },
        {
            "name": "Riley Garcia",
            "role": "Senior Full-Stack Engineer",
            "email": "riley.garcia@fastscale.com",
            "phone": "555-010-0006",
            "blocks": [
                "## PROFESSIONAL SUMMARY",
                "High-velocity Full-Stack Engineer who rapidly progressed from Junior Engineer to Lead in under 3 years. Delivered critical revenue-generating product launches with exceptional code quality and velocity.",
                "## SKILLS",
                "Stack: React, TypeScript, Python, FastAPI, PostgreSQL, AWS, Docker, Redis, Tailwind",
                "## EXPERIENCE",
                "<b>Lead Full-Stack Developer</b> | FastScale Tech | Jan 2023 - Present",
                "Promoted to Lead in record time after leading development of core subscription billing platform generating $4.2M ARR. Reduced customer onboarding friction by 55%.",
                "<b>Senior Software Engineer</b> | FastScale Tech | Jun 2021 - Dec 2022",
                "Architected real-time collaboration features using WebSockets and Redis Pub/Sub, supporting 50K concurrent active connections.",
                "<b>Junior Software Engineer</b> | FastScale Tech | Jan 2020 - May 2021",
                "Implemented responsive frontend dashboards and built automated regression test suites increasing test coverage to 92%.",
                "## EDUCATION",
                "B.S. in Computer Science | University of Washington | Graduated 2019"
            ]
        },
        {
            "name": "Avery Miller",
            "role": "Data Scientist & Analytics Lead",
            "email": "avery.miller@insightiq.com",
            "phone": "555-010-0007",
            "blocks": [
                "## SUMMARY",
                "Data Scientist with 5+ years of experience turning complex datasets into strategic business decisions. Strong background in statistical modeling, A/B testing, and executive storytelling.",
                "## SKILLS",
                "Data Science: Python, SQL, Pandas, NumPy, Scikit-Learn, Tableau, Snowflake, dbt, Statistics",
                "## EXPERIENCE",
                "<b>Lead Data Scientist</b> | InsightIQ | Jul 2021 - Present",
                "Designed multi-touch marketing attribution model directly informing $10M annual advertising spend. Built automated anomaly detection pipelines in Snowflake.",
                "<b>Data Analyst</b> | MetricsCorp | Jan 2019 - Jun 2021",
                "Developed executive KPI dashboards in Tableau and conducted statistical hypothesis testing for product experimentation.",
                "## EDUCATION",
                "M.S. in Data Analytics | Columbia University | Graduated 2018"
            ]
        },
        {
            "name": "Quinn Davis",
            "role": "Cloud Security Engineer",
            "email": "quinn.davis@securesphere.io",
            "phone": "555-010-0008",
            "blocks": [
                "## SUMMARY",
                "Information security engineer with expertise in zero trust architectures, DevSecOps, cloud compliance (SOC2, ISO 27001), and vulnerability assessments.",
                "## TECHNICAL SKILLS",
                "Security: AWS Security, IAM, SIEM, Penetration Testing, OWASP, Docker, Kubernetes, Python, Terraform",
                "## EXPERIENCE",
                "<b>Senior Security Engineer</b> | SecureSphere | May 2020 - Present",
                "Enforced automated static and dynamic security scanning in CI/CD pipeline, catching 400+ critical CVEs prior to production deployments. Led successful SOC 2 Type II audit.",
                "<b>Security Analyst</b> | CyberDefense LLC | Jun 2017 - Apr 2020",
                "Conducted penetration testing and incident response triage across 200+ multi-cloud VPCs.",
                "## CERTIFICATIONS",
                "CISSP | Certified Information Systems Security Professional",
                "## EDUCATION",
                "B.S. in Cybersecurity | Georgia Institute of Technology | Graduated 2017"
            ]
        },
        {
            "name": "Skyler Rodriguez",
            "role": "Mobile Applications Engineer",
            "email": "skyler.rodriguez@appfactory.dev",
            "phone": "555-010-0009",
            "blocks": [
                "## SUMMARY",
                "Cross-platform mobile developer with 6 years shipping consumer apps with over 5M collective downloads. Specialist in Flutter, React Native, iOS (Swift), and Android (Kotlin).",
                "## SKILLS",
                "Mobile: React Native, Flutter, Swift, Kotlin, TypeScript, Redux, SQLite, Firebase, App Store Deployment",
                "## EXPERIENCE",
                "<b>Lead Mobile Developer</b> | AppFactory Dev | Nov 2020 - Present",
                "Spearheaded complete rewrite of flagship mobile application into React Native, reducing duplicate code between iOS and Android by 70% and boosting app store rating from 3.8 to 4.8 stars.",
                "<b>Mobile Developer</b> | Handheld Innovations | Feb 2018 - Oct 2020",
                "Developed native iOS features using Swift and integrated CoreData for offline caching.",
                "## EDUCATION",
                "B.S. in Computer Science | University of Texas at Austin | Graduated 2018"
            ]
        },
        {
            "name": "Drew Martinez",
            "role": "Database Administrator & Data Engineer",
            "email": "drew.martinez@datalink.org",
            "phone": "555-010-0010",
            "blocks": [
                "## SUMMARY",
                "Database Engineer and DBA with 9 years architecting resilient relational and NoSQL databases. Expert in query optimization, replication topologies, and high availability.",
                "## SKILLS",
                "Databases: PostgreSQL, MySQL, Redis, MongoDB, Cassandra, SQL, Database Tuning, ETL, Python",
                "## EXPERIENCE",
                "<b>Principal Database Engineer</b> | DataLink Corp | Jan 2019 - Present",
                "Managed 40TB PostgreSQL production cluster. Tuned indexing strategies, query execution plans, and vacuum parameters, yielding an 80% decrease in slow queries.",
                "<b>Database Administrator</b> | Enterprise Systems | Mar 2015 - Dec 2018",
                "Designed disaster recovery protocols and automated point-in-time recovery testing across MySQL replication clusters.",
                "## EDUCATION",
                "B.S. in Information Systems | Purdue University | Graduated 2015"
            ]
        },
        {
            "name": "Sydney Hernandez",
            "role": "Frontend Engineer",
            "email": "sydney.h@webvanguard.com",
            "phone": "555-010-0011",
            "blocks": [
                "## SUMMARY",
                "Frontend software engineer with 4 years building interactive web apps in React, Vue, and Next.js. Strong focus on CSS animations and mobile-first responsiveness.",
                "## SKILLS",
                "Frontend: React, JavaScript, TypeScript, Next.js, CSS3, Tailwind CSS, HTML5, Webpack",
                "## EXPERIENCE",
                "<b>Frontend Engineer</b> | WebVanguard | Mar 2021 - Present",
                "Implemented customer checkout journey using Next.js and Tailwind, reducing checkout drop-off rate by 22%.",
                "<b>Junior Web Developer</b> | CreativeStudio | Jun 2019 - Feb 2021",
                "Built marketing landing pages and optimized frontend asset delivery pipelines.",
                "## EDUCATION",
                "B.A. in Digital Arts & Computer Science | New York University | Graduated 2019"
            ]
        },
        {
            "name": "Cameron Lopez",
            "role": "Senior Backend Developer",
            "email": "cameron.lopez@cloudlogic.io",
            "phone": "555-010-0012",
            "blocks": [
                "## SUMMARY",
                "Backend engineer with 5 years crafting scalable REST APIs and event-driven architectures using Python, Django, FastAPI, and Docker.",
                "## SKILLS",
                "Backend: Python, Django, FastAPI, PostgreSQL, Docker, Redis, Celery, Git, AWS",
                "## EXPERIENCE",
                "<b>Senior Backend Developer</b> | CloudLogic | Jan 2021 - Present",
                "Engineered multi-channel notification engine sending 2M push notifications and SMS daily with 99.98% delivery rate.",
                "<b>Software Developer</b> | FinApp Services | Jul 2019 - Dec 2020",
                "Built payment processing integrations with Stripe and Adyen using Django and PostgreSQL.",
                "## EDUCATION",
                "B.Tech in Computer Engineering | University of Illinois Urbana-Champaign | Graduated 2019"
            ]
        },
        {
            "name": "Jesse Gonzalez",
            "role": "QA & Automation Test Architect",
            "email": "jesse.g@qualityhub.net",
            "phone": "555-010-0013",
            "blocks": [
                "## SUMMARY",
                "SDET and QA engineer with 6 years designing robust test automation frameworks from unit to end-to-end regression. Passionate about shifting quality left.",
                "## SKILLS",
                "Testing: Playwright, Cypress, Selenium, PyTest, Jest, Postman, CI/CD, Python, JavaScript",
                "## EXPERIENCE",
                "<b>Lead QA Automation Engineer</b> | QualityHub | Apr 2021 - Present",
                "Architected end-to-end testing suite in Playwright and GitHub Actions running 1,200 test cases per pull request, reducing release defects by 75%.",
                "<b>QA Engineer</b> | TestCraft Solutions | Sep 2018 - Mar 2021",
                "Created automated regression tests in PyTest and Selenium for web and REST API workflows.",
                "## EDUCATION",
                "B.S. in Software Engineering | Ohio State University | Graduated 2018"
            ]
        },
        {
            "name": "Dakota Wilson",
            "role": "DevOps & Cloud Engineer",
            "email": "dakota.wilson@scaleops.org",
            "phone": "555-010-0014",
            "blocks": [
                "## SUMMARY",
                "Infrastructure and Cloud automation specialist with 5 years managing AWS environments, Terraform IaC, and Kubernetes clusters.",
                "## SKILLS",
                "Cloud/DevOps: AWS, Kubernetes, Docker, Terraform, Linux, CI/CD, Python, Helm",
                "## EXPERIENCE",
                "<b>DevOps Engineer</b> | ScaleOps | Feb 2021 - Present",
                "Automated zero-touch Kubernetes deployments using Helm and ArgoCD, slashing deployment rollback rates by 90%.",
                "<b>Cloud Operations Engineer</b> | NetServices | Aug 2019 - Jan 2021",
                "Managed AWS cloud infrastructure using Terraform and monitored fleet health with CloudWatch.",
                "## EDUCATION",
                "B.S. in Computer Science | University of Michigan | Graduated 2019"
            ]
        },
        {
            "name": "Logan Anderson",
            "role": "Data Engineer",
            "email": "logan.a@pipelinepro.io",
            "phone": "555-010-0015",
            "blocks": [
                "## SUMMARY",
                "Big Data Engineer with 6 years building streaming and batch data pipelines using Spark, Airflow, and Snowflake.",
                "## SKILLS",
                "Data Engineering: Python, SQL, Apache Spark, Airflow, Snowflake, AWS, PostgreSQL, Kafka",
                "## EXPERIENCE",
                "<b>Senior Data Engineer</b> | PipelinePro | Jun 2020 - Present",
                "Architected streaming ETL ingestion processing 12TB daily from clickstream logs into Snowflake warehouse.",
                "<b>Data Pipeline Developer</b> | BigData Co | May 2018 - May 2020",
                "Wrote distributed Spark jobs and scheduled DAGs using Apache Airflow.",
                "## EDUCATION",
                "M.S. in Data Science | University of Southern California | Graduated 2018"
            ]
        },
        {
            "name": "Peyton Thomas",
            "role": "Senior Full-Stack Engineer",
            "email": "peyton.t@webcraft.com",
            "phone": "555-010-0016",
            "blocks": [
                "## SUMMARY",
                "Full-stack web architect with 7 years developing consumer web applications. Strong command of React, Node.js, and cloud deployments.",
                "## SKILLS",
                "Stack: React, TypeScript, Node.js, Python, PostgreSQL, AWS, Docker, HTML5, CSS3",
                "## EXPERIENCE",
                "<b>Senior Full-Stack Engineer</b> | WebCraft | Jan 2020 - Present",
                "Designed and launched customer self-service portal serving 500K active accounts with 99.95% uptime.",
                "<b>Full-Stack Developer</b> | InnovateSoft | Jun 2017 - Dec 2019",
                "Created RESTful endpoints in Node.js and interactive client interfaces in React.",
                "## EDUCATION",
                "B.S. in Computer Science | Penn State University | Graduated 2017"
            ]
        },
        {
            "name": "Spencer Taylor",
            "role": "Machine Learning Engineer",
            "email": "spencer.taylor@cognitivesys.ai",
            "phone": "555-010-0017",
            "blocks": [
                "## SUMMARY",
                "AI/ML Engineer with 4 years deploying neural networks and classical predictive models to production. Proficient in PyTorch, Scikit-Learn, and Python.",
                "## SKILLS",
                "ML: Python, PyTorch, TensorFlow, Scikit-Learn, Pandas, Docker, FastAPI, NLP",
                "## EXPERIENCE",
                "<b>ML Engineer</b> | CognitiveSys AI | Jul 2021 - Present",
                "Trained recommendation systems increasing user click-through rates by 31% across e-commerce product pages.",
                "<b>Junior Data Scientist</b> | AlgoDynamics | Jan 2020 - Jun 2021",
                "Engineered feature pipelines and conducted cross-validation for predictive risk models.",
                "## EDUCATION",
                "M.S. in Computer Science | University of Wisconsin-Madison | Graduated 2020"
            ]
        },
        {
            "name": "Kendall Moore",
            "role": "Backend Developer",
            "email": "kendall.m@coreplatform.dev",
            "phone": "555-010-0018",
            "blocks": [
                "## SUMMARY",
                "Backend developer with 5 years experience designing resilient APIs, microservices, and database schemas with Python and Go.",
                "## SKILLS",
                "Backend: Python, Django, Go, PostgreSQL, Redis, Docker, Git, RESTful APIs",
                "## EXPERIENCE",
                "<b>Backend Developer</b> | CorePlatform | Sep 2020 - Present",
                "Refactored legacy monolith into modular microservices with 99.9% uptime SLA and reduced test cycle duration.",
                "<b>Software Engineer</b> | CodeBase Ltd | Feb 2019 - Aug 2020",
                "Maintained relational database schemas and created REST APIs in Django.",
                "## EDUCATION",
                "B.S. in Computer Engineering | University of Colorado Boulder | Graduated 2019"
            ]
        },
        {
            "name": "Reese Jackson",
            "role": "Senior Full-Stack Engineer",
            "email": "reese.jackson@modernstack.tech",
            "phone": "555-010-0019",
            "blocks": [
                "## SUMMARY",
                "Full-stack engineer with 8 years building scalable SaaS applications. Deep knowledge of React, Python, PostgreSQL, and cloud deployments.",
                "## SKILLS",
                "Languages & Tech: React, TypeScript, Python, FastAPI, Node.js, PostgreSQL, Docker, AWS, Tailwind",
                "## EXPERIENCE",
                "<b>Principal Software Engineer</b> | ModernStack | Aug 2019 - Present",
                "Guided technical roadmap and mentored team of 10 engineers building high-load financial dashboards.",
                "<b>Full-Stack Developer</b> | AgileForge | May 2016 - Jul 2019",
                "Built responsive dashboards in React and integrated secure backend REST endpoints in Python.",
                "## EDUCATION",
                "B.Tech in Computer Science | Cornell University | Graduated 2016"
            ]
        },
        {
            "name": "Parker Martin",
            "role": "DevOps Engineer",
            "email": "parker.martin@infraflow.org",
            "phone": "555-010-0020",
            "blocks": [
                "## SUMMARY",
                "DevOps engineer with 6 years optimizing CI/CD workflows, containerized environments, and cloud infrastructure monitoring.",
                "## SKILLS",
                "DevOps: AWS, Kubernetes, Docker, Terraform, CI/CD, Linux, Prometheus, Python",
                "## EXPERIENCE",
                "<b>Senior DevOps Engineer</b> | InfraFlow | Mar 2020 - Present",
                "Designed GitOps-driven deployment workflow using ArgoCD and Kubernetes, cutting deploy lead time by 80%.",
                "<b>Systems Administrator</b> | TechBase | Jan 2018 - Feb 2020",
                "Managed Linux server clusters and configured automated monitoring with Prometheus and Grafana.",
                "## EDUCATION",
                "B.S. in Information Technology | University of Maryland | Graduated 2018"
            ]
        }
    ]

    for candidate in candidates:
        name = candidate["name"]
        role = candidate["role"]
        filename = f"{name.replace(' ', '_')}_{role.replace(' ', '_')}.pdf"
        contact = f"{candidate['email']} | {candidate['phone']}"
        create_resume(filename, name, contact, candidate["blocks"])

    print(f"Successfully generated {len(candidates)} diverse, realistic sample resumes in sample_resumes/.")

if __name__ == '__main__':
    generate_20_resumes()
