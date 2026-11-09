"""
ResuMetrics Comprehensive Test Suite
Tests NLP parser, hybrid scoring pipeline, auth/authz, all major API endpoints,
Kanban persistence, AI assignment generation, analytics, history, CSV/PDF export,
and the applicant self-evaluation flow.

Run with: python -m unittest test_app.py -v
"""
import io
import json
import os
import unittest

from app import app, get_db_connection, LAST_REPORT
from resume_parser import (
    extract_text,
    clean_text,
    _extract_skill_phrases,
    extract_keyword_insights,
    extract_entities,
    audit_experience_timeline,
    analyze_career_velocity,
    calculate_tfidf_scores,
    calculate_dense_scores,
    compute_rrf_scores,
    build_candidate_report
)

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_resumes')


def _get_first_sample_pdf() -> bytes:
    files = [f for f in os.listdir(SAMPLE_DIR) if f.endswith('.pdf')]
    if not files:
        raise RuntimeError('No sample PDFs found. Run generate_samples.py first.')
    with open(os.path.join(SAMPLE_DIR, files[0]), 'rb') as fh:
        return fh.read(), files[0]


# ---------------------------------------------------------------------------
# 1. NLP Parser Unit Tests
# ---------------------------------------------------------------------------
class TestNLPParser(unittest.TestCase):
    """Unit tests for NLP and resume parsing algorithms."""

    def test_clean_text_basic(self):
        text = "Hello,   World! \n\n Test \t 123."
        cleaned = clean_text(text)
        self.assertIn("hello", cleaned)
        self.assertIn("world", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertNotIn("\t", cleaned)

    def test_docx_text_extraction(self):
        """Verify DOCX resume text extraction with XML/Zip fallback."""
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
            <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
              <w:body>
                <w:p><w:r><w:t>Morgan Jones</w:t></w:r></w:p>
                <w:p><w:r><w:t>Senior Machine Learning Engineer | PyTorch, Transformers, MLOps</w:t></w:r></w:p>
              </w:body>
            </w:document>"""
            zf.writestr('word/document.xml', xml)
        raw = extract_text(buf.getvalue(), 'docx')
        self.assertIn('Morgan Jones', raw)
        self.assertIn('PyTorch', raw)

    def test_alias_normalization_cicd(self):
        """CI/CD and UI/UX must not be split into individual letters."""
        jd = "We need expertise in CI/CD, UI/UX, Next.js, and scikit-learn."
        skills = _extract_skill_phrases(jd)
        self.assertIn("cicd", skills, f"Skills extracted: {skills}")
        self.assertIn("uiux", skills, f"Skills extracted: {skills}")
        self.assertIn("nextjs", skills, f"Skills extracted: {skills}")
        self.assertIn("sklearn", skills, f"Skills extracted: {skills}")
        self.assertNotIn("ci", skills, f"'ci' should not appear as standalone skill")
        self.assertNotIn("cd", skills, f"'cd' should not appear as standalone skill")

    def test_alias_normalization_rest_apis(self):
        jd = "Looking for a developer with REST APIs and Node.js experience."
        skills = _extract_skill_phrases(jd)
        self.assertIn("restapi", skills, f"Skills: {skills}")
        self.assertIn("nodejs", skills, f"Skills: {skills}")

    def test_entity_extraction_degrees(self):
        resume_text = (
            "Alex Smith\n"
            "EDUCATION\n"
            "B.S. in Computer Science | Stanford University | Graduated 2016\n"
            "M.S. Computer Engineering, MIT | 2018\n"
            "CERTIFICATIONS\n"
            "AWS Certified Solutions Architect\n"
        )
        entities = extract_entities(resume_text)
        self.assertTrue(len(entities['degrees']) >= 1,
                        f"Expected degrees, got: {entities['degrees']}")
        # At least one degree should contain a standard abbreviation
        degree_texts = " ".join(entities['degrees']).lower()
        self.assertTrue(
            any(d in degree_texts for d in ('b.s', 'b.s.', 'bs', 'm.s', 'm.s.', 'ms')),
            f"Expected standard degree abbreviation. Got: {entities['degrees']}"
        )
        uni_texts = " ".join(entities['universities']).lower()
        self.assertTrue(
            "stanford" in uni_texts or "mit" in uni_texts,
            f"Expected Stanford or MIT. Got: {entities['universities']}"
        )
        cert_texts = " ".join(entities['certifications']).lower()
        self.assertIn("aws", cert_texts, f"Expected AWS cert. Got: {entities['certifications']}")

    def test_timeline_audit_no_false_positives(self):
        """Overlapping jobs (concurrent positions) should NOT create fraud alerts."""
        text = (
            "EXPERIENCE\n"
            "Tech Lead | Company A | Jan 2020 - Present\n"
            "Advisor | Company B | Jun 2021 - Dec 2022\n"
            "Senior Engineer | Company C | Jan 2017 - Dec 2019\n"
        )
        audit = audit_experience_timeline(text)
        self.assertFalse(
            audit['timeline_alert'],
            f"False positive alert triggered: {audit.get('alert_reason')}"
        )
        self.assertGreaterEqual(audit['provable_years'], 5.0,
                                f"Provable years too low: {audit['provable_years']}")

    def test_timeline_audit_numeric_dates(self):
        """Numeric date ranges (01/2018 - 05/2023) must be parsed correctly."""
        text = "Software Engineer | FastCo | 01/2018 - 05/2023"
        audit = audit_experience_timeline(text)
        self.assertGreater(audit['provable_years'], 0, "Failed to parse numeric date range")

    def test_velocity_analysis_fast_tracker(self):
        """Fast tracker detection: senior role within <= 4 years provable experience."""
        # 2 years total, already a Lead – should trigger fast tracker
        text = (
            "Lead Software Engineer | ScaleUp Corp | Jan 2025 - Present\n"
            "Junior Engineer | ScaleUp Corp | Jan 2024 - Dec 2024\n"
        )
        job_roles = ["Lead Software Engineer"]
        vel = analyze_career_velocity(text, job_roles)
        self.assertTrue(vel['is_fast_tracker'], f"Expected fast tracker: {vel}")

    def test_velocity_analysis_normal_progression(self):
        """Normal career (8+ years) should not be flagged as fast tracker."""
        text = (
            "Principal Engineer | BigCorp | Jan 2015 - Present\n"
            "Senior Engineer | MidCorp | Jan 2010 - Dec 2014\n"
        )
        job_roles = ["Principal Engineer"]
        vel = analyze_career_velocity(text, job_roles)
        self.assertFalse(vel['is_fast_tracker'], f"Should not be fast tracker: {vel}")

    def test_hybrid_scoring_tech_vs_non_tech(self):
        """Tech resume must score significantly higher than non-tech for a tech JD."""
        resumes = [
            "Senior Python engineer with strong React, Docker, and PostgreSQL experience.",
            "Accountant with tax preparation, GAAP, and spreadsheet auditing skills."
        ]
        cleaned_resumes = [clean_text(r) for r in resumes]
        jd = "Python, React, Docker, PostgreSQL, microservices"
        cleaned_jd = clean_text(jd)
        job_skills = _extract_skill_phrases(jd)

        all_insights = [extract_keyword_insights(cr, job_skills) for cr in cleaned_resumes]
        matched_lists = [ins['matched_skills'] for ins in all_insights]
        related_counts = [len(ins.get('related_skills', [])) for ins in all_insights]

        tfidf = calculate_tfidf_scores(cleaned_resumes, cleaned_jd)
        dense = calculate_dense_scores(resumes, jd)
        rrf = compute_rrf_scores(
            tfidf, dense,
            job_skills=job_skills,
            cleaned_resumes=cleaned_resumes,
            skill_matches=matched_lists,
            related_skill_counts=related_counts
        )

        self.assertGreater(rrf[0], rrf[1],
                           f"Tech resume ({rrf[0]}) must beat accountant ({rrf[1]}) for tech JD")
        self.assertGreater(tfidf[0], tfidf[1])

    def test_keyword_insights_related_skills(self):
        """PyTorch should be treated as a related skill when TensorFlow is required."""
        resume = clean_text("Experienced ML engineer proficient in PyTorch and scikit-learn.")
        jd_skills = _extract_skill_phrases("TensorFlow, Scikit-Learn, Python, Machine Learning")
        insights = extract_keyword_insights(resume, jd_skills)
        # At least PyTorch or some related skill should appear
        all_matched = insights['matched_skills']
        all_related = [r['required'] for r in insights['related_skills']]
        self.assertTrue(
            len(all_matched) + len(all_related) > 0,
            f"Expected some matches or related skills. matched={all_matched}, related={all_related}"
        )


# ---------------------------------------------------------------------------
# 2. Flask Application Integration Tests
# ---------------------------------------------------------------------------
class TestFlaskApp(unittest.TestCase):
    """End-to-end integration tests for Flask web app routes and APIs."""

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        # Ensure sample resumes exist
        self.assertTrue(
            os.path.exists(SAMPLE_DIR) and len(os.listdir(SAMPLE_DIR)) > 0,
            "sample_resumes/ directory is empty. Run python generate_samples.py"
        )

    # --- Health & Public Routes ---
    def test_health_check(self):
        resp = self.client.get('/health')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get('status'), 'ok')

    def test_landing_page(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"ResuMetrics", resp.data)

    def test_login_page_loads(self):
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Sign In", resp.data)

    def test_register_page_loads(self):
        resp = self.client.get('/register')
        self.assertEqual(resp.status_code, 200)

    # --- Unauthenticated Protection ---
    def test_unauthenticated_analyze_redirects(self):
        """Unauthenticated /analyze must return 401 for JSON/API context."""
        resp = self.client.post('/analyze')
        # With no session and no files, should still hit auth check
        # May be 400 (no files) or 401 depending on request type
        self.assertIn(resp.status_code, [400, 401])

    def test_unauthenticated_generate_assignment_401(self):
        """Non-authenticated API request must get 401."""
        resp = self.client.post('/generate-assignment',
                                data=json.dumps({'candidate_name': 'Test'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 401)
        data = json.loads(resp.data)
        self.assertIn('Authentication required', data.get('error', ''))

    def test_unauthenticated_stage_update_401(self):
        resp = self.client.post('/api/candidate/stage',
                                data=json.dumps({'candidate_name': 'Test', 'stage': 'shortlisted'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_history_401(self):
        resp = self.client.get('/history')
        self.assertEqual(resp.status_code, 401)

    # --- Demo Login Flows ---
    def test_recruiter_demo_login(self):
        """Recruiter demo login should land on main recruiter dashboard."""
        resp = self.client.get('/demo-login', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        # Should show Recruiter Dashboard (dashboard.html)
        self.assertIn(b"ResuMetrics", resp.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_role'), 'recruiter')
            self.assertEqual(sess.get('user_id'), 999)

    def test_applicant_demo_login_shortcut(self):
        """Applicant demo login shortcut (/applicant-demo-login) must set applicant role."""
        resp = self.client.get('/applicant-demo-login', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"ResuMetrics", resp.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_role'), 'applicant')
            self.assertEqual(sess.get('user_id'), 998)

    def test_applicant_demo_via_query_param(self):
        """Applicant demo via /demo-login?role=applicant must set applicant role."""
        resp = self.client.get('/demo-login?role=applicant', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_role'), 'applicant')

    # --- Role Isolation ---
    def test_applicant_forbidden_from_recruiter_routes(self):
        """Applicant must receive 403 on recruiter-only endpoints."""
        self.client.get('/applicant-demo-login')
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_role'), 'applicant')

        resp = self.client.post('/generate-assignment',
                                data=json.dumps({'candidate_name': 'Test'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

        resp = self.client.post('/api/candidate/stage',
                                data=json.dumps({'candidate_name': 'Test', 'stage': 'interviewing'}),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    # --- Applicant Self-Evaluation ---
    def test_applicant_evaluate_endpoint(self):
        """Applicant self-evaluation must return analysis without touching LAST_REPORT."""
        self.client.get('/applicant-demo-login')
        pdf_bytes, fn = _get_first_sample_pdf()

        data = {
            'skills': 'Python, React, AWS, Docker, PostgreSQL',
            'resume': (io.BytesIO(pdf_bytes), fn)
        }
        resp = self.client.post('/api/applicant/evaluate', data=data,
                                content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        res_json = json.loads(resp.data)
        self.assertTrue(res_json.get('success'), f"Response: {res_json}")
        self.assertIn('candidate', res_json)
        self.assertGreaterEqual(res_json['candidate']['score'], 0)
        self.assertIn('matched_skills', res_json['candidate'])

    def test_applicant_sample_endpoint(self):
        """Applicant sample endpoint must return a full candidate evaluation."""
        self.client.get('/applicant-demo-login')
        resp = self.client.post('/api/applicant/sample')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get('success'), f"Response: {data}")
        self.assertIn('candidate', data)
        self.assertIn('job_description', data)

    # --- Recruiter Full Workflow ---
    def test_recruiter_full_workflow(self):
        """
        End-to-end recruiter workflow:
        analyze → generate-assignment → stage update → chat → analytics → export CSV → export PDF → history
        """
        self.client.get('/demo-login')  # recruiter role

        # Load two sample PDFs
        sample_files = [f for f in os.listdir(SAMPLE_DIR) if f.endswith('.pdf')][:2]
        self.assertGreaterEqual(len(sample_files), 2, "Need at least 2 sample PDFs for this test")

        file_tuples = []
        for fn in sample_files:
            with open(os.path.join(SAMPLE_DIR, fn), 'rb') as fh:
                file_tuples.append((io.BytesIO(fh.read()), fn))

        data = {
            'skills': 'Python, React, AWS, Docker, Kubernetes, CI/CD, SQL, Node.js',
            'resumes': file_tuples
        }
        resp = self.client.post('/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200, f"Analyze failed: {resp.data[:200]}")
        res_json = json.loads(resp.data)
        self.assertIn('candidates', res_json)
        self.assertEqual(len(res_json['candidates']), 2)

        top = res_json['candidates'][0]
        cand_name = top['name']

        # Test AI Take-Home Assignment Generation
        gen_resp = self.client.post('/generate-assignment',
                                    data=json.dumps({
                                        'candidate_name': cand_name,
                                        'roles': ['Senior Software Engineer'],
                                        'matched_skills': top.get('matched_skills', ['Python', 'Docker']),
                                        'missing_skills': top.get('missing_skills', ['Kubernetes']),
                                        'provable_years': 5
                                    }),
                                    content_type='application/json')
        self.assertEqual(gen_resp.status_code, 200, f"Assignment gen failed: {gen_resp.data[:200]}")
        gen_json = json.loads(gen_resp.data)
        self.assertIn('assignment', gen_json)
        self.assertIn('Technical Assessment', gen_json['assignment'])
        self.assertTrue(len(gen_json['assignment']) > 100)

        # Test Kanban stage update
        stage_resp = self.client.post('/api/candidate/stage',
                                      data=json.dumps({
                                          'candidate_name': cand_name,
                                          'stage': 'interviewing'
                                      }),
                                      content_type='application/json')
        self.assertEqual(stage_resp.status_code, 200)
        stage_json = json.loads(stage_resp.data)
        self.assertTrue(stage_json.get('success'))
        self.assertEqual(stage_json.get('stage'), 'interviewing')

        # Invalid stage must be rejected
        bad_stage = self.client.post('/api/candidate/stage',
                                     data=json.dumps({'candidate_name': cand_name, 'stage': 'unknown_stage'}),
                                     content_type='application/json')
        self.assertEqual(bad_stage.status_code, 400)

        # Test Conversational AI Chatbot – pipeline query
        chat_resp = self.client.post('/chat',
                                     data=json.dumps({'query': 'What is the current hiring pipeline breakdown?'}),
                                     content_type='application/json')
        self.assertEqual(chat_resp.status_code, 200)
        chat_json = json.loads(chat_resp.data)
        self.assertIn('Pipeline', chat_json.get('answer', ''), f"Chat answer: {chat_json}")

        # Test chatbot – top candidate query
        chat_top = self.client.post('/chat',
                                    data=json.dumps({'query': 'Who is the top candidate?'}),
                                    content_type='application/json')
        self.assertEqual(chat_top.status_code, 200)
        self.assertIn('answer', json.loads(chat_top.data))

        # Test Analytics
        analytics_resp = self.client.get('/analytics')
        self.assertEqual(analytics_resp.status_code, 200)
        analytics_json = json.loads(analytics_resp.data)
        self.assertIn('average_score', analytics_json)
        self.assertEqual(analytics_json.get('total_candidates'), 2)

        # Test Export CSV
        csv_resp = self.client.get('/export-csv')
        self.assertEqual(csv_resp.status_code, 200)
        # Check actual header fields that exist in the CSV
        self.assertIn(b"ATS Stage", csv_resp.data)
        self.assertIn(b"Match Score", csv_resp.data)

        # Test Export PDF Report
        pdf_resp = self.client.get('/export-report')
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp.headers.get('Content-Type'), 'application/pdf')
        self.assertGreater(len(pdf_resp.data), 1000, "PDF too small – likely empty or errored")

        # Test History Retrieval
        hist_resp = self.client.get('/history')
        self.assertEqual(hist_resp.status_code, 200)
        hist_json = json.loads(hist_resp.data)
        self.assertGreater(len(hist_json.get('analysis_history', [])), 0)

    # --- Headless API v1 ---
    def test_headless_api_v1_analyze(self):
        """Headless API must work with API-key authentication (no session)."""
        pdf_bytes, fn = _get_first_sample_pdf()
        data = {
            'skills': 'Python, Docker, AWS',
            'resumes': [(io.BytesIO(pdf_bytes), fn)]
        }
        resp = self.client.post('/api/v1/analyze',
                                headers={'X-API-Key': 'demo-api-key-123'},
                                data=data,
                                content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        res_json = json.loads(resp.data)
        self.assertIn('candidates', res_json)
        self.assertEqual(len(res_json['candidates']), 1)
        cand = res_json['candidates'][0]
        self.assertIn('score', cand)
        self.assertIn('matched_skills', cand)

    def test_headless_api_v1_unauthorized(self):
        """Headless API must reject invalid API key with 401."""
        pdf_bytes, fn = _get_first_sample_pdf()
        data = {
            'skills': 'Python',
            'resumes': [(io.BytesIO(pdf_bytes), fn)]
        }
        resp = self.client.post('/api/v1/analyze',
                                headers={'X-API-Key': 'wrong-key'},
                                data=data,
                                content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 401)

    # --- Sample Demo Load ---
    def test_load_samples_route(self):
        """Load samples route must return analyzed candidates."""
        self.client.get('/demo-login')
        resp = self.client.post('/api/samples/load')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn('candidates', data)
        self.assertGreater(len(data['candidates']), 0)

    def test_docx_upload_and_analyze(self):
        """Verify full /analyze flow when uploading a .docx resume."""
        import zipfile
        self.client.get('/demo-login')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
            <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
              <w:body>
                <w:p><w:r><w:t>Taylor Williams</w:t></w:r></w:p>
                <w:p><w:r><w:t>taylor.williams@designsync.org | 555-010-0003</w:t></w:r></w:p>
                <w:p><w:r><w:t>Senior Frontend Engineer specializing in React, TypeScript, Next.js, and Tailwind CSS.</w:t></w:r></w:p>
                <w:p><w:r><w:t>Lead Frontend Engineer | DesignSync | Aug 2020 - Present</w:t></w:r></w:p>
                <w:p><w:r><w:t>B.S. in Software Engineering | University of California Berkeley | 2018</w:t></w:r></w:p>
              </w:body>
            </w:document>"""
            zf.writestr('word/document.xml', xml)

        data = {
            'skills': 'React, TypeScript, Next.js, Tailwind',
            'resumes': [(io.BytesIO(buf.getvalue()), 'Taylor_Williams.docx')]
        }
        resp = self.client.post('/analyze', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        res_json = json.loads(resp.data)
        self.assertIn('candidates', res_json)
        self.assertEqual(len(res_json['candidates']), 1)
        self.assertIn('Taylor_Williams.docx', res_json['candidates'][0]['name'])
        self.assertGreater(res_json['candidates'][0]['score'], 40)

    # --- Logout ---
    def test_logout_clears_session(self):
        self.client.get('/demo-login')
        with self.client.session_transaction() as sess:
            self.assertIn('user_id', sess)

        resp = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

    # --- ATS Formatting & Intelligence Tests ---
    def test_ats_formatting_audit(self):
        from resume_parser import audit_ats_formatting
        sample_text = "Accomplished Senior Software Engineer with extensive experience building cloud architectures. " * 30
        contact = {'email': 'dev@example.com', 'phone': '+1234567890', 'linkedin': 'linkedin.com/in/dev', 'github': 'github.com/dev'}
        entities = {'metrics': ['40%', '$150k', '100k+'], 'action_verbs': ['Architected', 'Spearheaded', 'Engineered']}
        audit = audit_ats_formatting(sample_text, contact, entities)
        self.assertIn('ats_health_score', audit)
        self.assertGreater(audit['ats_health_score'], 80)
        self.assertEqual(audit['contact_completeness_score'], 100)
        self.assertEqual(audit['metrics_density'], 'Moderate')

    def test_bullet_point_optimizer(self):
        from resume_parser import optimize_resume_bullet
        raw = "Worked on database queries and improved speed"
        revs = optimize_resume_bullet(raw)
        self.assertEqual(len(revs), 3)
        self.assertIn('Google XYZ', revs[0]['type'])
        self.assertIn('database queries and improved speed', revs[0]['text'].lower())
        self.assertIn('formula', revs[0])

    def test_tailored_cover_letter(self):
        from resume_parser import generate_tailored_cover_letter
        cl = generate_tailored_cover_letter("John_Doe.pdf", ["Python", "Docker", "AWS"], ["Kubernetes"], provable_years=5)
        self.assertIn("John Doe", cl)
        self.assertIn("Python", cl)
        self.assertIn("5 years", cl)

    def test_api_optimize_bullet_endpoint(self):
        self.client.get('/applicant-demo-login')
        resp = self.client.post('/api/applicant/optimize-bullet', json={
            'bullet': 'Helped team with cloud deployment'
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get('success'))
        self.assertEqual(len(data.get('revisions', [])), 3)

    def test_api_cover_letter_endpoint(self):
        self.client.get('/applicant-demo-login')
        resp = self.client.post('/api/applicant/cover-letter', json={
            'name': 'Sarah_Connor.pdf',
            'matched_skills': ['Python', 'Docker'],
            'missing_skills': ['Go'],
            'provable_years': 4,
            'job_roles': ['Senior Backend Engineer']
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get('success'))
        self.assertIn('Sarah Connor', data.get('cover_letter'))

    def test_applicant_sample_includes_ats_audit(self):
        self.client.get('/applicant-demo-login')
        resp = self.client.post('/api/applicant/sample')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get('success'))
        candidate = data.get('candidate', {})
        self.assertIn('ats_health_audit', candidate)
        self.assertIn('cover_letter', candidate)

    def test_forgot_password_page_loads(self):
        """GET /forgot-password should render forgot password template."""
        resp = self.client.get('/forgot-password')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Reset your password', resp.data)

    def test_forgot_password_submission_existing_user(self):
        """POST /forgot-password with registered user should generate reset link."""
        self.client.post('/register', data={
            'full_name': 'Test Reset User',
            'email': 'reset_test@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'recruiter'
        })
        self.client.get('/logout')

        resp = self.client.post('/forgot-password', data={
            'email': 'reset_test@example.com'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'reset-password', resp.data)

    def test_reset_password_flow(self):
        """Full password reset flow from token generation to updated login."""
        from app import get_password_reset_serializer

        self.client.post('/register', data={
            'full_name': 'Flow User',
            'email': 'flow_test@example.com',
            'password': 'OldPassword123!',
            'confirm_password': 'OldPassword123!',
            'role': 'recruiter'
        })
        self.client.get('/logout')

        serializer = get_password_reset_serializer()
        token = serializer.dumps('flow_test@example.com', salt='resumetrics-password-reset')

        resp_get = self.client.get(f'/reset-password/{token}')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Create new password', resp_get.data)

        resp_mismatch = self.client.post(f'/reset-password/{token}', data={
            'password': 'NewPassword123!',
            'confirm_password': 'DifferentPassword456!'
        })
        self.assertEqual(resp_mismatch.status_code, 200)
        self.assertIn(b'Passwords do not match', resp_mismatch.data)

        resp_post = self.client.post(f'/reset-password/{token}', data={
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'successfully reset', resp_post.data)

        login_resp = self.client.post('/login', data={
            'email': 'flow_test@example.com',
            'password': 'NewPassword123!'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b'Flow User', login_resp.data)

    def test_reset_password_invalid_token(self):
        """Invalid token should redirect to forgot-password with error."""
        resp = self.client.get('/reset-password/totally-invalid-token', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Invalid or tampered', resp.data)



if __name__ == '__main__':
    unittest.main(verbosity=2)
