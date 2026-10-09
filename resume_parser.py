import os
import io
import re
import datetime
import hashlib
from functools import lru_cache
import numpy as np

# Suppress Hugging Face & Tokenizer verbose warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

import logging
import warnings
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# Fast PDF & DOCX reading
try:
    from pypdf import PdfReader
    USE_PYPDF = True
except ImportError:
    try:
        import pdfplumber
        USE_PYPDF = False
    except ImportError:
        USE_PYPDF = None

try:
    from docx import Document
    USE_DOCX = True
except ImportError:
    USE_DOCX = False

# Top-level sklearn vectorizer for zero-latency imports during request cycle
from sklearn.feature_extraction.text import TfidfVectorizer

# ---------------------------------------------------------------------------
# Instant Pre-Compiled Stopwords & Fast Alias Mapper
# ---------------------------------------------------------------------------
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but',
    'by', 'can', 'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for',
    'from', 'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself',
    'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'just',
    'me', 'more', 'most', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only',
    'or', 'other', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she', 'should',
    'so', 'some', 'such', 'than', 'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then',
    'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up',
    'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom',
    'why', 'will', 'with', 'you', 'your', 'yours', 'yourself', 'yourselves', 'also', 'well',
    'using', 'used', 'worked', 'working', 'responsible', 'duties', 'project', 'projects'
}

ALIAS_MAP = {
    'c++': 'cpp',
    'c#': 'csharp',
    '.net': 'dotnet',
    'node.js': 'nodejs',
    'react.js': 'reactjs',
    'vue.js': 'vuejs',
    'angular.js': 'angularjs',
    'ci/cd': 'cicd',
    'ui/ux': 'uiux',
    'restful': 'rest',
    'rest api': 'restapi'
}

# ---------------------------------------------------------------------------
# Smart Related-Skills Adjacency Map
# Skills in the same group are considered "related" / adjacent.
# If a job requires skill A and a candidate has skill B where B is in
# A's related set, it counts as a partial (related) match instead of missing.
# ---------------------------------------------------------------------------
RELATED_SKILLS_GROUPS = [
    # ML / AI Frameworks
    {'pytorch', 'tensorflow', 'keras', 'mxnet', 'jax', 'caffe', 'theano', 'onnx', 'deep learning'},
    # ML Libraries & Tools
    {'scikit-learn', 'sklearn', 'xgboost', 'lightgbm', 'catboost', 'machine learning', 'ml'},
    # NLP
    {'nlp', 'natural language processing', 'spacy', 'nltk', 'huggingface', 'transformers', 'bert', 'gpt', 'llm'},
    # Computer Vision
    {'opencv', 'computer vision', 'image processing', 'yolo', 'detectron'},
    # Python ecosystem
    {'python', 'python3', 'cpython', 'anaconda', 'jupyter'},
    # JavaScript ecosystem
    {'javascript', 'typescript', 'js', 'es6', 'ecmascript'},
    # Frontend Frameworks
    {'react', 'reactjs', 'nextjs', 'next', 'gatsby', 'preact'},
    {'angular', 'angularjs', 'angular2'},
    {'vue', 'vuejs', 'nuxt', 'nuxtjs'},
    {'svelte', 'sveltekit'},
    # CSS / UI
    {'css', 'sass', 'scss', 'less', 'tailwind', 'tailwindcss', 'bootstrap', 'styled-components'},
    # Backend Python
    {'flask', 'django', 'fastapi', 'tornado', 'pyramid', 'bottle'},
    # Backend JS
    {'nodejs', 'express', 'expressjs', 'nestjs', 'koa', 'hapi', 'deno', 'bun'},
    # Java ecosystem
    {'java', 'spring', 'spring boot', 'springboot', 'hibernate', 'maven', 'gradle'},
    # C-family
    {'cpp', 'c', 'csharp', 'rust', 'go', 'golang'},
    # .NET
    {'dotnet', 'csharp', 'aspnet', 'asp.net', 'blazor', 'entity framework'},
    # SQL Databases
    {'sql', 'mysql', 'postgresql', 'postgres', 'sqlite', 'mariadb', 'oracle', 'mssql', 'sql server'},
    # NoSQL Databases
    {'mongodb', 'nosql', 'dynamodb', 'couchdb', 'firebase', 'firestore', 'cassandra', 'couchbase'},
    # In-memory / Cache
    {'redis', 'memcached', 'caching', 'elasticsearch', 'elastic'},
    # Cloud - AWS
    {'aws', 'amazon web services', 'ec2', 's3', 'lambda', 'cloudformation', 'sagemaker'},
    # Cloud - GCP
    {'gcp', 'google cloud', 'bigquery', 'cloud functions', 'google cloud platform'},
    # Cloud - Azure
    {'azure', 'microsoft azure', 'azure devops', 'azure functions'},
    # Cloud general
    {'aws', 'gcp', 'azure', 'cloud', 'cloud computing'},
    # Containers & Orchestration
    {'docker', 'kubernetes', 'k8s', 'container', 'containerization', 'podman', 'helm'},
    # CI/CD
    {'cicd', 'jenkins', 'github actions', 'gitlab ci', 'circleci', 'travis', 'bamboo', 'argo'},
    # IaC
    {'terraform', 'ansible', 'puppet', 'chef', 'cloudformation', 'pulumi', 'infrastructure as code'},
    # Version Control
    {'git', 'github', 'gitlab', 'bitbucket', 'svn', 'version control'},
    # Data Engineering
    {'spark', 'pyspark', 'hadoop', 'hive', 'kafka', 'airflow', 'luigi', 'data pipeline', 'etl'},
    # Data Viz
    {'tableau', 'power bi', 'powerbi', 'matplotlib', 'plotly', 'seaborn', 'data visualization', 'grafana', 'd3', 'd3js'},
    # Data Science
    {'pandas', 'numpy', 'scipy', 'data analysis', 'data science', 'statistics'},
    # Mobile
    {'react native', 'flutter', 'ionic', 'xamarin', 'mobile development'},
    {'swift', 'ios', 'objective-c', 'xcode'},
    {'kotlin', 'android', 'java'},
    # APIs
    {'rest', 'restapi', 'graphql', 'grpc', 'soap', 'api', 'api development', 'microservices'},
    # Testing
    {'jest', 'mocha', 'cypress', 'selenium', 'pytest', 'unittest', 'testing', 'unit testing', 'tdd'},
    # Security
    {'cybersecurity', 'security', 'penetration testing', 'owasp', 'encryption', 'soc2'},
    # Agile
    {'agile', 'scrum', 'kanban', 'jira', 'confluence', 'sprint'},
    # Linux / OS
    {'linux', 'ubuntu', 'centos', 'debian', 'bash', 'shell', 'shell scripting'},
    # Messaging
    {'rabbitmq', 'kafka', 'sqs', 'pub/sub', 'message queue', 'celery'},
    # PHP ecosystem
    {'php', 'laravel', 'symfony', 'wordpress', 'drupal'},
    # Ruby ecosystem
    {'ruby', 'rails', 'ruby on rails', 'sinatra'},
    # R ecosystem
    {'r', 'rstudio', 'tidyverse', 'ggplot2', 'shiny'},
]

def _build_related_lookup(groups):
    """Build a O(1) lookup: skill -> set of all related skills (excluding itself)."""
    lookup = {}
    for group in groups:
        for skill in group:
            if skill not in lookup:
                lookup[skill] = set()
            lookup[skill].update(group - {skill})
    return lookup

RELATED_SKILLS_LOOKUP = _build_related_lookup(RELATED_SKILLS_GROUPS)

COMBINED_ALIAS_PATTERN = re.compile(
    r'\b(?:c\+\+|c#|\.net|node\.js|react\.js|vue\.js|angular\.js|ci/cd|ui/ux|restful|rest api)\b',
    re.IGNORECASE
)

SUPPORTED_EXTENSIONS = {'pdf', 'docx'}

# ---------------------------------------------------------------------------
# Lazy-Loaded Dense Transformer Core with Background Pre-Warm Support
# ---------------------------------------------------------------------------
_semantic_model = None
_model_attempted = False
_EMBEDDING_CACHE = {}  # key: sha256 hex digest -> numpy array (1, dim)

def get_semantic_model():
    """Thread-safe lazy loader for SentenceTransformer with PyTorch optimizations."""
    global _semantic_model, _model_attempted
    if _semantic_model is None and not _model_attempted:
        _model_attempted = True
        try:
            import torch
            torch.set_num_threads(min(8, os.cpu_count() or 4))
            from sentence_transformers import SentenceTransformer
            _semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
            # Warm up JIT / CUDA / CPU layers
            with torch.inference_mode():
                _semantic_model.encode(["warmup sentence"], show_progress_bar=False)
        except Exception as e:
            print(f"Warning: Dense Transformer model unavailable: {e}")
            _semantic_model = None
    return _semantic_model


def warmup_semantic_model():
    """Background worker entry point to initialize model during app startup."""
    try:
        get_semantic_model()
    except Exception as e:
        print(f"Model warm-up background task completed with notice: {e}")


def _hash_text(text):
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()


# ---------------------------------------------------------------------------
# High-Speed In-Memory & File Text Extraction
# ---------------------------------------------------------------------------
def extract_text(file_source, file_type):
    """Fast in-memory (bytes/stream) or file-path text extraction."""
    text = []
    try:
        if isinstance(file_source, bytes):
            source = io.BytesIO(file_source)
        elif hasattr(file_source, 'read'):
            source = file_source
        else:
            source = file_source

        if file_type == 'pdf':
            if USE_PYPDF:
                reader = PdfReader(source)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text.append(extracted)
            elif USE_PYPDF is False:
                import pdfplumber
                with pdfplumber.open(source) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text.append(extracted)
        elif file_type == 'docx':
            if USE_DOCX:
                doc = Document(source)
                text = [p.text for p in doc.paragraphs if p.text]
            else:
                raise ValueError("python-docx is not installed")
        else:
            raise ValueError(f"Unsupported file type: .{file_type}")
    except Exception as e:
        source_name = file_source if isinstance(file_source, str) else file_type
        print(f"Error parsing {source_name}: {e}")
    return "\n".join(text)


# ---------------------------------------------------------------------------
# Single-Pass Fast NLP Cleaning & Technical Term Preservation
# ---------------------------------------------------------------------------
def clean_text(text):
    """Single-pass token cleaning with O(1) stop-word rejection and alias preserving."""
    if not text:
        return ""
    # Single regex replacement for all technical aliases
    lowered = COMBINED_ALIAS_PATTERN.sub(
        lambda m: ALIAS_MAP.get(m.group(0).lower(), m.group(0).lower()),
        text.lower()
    )
    cleaned_tokens = re.sub(r'[^a-z0-9\s]', ' ', lowered).split()
    words = [w for w in cleaned_tokens if w not in STOP_WORDS and len(w) > 1]
    return " ".join(words)


# ---------------------------------------------------------------------------
# High-Performance Sparse TF-IDF Scoring
# ---------------------------------------------------------------------------
def calculate_tfidf_scores(cleaned_resumes, cleaned_job):
    """Sublinear TF-IDF with Unigram + Bigram matching and sparse dot product."""
    if not cleaned_job or not any(cleaned_resumes):
        return [0.0] * len(cleaned_resumes)

    corpus = [cleaned_job] + cleaned_resumes
    vectorizer = TfidfVectorizer(
        sublinear_tf=True,
        ngram_range=(1, 2),
        max_features=5000
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)

    job_vector = tfidf_matrix[0:1]
    resume_vectors = tfidf_matrix[1:]

    # Since TF-IDF vectors are L2-normalized by default, cosine similarity is direct dot product
    similarities = job_vector.dot(resume_vectors.T).toarray().ravel()
    return [round(float(score) * 100, 2) for score in similarities]


# ---------------------------------------------------------------------------
# Fast Vectorized Dense Semantic Embeddings (SHA-256 Cached)
# ---------------------------------------------------------------------------
def calculate_dense_scores(resume_texts, job_text):
    """High-speed vectorized dense embeddings with SHA-256 caching."""
    model = get_semantic_model()
    if not model or not job_text or not any(resume_texts):
        return [0.0] * len(resume_texts)

    import torch

    # Truncate text to 1500 chars (most semantically rich sections) to minimize transformer latency
    trunc_job = job_text[:1000]
    trunc_resumes = [t[:1500] for t in resume_texts]

    job_key = _hash_text(trunc_job)
    resume_keys = [_hash_text(t) for t in trunc_resumes]

    # Collect texts needing embedding
    uncached_items = []
    if job_key not in _EMBEDDING_CACHE:
        uncached_items.append((job_key, trunc_job))
    
    for key, text in zip(resume_keys, trunc_resumes):
        if key not in _EMBEDDING_CACHE:
            uncached_items.append((key, text))

    if uncached_items:
        texts_to_encode = [item[1] for item in uncached_items]
        with torch.inference_mode():
            new_embs = model.encode(
                texts_to_encode,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
        for (key, _), emb in zip(uncached_items, new_embs):
            _EMBEDDING_CACHE[key] = emb

    job_emb = _EMBEDDING_CACHE[job_key]
    resume_embs = np.vstack([_EMBEDDING_CACHE[k] for k in resume_keys])

    # Vectorized cosine similarity via normalized dot product
    sims = np.dot(resume_embs, job_emb)
    return [round(float(max(0.0, s)) * 100, 2) for s in sims]


# ---------------------------------------------------------------------------
# Dynamic Hybrid Reciprocal & Weight Fusion
# ---------------------------------------------------------------------------
def compute_rrf_scores(tfidf_scores, dense_scores, job_skills=None, cleaned_resumes=None, w_tfidf=0.40, w_skill=0.35, w_dense=0.25, skill_matches=None, related_skill_counts=None):
    """Dynamic blend of TF-IDF, skill overlap, and dense vector scores with customizable weights.
    
    related_skill_counts: list of int, count of related (adjacent) skills per candidate.
                          Related skills receive 0.5x credit towards the skill score.
    """
    if not tfidf_scores:
        return []

    RELATED_CREDIT = 0.9  # Partial credit multiplier for related skills

    # Calculate skill overlap score per candidate if available
    skill_scores = []
    if skill_matches is not None:
        total_skills = len(job_skills) if job_skills else 1
        for i, matched in enumerate(skill_matches):
            exact_count = len(matched)
            related_count = related_skill_counts[i] if related_skill_counts and i < len(related_skill_counts) else 0
            effective = exact_count + (related_count * RELATED_CREDIT)
            ratio = (effective / total_skills) * 100.0 if total_skills else 0.0
            skill_scores.append(ratio)
    elif job_skills and cleaned_resumes:
        for clean_r in cleaned_resumes:
            if not job_skills:
                skill_scores.append(0.0)
            else:
                tokens_set = set(clean_r.split())
                matched_count = 0
                for s in job_skills:
                    if not s:
                        continue
                    if ' ' in s:
                        if s in clean_r:
                            matched_count += 1
                    elif s in tokens_set:
                        matched_count += 1
                ratio = (matched_count / len(job_skills)) * 100.0
                skill_scores.append(ratio)
    else:
        skill_scores = [0.0] * len(tfidf_scores)

    has_dense = any(d > 0 for d in dense_scores)

    # Normalize weights
    total_w = w_tfidf + w_skill + (w_dense if has_dense else 0.0)
    if total_w <= 0:
        total_w = 1.0

    norm_w_tf = w_tfidf / total_w
    norm_w_sk = w_skill / total_w
    norm_w_d = (w_dense / total_w) if has_dense else 0.0

    blended_scores = []
    for i in range(len(tfidf_scores)):
        tf_s = tfidf_scores[i]
        sk_s = skill_scores[i]
        d_s = dense_scores[i] if has_dense else tf_s

        final_score = ((norm_w_tf * tf_s) + (norm_w_sk * sk_s) + (norm_w_d * d_s)) * 1.25
        blended_scores.append(round(min(100.0, max(0.0, final_score)), 2))

    return blended_scores


# ---------------------------------------------------------------------------
# Regex-Based Named Entity Recognition (NER)
# Extracts degrees, university names, and job role titles without spaCy
# ---------------------------------------------------------------------------
DEGREE_PATTERN = re.compile(
    r'\b('
    r'(?:Bachelor|Master|Doctor|Associate)(?:\'s)?\s+(?:of\s+)?(?:Science|Arts|Engineering|Technology|Business|Administration|Computer\s+Science|Information\s+Technology|Commerce|Law|Medicine|Education|Fine\s+Arts|Design|Philosophy)'
    r'|B\.?\s*(?:Tech|Sc|E|A|Com|Arch|Des|Pharm|Ed)'
    r'|M\.?\s*(?:Tech|Sc|E|A|Com|BA|CA|Phil|Des|Pharm|Ed|S)'
    r'|Ph\.?\s*D\.?'
    r'|MBA|BBA|BCA|MCA|BE|ME|BSc|MSc|BA|MA'
    r'|Diploma(?:\s+in\s+[\w\s]{3,30})?'
    r'|(?:12th|10th|HSC|SSC|CBSE|ICSE|ISC|IB)'
    r')\b',
    re.IGNORECASE
)

UNIVERSITY_PATTERN = re.compile(
    r'(?:'
    r'(?:University|Institute|College|School|Academy)\s+of\s+[\w\s]{3,40}'
    r'|(?:IIT|NIT|IIIT|BITS|VIT|SRM|MIT|KIIT|Amity|Manipal|Stanford|Harvard|Oxford|Cambridge|Berkeley|Cornell|CMU|Caltech|Princeton|Yale|Columbia|Georgia\s+Tech|UCLA|USC|NYU|Purdue)\b[\w\s]{0,20}'
    r'|[\w\s]{3,30}(?:University|Institute|College|Polytechnic)'
    r')',
    re.IGNORECASE
)

JOB_ROLE_PATTERN = re.compile(
    r'\b('
    r'(?:Senior|Junior|Lead|Principal|Staff|Chief|Head|Director|VP|Vice\s+President|Manager|Associate|Assistant)?\s*'
    r'(?:Software|Full[\s-]?Stack|Front[\s-]?End|Back[\s-]?End|DevOps|Cloud|Data|Machine\s+Learning|ML|AI|Mobile|iOS|Android|Web|QA|Test|Security|Network|System|Database|Platform|Product|UI/?UX|Research|Solutions|IT|Business|Marketing|Sales|HR|Project|Program|Technical|Engineering)?\s*'
    r'(?:Engineer|Developer|Architect|Analyst|Scientist|Designer|Consultant|Administrator|Specialist|Coordinator|Intern|Trainee|Officer|Manager|Lead|Tester)'
    r')\b',
    re.IGNORECASE
)

SOFT_SKILLS_PATTERN = re.compile(
    r'\b(leadership|communication|teamwork|problem[\s-]?solving|time[\s-]?management|agile|mentoring|analytical|adaptability|critical[\s-]?thinking|collaboration|creativity|conflict[\s-]?resolution|public[\s-]?speaking|empathy|strategic[\s-]?planning)\b',
    re.IGNORECASE
)

ACTION_VERBS_PATTERN = re.compile(
    r'\b(engineered|architected|orchestrated|spearheaded|developed|optimized|implemented|managed|led|directed|designed|reduced|increased|accelerated|automated|integrated|transformed|streamlined)\b',
    re.IGNORECASE
)

CERTIFICATIONS_PATTERN = re.compile(
    r'\b(aws certified|azure|gcp|cisco ccna|comptia|pmp|scrum master|six sigma|itil|cissp|cfa|cpa|certified scrum|google cloud certified)\b',
    re.IGNORECASE
)

QUANTIFIABLE_PATTERN = re.compile(
    r'(?:\$[\d,]+(?:\.\d+)?(?:[kKmMbB])?)|(?:\b\d+(?:\.\d+)?%)|(?:\b\d+(?:[kKmM])\b)',
    re.IGNORECASE
)

LANGUAGES_PATTERN = re.compile(
    r'\b(english|spanish|french|german|mandarin|chinese|hindi|arabic|portuguese|russian|japanese|korean|italian|dutch)\b',
    re.IGNORECASE
)

DOMAINS = {
    "Finance & FinTech": [r'\bfinance\b', r'\bfintech\b', r'\bbanking\b', r'\binvestment\b', r'\btrading\b', r'\bblockchain\b'],
    "Healthcare & MedTech": [r'\bhealthcare\b', r'\bmedical\b', r'\bclinical\b', r'\bhipaa\b', r'\behr\b', r'\bhospital\b', r'\bpharma\b'],
    "E-Commerce & Retail": [r'\be-?commerce\b', r'\bretail\b', r'\bshopify\b', r'\bmagento\b', r'\bb2c\b', r'\bpoint of sale\b'],
    "Cybersecurity": [r'\bcybersecurity\b', r'\bpenetration testing\b', r'\bvulnerability\b', r'\bfirewalls\b', r'\bmalware\b', r'\bincident response\b'],
    "AI & Data Science": [r'\bmachine learning\b', r'\bartificial intelligence\b', r'\bdeep learning\b', r'\bnlp\b', r'\bcomputer vision\b', r'\bdata science\b'],
    "Cloud & DevOps": [r'\bdevops\b', r'\bkubernetes\b', r'\bdocker\b', r'\bci/cd\b', r'\bmicroservices\b', r'\bterraform\b']
}

def extract_entities(resume_text):
    """Fast regex-based NER: extracts degrees, universities, and job roles from resume text."""
    if not resume_text:
        return {"degrees": [], "universities": [], "job_roles": []}

    text = resume_text[:5000]  # Limit to first 5000 chars for speed

    # Extract unique degrees
    degrees = list({m.group(0).strip() for m in DEGREE_PATTERN.finditer(text)})

    # Extract unique universities
    universities = list({m.group(0).strip() for m in UNIVERSITY_PATTERN.finditer(text)})
    # Filter very short matches
    universities = [u for u in universities if len(u) > 5]

    # Extract unique job roles
    roles = list({m.group(0).strip() for m in JOB_ROLE_PATTERN.finditer(text)})
    # Filter very short / noise matches
    roles = [r for r in roles if len(r) > 4]

    # Extract soft skills
    soft_skills = list({m.group(0).strip().title() for m in SOFT_SKILLS_PATTERN.finditer(text)})
    
    # Extract action verbs (Impact language)
    action_verbs = list({m.group(0).strip().title() for m in ACTION_VERBS_PATTERN.finditer(text)})

    # Extract quantifiable metrics (percentages, currency, scale)
    metrics = list({m.group(0).strip().upper() for m in QUANTIFIABLE_PATTERN.finditer(text)})

    # Extract certifications
    certs = list({m.group(0).strip().title() for m in CERTIFICATIONS_PATTERN.finditer(text)})

    # Extract languages
    languages = list({m.group(0).strip().title() for m in LANGUAGES_PATTERN.finditer(text)})

    # Classify Industry Domains based on keyword density
    domain_scores = {}
    for domain, patterns in DOMAINS.items():
        score = sum(len(re.findall(p, text, re.IGNORECASE)) for p in patterns)
        if score > 1: # Require at least 2 mentions to confidently classify
            domain_scores[domain] = score
    top_domains = [d[0] for d in sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)[:2]]

    return {
        "degrees": sorted(degrees)[:8],
        "universities": sorted(universities)[:5],
        "job_roles": sorted(roles)[:8],
        "soft_skills": sorted(soft_skills)[:6],
        "action_verbs": sorted(action_verbs)[:6],
        "metrics": sorted(metrics)[:5],
        "certifications": sorted(certs)[:4],
        "languages": sorted(languages)[:4],
        "domains": top_domains
    }


# ---------------------------------------------------------------------------
# Pre-Compiled Patterns & Insights
# ---------------------------------------------------------------------------
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_PATTERN = re.compile(r'(?:\+\d{1,3}[-.\s]?)?(?:\(\d{2,4}\)[-.\s]?)?\b\d{3,5}[-.\s]?\d{3,5}(?:[-.\s]?\d{3,5})?\b')
CLAIMED_EXP_PATTERN = re.compile(r'(\d+)\+?\s*years?\s*(?:of)?\s*(?:experience|exp)', re.IGNORECASE)
DATE_RANGE_PATTERN = re.compile(r'([a-zA-Z]{3,9})\s*(\d{4})\s*[-–—to]+\s*([a-zA-Z]{3,9}|\bpresent\b|\bcurrent\b)?\s*(\d{4})?', re.IGNORECASE)
SPLIT_PHRASES_PATTERN = re.compile(r'[,\n;•|/&]+|\band\b|\bor\b')
FLUFF_PATTERN = re.compile(r'looking for a|looking for|we need|developer with|experience for|experience in|years of|years|strong knowledge in|proficiency in|must have', re.IGNORECASE)

GENERIC_NOISE_WORDS = {
    'experience', 'years', 'year', 'work', 'working', 'strong', 'good',
    'knowledge', 'ability', 'skills', 'skill', 'required', 'preferred',
    'must', 'plus', 'looking', 'candidate', 'candidates', 'team', 'role'
}

MONTH_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
    'nov': 11, 'november': 11, 'dec': 12, 'december': 12
}


def _extract_skill_phrases(text):
    if not text:
        return set()
    cleaned = FLUFF_PATTERN.sub(',', text.lower())
    raw_phrases = SPLIT_PHRASES_PATTERN.split(cleaned)
    phrases = set()

    for phrase in raw_phrases:
        cleaned_phrase = clean_text(phrase).strip()
        if cleaned_phrase:
            words = cleaned_phrase.split()
            if 1 <= len(words) <= 3 and cleaned_phrase not in GENERIC_NOISE_WORDS:
                phrases.add(cleaned_phrase)
    return phrases


def _has_skill_in_resume(skill, tokens_set, cleaned_resume):
    """Check if a skill (single-word or multi-word phrase) is present in the resume."""
    if ' ' in skill:
        return skill in cleaned_resume
    return skill in tokens_set


def extract_keyword_insights(cleaned_resume, job_skills):
    """Smart skill matching with related-skill detection.
    
    Returns three categories:
      - matched_skills: exact matches found in resume
      - related_skills: not exact match, but a related/adjacent skill was found
                        (e.g., job wants TensorFlow, candidate has PyTorch)
      - missing_skills: no match and no related skill found
    
    Each related skill entry is a dict: {"required": "tensorflow", "found": "pytorch"}
    """
    if not job_skills:
        return {"matched_skills": [], "related_skills": [], "missing_skills": []}

    tokens_set = set(cleaned_resume.split())
    matched_skills = []
    related_skills = []
    missing_skills = []

    for s in job_skills:
        if not s:
            continue

        # Check for exact match first
        if _has_skill_in_resume(s, tokens_set, cleaned_resume):
            matched_skills.append(s)
            continue

        # Check for related/adjacent skill match
        related_set = RELATED_SKILLS_LOOKUP.get(s, set())
        found_related = None
        if related_set:
            for related in related_set:
                if _has_skill_in_resume(related, tokens_set, cleaned_resume):
                    found_related = related
                    break

        if found_related:
            related_skills.append({"required": s, "found": found_related})
        else:
            missing_skills.append(s)

    return {
        "matched_skills": sorted(matched_skills),
        "related_skills": sorted(related_skills, key=lambda x: x["required"]),
        "missing_skills": sorted(missing_skills)
    }


def extract_contact_info(resume_text):
    """Extract contact info scoped to the top 1500 chars (resume header) for fast execution."""
    header_text = resume_text[:1500] if len(resume_text) > 1500 else resume_text
    email_match = EMAIL_PATTERN.search(header_text)
    phone_match = PHONE_PATTERN.search(header_text)

    email = email_match.group(0) if email_match else "Not found"
    phone = "Not found"
    if phone_match:
        candidate = phone_match.group(0).strip()
        digits = re.sub(r'\D', '', candidate)
        if 7 <= len(digits) <= 15:
            phone = candidate

    return {"email": email, "phone": phone}


def analyze_career_velocity(resume_text, job_roles):
    """Detects 'Fast Trackers' based on role progressions or timeframes."""
    is_fast_tracker = False
    velocity_notes = "Normal progression."
    
    # Simple heuristic: If they have 'Senior', 'Lead', or 'Manager' but under 4 years of provable experience
    senior_roles = [r for r in job_roles if 'senior' in r.lower() or 'lead' in r.lower() or 'manager' in r.lower()]
    if senior_roles:
        timeline = audit_experience_timeline(resume_text)
        if 0 < timeline['provable_years'] <= 4:
            is_fast_tracker = True
            velocity_notes = f"Fast Tracker: Reached {senior_roles[0]} in ~{timeline['provable_years']} years."
            
    return {"is_fast_tracker": is_fast_tracker, "velocity_notes": velocity_notes}


def profile_soft_skills(soft_skills_list, resume_text):
    """Scores soft skills based on mentions and presence."""
    profile = {
        "Leadership": "Low",
        "Communication": "Low",
        "Problem Solving": "Low"
    }
    
    text_lower = resume_text.lower()
    
    if any(s in text_lower for s in ['lead', 'manage', 'mentor', 'guide', 'direct', 'leadership']):
        profile["Leadership"] = "High" if text_lower.count('lead') > 2 else "Medium"
        
    if any(s in text_lower for s in ['communicate', 'present', 'collaborate', 'team', 'cross-functional', 'communication']):
        profile["Communication"] = "High" if text_lower.count('team') > 2 else "Medium"
        
    if any(s in text_lower for s in ['solve', 'optimize', 'troubleshoot', 'resolve', 'analyze', 'problem solving']):
        profile["Problem Solving"] = "High" if text_lower.count('resolv') > 2 else "Medium"
        
    return profile


def generate_outreach_email(candidate_name, score, matched, missing):
    """Generates a personalized draft outreach email based on candidate match."""
    first_name = candidate_name.split('_')[0].split('.')[0] if candidate_name else "Candidate"
    
    if score >= 75:
        return f"Hi {first_name},\n\nI was incredibly impressed by your background, particularly your experience with {', '.join(matched[:2])}. You seem like a fantastic fit for our open role. Would you have 15 minutes for a quick chat this week?\n\nBest,\n[Your Name]"
    elif score >= 50:
        return f"Hi {first_name},\n\nYour profile caught my eye! Your skills in {', '.join(matched[:2])} align well with what we're looking for. While we are also using {missing[0] if missing else 'some other tools'}, we'd love to learn more about your ability to adapt. Are you open to a brief call?\n\nBest,\n[Your Name]"
    else:
        return f"Hi {first_name},\n\nThank you for applying. While your experience with {matched[0] if matched else 'certain tools'} is notable, we are heavily focused on {missing[0] if missing else 'other core skills'} at this time. We will keep your resume on file for future opportunities.\n\nBest,\n[Your Name]"


def audit_experience_timeline(resume_text):
    claimed_match = CLAIMED_EXP_PATTERN.search(resume_text)
    claimed_years = int(claimed_match.group(1)) if claimed_match else None

    matches = DATE_RANGE_PATTERN.findall(resume_text)
    total_months = 0
    now = datetime.datetime.now()

    for start_m, start_y, end_m, end_y in matches:
        try:
            s_m = MONTH_MAP.get(start_m.lower(), 1)
            s_y = int(start_y)
            if end_m.lower() in ['present', 'current'] or not end_y:
                e_m, e_y = now.month, now.year
            else:
                e_m = MONTH_MAP.get(end_m.lower(), 12)
                e_y = int(end_y)

            months = (e_y - s_y) * 12 + (e_m - s_m)
            if 0 < months < 600:
                total_months += months
        except Exception:
            continue

    provable_years = round(total_months / 12.0, 1)
    timeline_alert = False
    alert_reason = ""

    if claimed_years is not None and (claimed_years - provable_years) > 1.5:
        timeline_alert = True
        alert_reason = f"Claimed {claimed_years} yrs exp, but job history proves ~{provable_years} yrs."

    return {
        "provable_years": provable_years,
        "claimed_years": claimed_years,
        "timeline_alert": timeline_alert,
        "alert_reason": alert_reason
    }


def analyze_culture_fit(text):
    text_lower = text.lower()
    culture_keywords = {
        'Collaborative & Team-Oriented': ['team', 'collaborate', 'together', 'cross-functional', 'mentor', 'support'],
        'Innovative & Creative': ['innovate', 'create', 'design', 'research', 'novel', 'patent', 'brainstorm'],
        'Results-Driven & Analytical': ['result', 'deliver', 'achieve', 'impact', 'increase', 'decrease', 'revenue', 'data', 'analyze'],
        'Adaptable & Agile': ['adapt', 'agile', 'flexible', 'fast-paced', 'dynamic', 'pivot', 'startup']
    }
    
    profile = {}
    total_matches = 0
    for trait, words in culture_keywords.items():
        matches = sum(1 for w in words if w in text_lower)
        total_matches += matches
        profile[trait] = matches
        
    if total_matches == 0:
        return {"alignment": "Unknown", "dominant_trait": "Generalist", "score": 0}
        
    dominant = max(profile, key=profile.get)
    score = min(100, int((total_matches / (len(text_lower.split()) + 1)) * 5000))
    alignment = "High" if score > 50 else "Medium" if score > 20 else "Low"
    
    return {
        "alignment": alignment,
        "dominant_trait": dominant,
        "score": score
    }

def predict_salary(roles, years_exp):
    base = 60000
    if years_exp > 5:
        base += 35000
    elif years_exp > 2:
        base += 15000
        
    role_str = " ".join(roles).lower()
    if 'senior' in role_str or 'architect' in role_str or 'lead' in role_str or 'manager' in role_str:
        base += 40000
    if 'data scientist' in role_str or 'machine learning' in role_str or 'ai' in role_str:
        base += 25000
    if 'engineer' in role_str or 'developer' in role_str:
        base += 15000
        
    return f"${base:,} - ${base + 20000:,}"

def build_candidate_report(filename, resume_text, cleaned_resume, job_skills, score, tfidf_score=0.0, dense_score=0.0, precomputed_insights=None):
    contact_info = extract_contact_info(resume_text)
    skill_insights = precomputed_insights if precomputed_insights is not None else extract_keyword_insights(cleaned_resume, job_skills)
    timeline_audit = audit_experience_timeline(resume_text)
    entities = extract_entities(resume_text)

    return {
        "name": filename,
        "score": score,
        "tfidf_score": tfidf_score,
        "dense_score": dense_score,
        "contact": contact_info,
        "matched_skills": skill_insights["matched_skills"],
        "related_skills": skill_insights.get("related_skills", []),
        "missing_skills": skill_insights["missing_skills"][:5],
        "entities": entities,
        "soft_skills_profile": profile_soft_skills(entities.get("soft_skills", []), resume_text),
        "velocity_analysis": analyze_career_velocity(resume_text, entities.get("job_roles", [])),
        "culture_fit": analyze_culture_fit(resume_text),
        "salary_prediction": predict_salary(entities.get("job_roles", []), timeline_audit.get("provable_years", 0)),
        "timeline_audit": timeline_audit,
        "tldr_summary": generate_tldr_summary(score, skill_insights["matched_skills"], skill_insights["missing_skills"], timeline_audit),
        "interview_questions": generate_interview_questions(skill_insights["matched_skills"], skill_insights["missing_skills"], timeline_audit),
        "outreach_email": generate_outreach_email(filename, score, skill_insights["matched_skills"], skill_insights["missing_skills"])
    }

def generate_tldr_summary(score, matched, missing, timeline_audit):
    summary = f"Candidate is a {'strong' if score > 75 else 'moderate' if score > 50 else 'weak'} fit ({score}% match). "
    if matched:
        summary += f"They have solid experience in {', '.join(matched[:3])}. "
    if missing:
        summary += f"However, they lack {', '.join(missing[:2])}. "
    if timeline_audit.get("timeline_alert"):
        summary += "Caution: There is a discrepancy in their claimed years of experience."
    return summary.strip()

def generate_interview_questions(matched, missing, timeline_audit):
    questions = []
    if missing:
        questions.append(f"We noticed you don't have explicit experience with {missing[0]}. How would you approach learning it quickly for this role?")
    if matched:
        questions.append(f"Can you walk me through a specific project where you heavily utilized {matched[0]}?")
    if len(missing) > 1:
        questions.append(f"How would you handle a task requiring {missing[1]}, given it's not currently in your tech stack?")
    if timeline_audit.get("timeline_alert"):
        questions.append("Could you clarify the exact duration of your employment at your last two positions?")
    if len(questions) < 2:
        questions.append("What do you consider your strongest technical skill and why?")
    return questions[:3]

def optimize_job_description(job_skills):
    suggestions = []
    for s in job_skills:
        related = RELATED_SKILLS_LOOKUP.get(s, set())
        if related:
            suggestions.extend(list(related)[:2])  # Just pick a couple related to suggest
    
    unique_suggestions = list(set(suggestions) - set(job_skills))
    return sorted(unique_suggestions)[:5]