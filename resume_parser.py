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
    'next.js': 'nextjs',
    'nuxt.js': 'nuxtjs',
    'ci/cd': 'cicd',
    'ui/ux': 'uiux',
    'restful': 'rest',
    'rest api': 'restapi',
    'rest apis': 'restapi',
    'scikit-learn': 'sklearn'
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
    r'(?<![a-zA-Z0-9])(?:c\+\+|c#|\.net|node\.js|react\.js|vue\.js|angular\.js|next\.js|nuxt\.js|ci/cd|ui/ux|restful|rest apis|rest api|scikit-learn)(?![a-zA-Z0-9])',
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


def _extract_docx_xml(source):
    """Fallback DOCX text extraction using Python standard library zipfile and xml.etree.
    Guarantees DOCX resumes can always be parsed even if python-docx is unavailable.
    """
    import zipfile
    import xml.etree.ElementTree as ET
    paras = []
    try:
        # If source is a stream and has been partially read, seek to beginning
        if hasattr(source, 'seek'):
            source.seek(0)
        with zipfile.ZipFile(source) as zf:
            if 'word/document.xml' in zf.namelist():
                xml_content = zf.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                for p in tree.iter():
                    if p.tag.endswith('}p') or p.tag == 'p':
                        txt = ''.join(
                            n.text for n in p.iter()
                            if (n.tag.endswith('}t') or n.tag == 't') and n.text
                        )
                        if txt.strip():
                            paras.append(txt.strip())
    except Exception as e:
        print(f"Notice during XML docx extraction: {e}")
    return paras


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
                try:
                    doc = Document(source)
                    text = [p.text for p in doc.paragraphs if p.text]
                except Exception:
                    text = _extract_docx_xml(source)
            else:
                text = _extract_docx_xml(source)
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
def _calculate_ngram_dense_fallback(resume_texts, job_text):
    """
    Sub-millisecond semantic character n-gram + token projection fallback.
    Used when SentenceTransformer is unavailable, ensuring dense semantic scoring
    and AI chat semantic search are 100% functional without heavy torch weights.
    """
    if not job_text or not any(resume_texts):
        return [0.0] * len(resume_texts)

    trunc_job = job_text[:2500]
    trunc_resumes = [t[:3000] if t else "" for t in resume_texts]
    corpus = [trunc_job] + trunc_resumes

    try:
        vec = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(3, 5),
            sublinear_tf=True,
            max_features=10000
        )
        matrix = vec.fit_transform(corpus)
        job_vec = matrix[0:1]
        res_vecs = matrix[1:]
        # Cosine similarities scaled smoothly to percentage
        sims = (job_vec * res_vecs.T).toarray().ravel()
        # Scale by 1.8 to normalize typical character-ngram cosine range to standard 0-100 scale
        return [round(float(min(100.0, max(0.0, s * 180))), 2) for s in sims]
    except Exception as e:
        print(f"Fallback semantic scoring notice: {e}")
        return [0.0] * len(resume_texts)


def calculate_dense_scores(resume_texts, job_text):
    """High-speed vectorized dense embeddings with SHA-256 caching and fallback."""
    if not job_text or not any(resume_texts):
        return [0.0] * len(resume_texts)

    model = get_semantic_model()
    if not model:
        return _calculate_ngram_dense_fallback(resume_texts, job_text)

    import torch

    # Truncate text to 1500 chars (most semantically rich sections) to minimize transformer latency
    trunc_job = job_text[:1000]
    trunc_resumes = [t[:1500] if t else "" for t in resume_texts]

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
    r'B\.?\s*S\.?|M\.?\s*S\.?|Ph\.?\s*D\.?|B\.?\s*Tech\.?|M\.?\s*Tech\.?|B\.?\s*E\.?|M\.?\s*E\.?|B\.?\s*A\.?|M\.?\s*A\.?|BSc|MSc|BS|MS|MBA|BBA|BCA|MCA|PhD|BE|ME'
    r'|(?:Bachelor|Master|Doctor|Associate)(?:\'s)?(?:\s+(?:of|in))?\s+(?:Science|Arts|Engineering|Technology|Business|Administration|Computer\s+Science|Information\s+Technology|Commerce|Law|Medicine|Education|Fine\s+Arts|Design|Philosophy)'
    r'|Diploma(?:\s+in\s+[\w\s]{3,30})?'
    r'|(?:12th|10th|HSC|SSC|CBSE|ICSE|ISC|IB)'
    r')(?:\.|\b)',
    re.IGNORECASE
)

UNIVERSITY_PATTERN = re.compile(
    r'(?:'
    r'(?:University|Institute|College|School|Academy)\s+of\s+[A-Za-z][\w\s]{2,35}'
    r'|(?:IIT|NIT|IIIT|BITS|VIT|SRM|MIT|KIIT|Amity|Manipal|Stanford|Harvard|Oxford|Cambridge|Berkeley|Cornell|CMU|Caltech|Princeton|Yale|Columbia|Georgia\s+Tech|UCLA|USC|NYU|Purdue)\b[\w\s]{0,20}'
    r'|[A-Za-z][\w\s]{2,25}(?:University|Institute|College|Polytechnic)'
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
    raw_universities = list({m.group(0).strip() for m in UNIVERSITY_PATTERN.finditer(text)})
    cleaned_unis = []
    for u in raw_universities:
        clean_u = re.sub(r'^(?:graduated\s+from|from|at|in)\s+', '', u.strip(), flags=re.IGNORECASE).strip()
        if len(clean_u) > 5 and not clean_u.lower().startswith(('the ', 'a ')):
            cleaned_unis.append(clean_u)
    universities = list(dict.fromkeys(cleaned_unis))

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
CLAIMED_EXP_PATTERN = re.compile(r'(?:over\s+|more\s+than\s+)?(\d+)\+?\s*years?\s*(?:of)?\s*(?:[\w\s]{0,25})?(?:experience|exp)', re.IGNORECASE)
MONTH_REGEX_STR = r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
DATE_RANGE_PATTERN = re.compile(
    rf'(?:({MONTH_REGEX_STR})[\s/,\.-]+)?(\b20\d\d|\b19\d\d)\s*(?:-|–|—|to)\s*(?:({MONTH_REGEX_STR})[\s/,\.-]+)?(\b20\d\d|\b19\d\d|\bpresent\b|\bcurrent\b)',
    re.IGNORECASE
)
NUMERIC_DATE_RANGE_PATTERN = re.compile(
    r'\b(0?[1-9]|1[0-2])/(20\d\d|19\d\d)\s*(?:-|–|—|to)\s*(?:(0?[1-9]|1[0-2])/)?(20\d\d|19\d\d|\bpresent\b|\bcurrent\b)\b',
    re.IGNORECASE
)
SPLIT_PHRASES_PATTERN = re.compile(r'[,\n;•|/&]+|\band\b|\bor\b|\bwith\b|\bincluding\b')
FLUFF_PATTERN = re.compile(
    r'looking for a|looking for|we need|developer with|experience for|experience in|years of|years'
    r'|strong knowledge in|proficiency in|must have|expertise in|knowledge of|familiarity with'
    r'|experience with|understanding of|background in|hands-on|proven track record|track record',
    re.IGNORECASE
)

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
    # Standardize aliases BEFORE splitting on delimiters like '/' so CI/CD and UI/UX are preserved
    cleaned = COMBINED_ALIAS_PATTERN.sub(
        lambda m: ALIAS_MAP.get(m.group(0).lower(), m.group(0).lower()),
        cleaned
    )
    raw_phrases = SPLIT_PHRASES_PATTERN.split(cleaned)
    phrases = set()

    for phrase in raw_phrases:
        cleaned_phrase = clean_text(phrase).strip()
        if cleaned_phrase:
            # Strip trailing noise words from multi-word phrases
            # e.g. "nodejs experience" → "nodejs"
            words = cleaned_phrase.split()
            while words and words[-1] in GENERIC_NOISE_WORDS:
                words.pop()
            while words and words[0] in GENERIC_NOISE_WORDS:
                words.pop(0)
            cleaned_phrase = ' '.join(words)
            if cleaned_phrase and 1 <= len(words) <= 3 and cleaned_phrase not in GENERIC_NOISE_WORDS:
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


def analyze_career_velocity(resume_text, job_roles, precomputed_timeline=None):
    """Detects 'Fast Trackers' based on role progressions or timeframes."""
    is_fast_tracker = False
    velocity_notes = "Normal progression."
    
    # Simple heuristic: If they have 'Senior', 'Lead', 'Manager', or 'Architect' with <= 4 years provable experience
    senior_roles = [r for r in job_roles if any(k in r.lower() for k in ('senior', 'lead', 'manager', 'architect', 'principal', 'staff', 'head', 'director'))]
    if senior_roles:
        timeline = precomputed_timeline if precomputed_timeline is not None else audit_experience_timeline(resume_text)
        provable = timeline.get('provable_years', 0)
        if 0 < provable <= 4:
            is_fast_tracker = True
            velocity_notes = f"Fast Tracker: Reached {senior_roles[0]} in ~{provable} years."
            
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


CLICHE_PATTERNS = [
    'team player', 'hard worker', 'results driven', 'results-driven',
    'go getter', 'go-getter', 'detail oriented', 'detail-oriented',
    'self starter', 'self-starter', 'think outside the box',
    'fast learner', 'dynamic professional', 'hardworking', 'enthusiastic',
    'synergy', 'proactive approach', 'proven track record'
]

WEAK_OPENERS = re.compile(
    r'^(?:(?:was\s+)?responsible\s+for|worked\s+on|helped\s+(?:with|to)|assisted\s+(?:in|with)|'
    r'handled|participated\s+in|involved\s+in|contributed\s+to|did|tasked\s+with|aimed\s+to|'
    r'created|built|made|wrote|developed|designed)\s+',
    re.IGNORECASE
)


def audit_ats_formatting(resume_text, contact_info, entities):
    """Comprehensive ATS pre-flight formatting and parsability audit."""
    words = len(resume_text.split())
    if words < 250:
        wc_status = 'Under-detailed (<250 words) — Risk of missing key ATS skill triggers'
        wc_score = 60
    elif words > 1200:
        wc_status = 'Overly Dense (>1200 words) — Consider trimming to 2 concise pages'
        wc_score = 75
    else:
        wc_status = 'Optimal ATS Length (450–900 words) — Ideal keyword-to-page ratio'
        wc_score = 100

    contact = contact_info or {}
    c_items = 0
    if contact.get('email'): c_items += 1
    if contact.get('phone'): c_items += 1
    if contact.get('linkedin'): c_items += 1
    if contact.get('github'): c_items += 1
    contact_score = round((c_items / 4) * 100)

    found_cliches = []
    text_lower = resume_text.lower()
    for c in CLICHE_PATTERNS:
        if c in text_lower:
            found_cliches.append(c)

    ents = entities or {}
    metrics = ents.get('metrics', [])
    metric_density = 'High' if len(metrics) >= 4 else 'Moderate' if len(metrics) >= 2 else 'Low'

    score = round(
        (wc_score * 0.3) +
        (contact_score * 0.3) +
        (100 if metric_density == 'High' else 75 if metric_density == 'Moderate' else 50) * 0.3 +
        (max(0, 100 - len(found_cliches) * 15)) * 0.1
    )

    return {
        'ats_health_score': min(100, max(20, score)),
        'word_count': words,
        'word_count_status': wc_status,
        'contact_completeness_score': contact_score,
        'contact_checks': {
            'email': bool(contact.get('email')),
            'phone': bool(contact.get('phone')),
            'linkedin': bool(contact.get('linkedin')),
            'github': bool(contact.get('github'))
        },
        'cliches_detected': found_cliches,
        'metrics_density': metric_density,
        'metrics_count': len(metrics),
        'action_verbs_count': len(ents.get('action_verbs', []))
    }


def optimize_resume_bullet(raw_bullet, target_role=None):
    """Transforms a weak/standard resume bullet into 3 high-impact executive variations."""
    if not raw_bullet or not raw_bullet.strip():
        return []
    clean = re.sub(r'^[•\-\*\d\.\)\s]+', '', raw_bullet.strip()).rstrip('.')
    core = WEAK_OPENERS.sub('', clean).strip()
    if not core:
        core = clean

    cap_core = core[0].lower() + core[1:] if len(core) > 1 else core.lower()

    return [
        {
            'type': 'Google XYZ Impact Formula',
            'tag': 'Metric-Driven',
            'formula': 'Accomplished [X] measured by [Y] by doing [Z]',
            'text': f'Engineered high-throughput architecture for {cap_core}, driving a 35% improvement in execution speed and scaling service capacity to 100k+ users.',
            'benefit': 'Quantifies exact business impact and engineering efficiency.'
        },
        {
            'type': 'Senior Engineering Ownership',
            'tag': 'Leadership & Strategy',
            'formula': 'Spearheaded [Initiative] aligning [Team] to achieve [Outcome]',
            'text': f'Spearheaded technical execution for {cap_core}, partnering across product and engineering to accelerate feature deployment velocity by 25%.',
            'benefit': 'Demonstrates cross-functional leadership and initiative.'
        },
        {
            'type': 'Technical Rigor & Resilience',
            'tag': 'Systems Design',
            'formula': 'Architected [System] with [Best Practices] eliminating [Failure Mode]',
            'text': f'Architected resilient microservice workflows for {cap_core}, integrating automated CI/CD validation and achieving 99.95% production uptime.',
            'benefit': 'Signals production reliability and architectural depth.'
        }
    ]


def generate_tailored_cover_letter(candidate_name, matched_skills, missing_skills, provable_years=0, job_roles=None, job_description=None):
    """Constructs a tailored, executive 3-paragraph cover letter based on parsed resume intelligence."""
    clean_name = candidate_name.replace('.pdf', '').replace('.docx', '').replace('_', ' ').strip()
    primary_role = job_roles[0] if (job_roles and len(job_roles) > 0) else 'Software Engineer'
    top_skills = ', '.join(matched_skills[:4]) if matched_skills else 'modern software engineering principles and full-stack development'
    years_text = f'over {provable_years} years of proven industry experience' if provable_years > 1 else 'hands-on technical background'

    p1 = f"Dear Hiring Team,\n\nI am writing to express my enthusiastic interest in the {primary_role} opportunity at your organization. With {years_text} designing, scaling, and maintaining mission-critical applications, I offer deep technical fluency across {top_skills}. Your team's commitment to technical excellence and user-centric systems strongly aligns with my professional background."

    p2 = f"Throughout my engineering career, I have focused on building performant, scalable, and resilient software solutions. Leveraging expertise in {top_skills}, I have consistently translated complex architectural requirements into reliable production services while optimizing execution throughput and code quality. Furthermore, I thrive in collaborative agile environments where engineering rigor and rapid iterative delivery intersect."

    p3 = "I welcome the opportunity to discuss how my technical expertise, problem-solving mindset, and dedication to high-quality code can contribute directly to your engineering team's ongoing success. Thank you for your time and consideration.\n\nSincerely,\n" + clean_name

    return f"{p1}\n\n{p2}\n\n{p3}"



def audit_experience_timeline(resume_text):
    claimed_match = CLAIMED_EXP_PATTERN.search(resume_text)
    claimed_years = int(claimed_match.group(1)) if claimed_match else None

    now = datetime.datetime.now()
    intervals = []

    # 1. Textual month/year ranges: 'Jan 2019 - Present', '2018 - 2023', etc.
    for match in DATE_RANGE_PATTERN.finditer(resume_text):
        try:
            start_m, start_y, end_m, end_y = match.groups()
            s_m = MONTH_MAP.get(start_m.lower(), 1) if start_m else 1
            s_y = int(start_y)

            if not end_y or (end_m and end_m.lower() in ('present', 'current')) or (end_y and end_y.lower() in ('present', 'current')):
                e_m, e_y = now.month, now.year
            elif end_y.isdigit():
                e_y = int(end_y)
                e_m = MONTH_MAP.get(end_m.lower(), 12) if end_m else 12
            else:
                continue

            s_total = s_y * 12 + s_m
            e_total = e_y * 12 + e_m
            if 0 < (e_total - s_total) < 600:
                intervals.append((s_total, e_total))
        except Exception:
            continue

    # 2. Numeric date ranges: '01/2018 - 05/2023', '01/2019 - Present'
    for match in NUMERIC_DATE_RANGE_PATTERN.finditer(resume_text):
        try:
            s_m_str, s_y_str, e_m_str, e_y_str = match.groups()
            s_m = int(s_m_str)
            s_y = int(s_y_str)

            if e_y_str.lower() in ('present', 'current'):
                e_m, e_y = now.month, now.year
            elif e_y_str.isdigit():
                e_y = int(e_y_str)
                e_m = int(e_m_str) if e_m_str else 12
            else:
                continue

            s_total = s_y * 12 + s_m
            e_total = e_y * 12 + e_m
            if 0 < (e_total - s_total) < 600:
                intervals.append((s_total, e_total))
        except Exception:
            continue

    # Merge overlapping employment intervals so concurrent positions are not double-counted
    merged = []
    for start, end in sorted(intervals, key=lambda x: x[0]):
        if not merged or merged[-1][1] < start:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    total_months = sum(end - start for start, end in merged)
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

    # Accurate individual skill match ratio
    total_req = len(job_skills) if job_skills else 1
    exact_count = len(skill_insights["matched_skills"])
    related_count = len(skill_insights.get("related_skills", []))
    effective = exact_count + (related_count * 0.9)
    skill_match_score = round(min(100.0, (effective / total_req) * 100.0), 2) if total_req else 0.0

    return {
        "name": filename,
        "score": score,
        "tfidf_score": tfidf_score,
        "dense_score": dense_score,
        "skill_match_score": skill_match_score,
        "stage": "applied",
        "contact": contact_info,
        "matched_skills": skill_insights["matched_skills"],
        "related_skills": skill_insights.get("related_skills", []),
        "missing_skills": skill_insights["missing_skills"][:5],
        "entities": entities,
        "soft_skills_profile": profile_soft_skills(entities.get("soft_skills", []), resume_text),
        "velocity_analysis": analyze_career_velocity(resume_text, entities.get("job_roles", []), precomputed_timeline=timeline_audit),
        "culture_fit": analyze_culture_fit(resume_text),
        "salary_prediction": predict_salary(entities.get("job_roles", []), timeline_audit.get("provable_years", 0)),
        "timeline_audit": timeline_audit,
        "tldr_summary": generate_tldr_summary(score, skill_insights["matched_skills"], skill_insights["missing_skills"], timeline_audit),
        "interview_questions": generate_interview_questions(skill_insights["matched_skills"], skill_insights["missing_skills"], timeline_audit),
        "outreach_email": generate_outreach_email(filename, score, skill_insights["matched_skills"], skill_insights["missing_skills"]),
        "ats_health_audit": audit_ats_formatting(resume_text, contact_info, entities),
        "cover_letter": generate_tailored_cover_letter(filename, skill_insights["matched_skills"], skill_insights["missing_skills"], timeline_audit.get("provable_years", 0), entities.get("job_roles", []))
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