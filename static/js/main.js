(function () {
  'use strict';

  const GAUGE_CIRCUMFERENCE = 326.7;

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const fileListEl = document.getElementById('file-list');
  const skillsInput = document.getElementById('skills-input');
  const analyzeBtn = document.getElementById('analyze-btn');
  const btnLabel = analyzeBtn.querySelector('.btn-label');
  const spinner = analyzeBtn.querySelector('.spinner');
  const clearResumesBtn = document.getElementById('clear-resumes-btn');
  const formError = document.getElementById('form-error');
  const emptyState = document.getElementById('empty-state');
  const resultsList = document.getElementById('results-list');
  const skippedFilesEl = document.getElementById('skipped-files');
  const exportBtn = document.getElementById('export-btn');
  const exportCsvBtn = document.getElementById('export-csv-btn');
  const compareBtn = document.getElementById('compare-btn');
  const shortlistBtn = document.getElementById('shortlist-btn');
  const selectAllBtn = document.getElementById('select-all-btn');
  const analyticsBtn = document.getElementById('analytics-btn');
  const chatBtn = document.getElementById('chat-btn');
  const analyticsPanel = document.getElementById('analytics-panel');
  const chatPanel = document.getElementById('chat-panel');
  const cardTemplate = document.getElementById('candidate-card-template');

  // Tab Navigation
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));
      
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add('active');
      }
    });
  });

  const optimizeJdBtn = document.getElementById('optimize-jd-btn');
  const jdSuggestions = document.getElementById('jd-suggestions');

  if (optimizeJdBtn) {
    optimizeJdBtn.addEventListener('click', async () => {
      const skills = skillsInput.value.trim();
      if (!skills) {
        alert("Please enter some skills first.");
        return;
      }
      
      optimizeJdBtn.disabled = true;
      optimizeJdBtn.textContent = 'Optimizing...';
      
      try {
        const response = await fetch('/optimize-jd', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ skills })
        });
        const data = await response.json();
        if (data.suggestions && data.suggestions.length) {
          jdSuggestions.innerHTML = `<strong>Suggested Additions:</strong> ${data.suggestions.join(', ')}`;
          jdSuggestions.hidden = false;
        } else {
          jdSuggestions.innerHTML = 'No additional suggestions found.';
          jdSuggestions.hidden = false;
        }
      } catch (err) {
        console.error(err);
      } finally {
        optimizeJdBtn.disabled = false;
        optimizeJdBtn.textContent = 'Optimize JD & Suggest Skills';
      }
    });
  }

  // Filter elements
  const resultsFilters = document.getElementById('results-filters');
  const candidateSearch = document.getElementById('candidate-search');
  const filterTopMatches = document.getElementById('filter-top-matches');

  // Comparison grid elements
  const compareOverlay = document.getElementById('compare-overlay');
  const compareGrid = document.getElementById('compare-grid');
  const closeCompare = document.getElementById('close-compare');

  // Email modal elements
  const emailOverlay = document.getElementById('email-overlay');
  const closeEmail = document.getElementById('close-email');
  const sendEmailBtn = document.getElementById('send-email-btn');
  const emailCountEl = document.getElementById('email-count');
  const emailResult = document.getElementById('email-result');

  const wTfidf = document.getElementById('w-tfidf');
  const wSkill = document.getElementById('w-skill');
  const wDense = document.getElementById('w-dense');
  const wTfidfVal = document.getElementById('w-tfidf-val');
  const wSkillVal = document.getElementById('w-skill-val');
  const wDenseVal = document.getElementById('w-dense-val');

  if (wTfidf && wSkill && wDense) {
    wTfidf.addEventListener('input', () => wTfidfVal.textContent = `${wTfidf.value}%`);
    wSkill.addEventListener('input', () => wSkillVal.textContent = `${wSkill.value}%`);
    wDense.addEventListener('input', () => wDenseVal.textContent = `${wDense.value}%`);
  }

  if (candidateSearch) candidateSearch.addEventListener('input', () => renderResults(lastCandidates));
  if (filterTopMatches) filterTopMatches.addEventListener('change', () => renderResults(lastCandidates));

  let stagedFiles = [];
  let lastCandidates = [];

  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => { dropzone.classList.remove('dragover'); });
  dropzone.addEventListener('drop', (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); addFiles(e.dataTransfer.files); });
  fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });

  function addFiles(fileListLike) {
    const incoming = Array.from(fileListLike);
    const allowedExt = ['pdf', 'docx'];
    incoming.forEach((file) => {
      const ext = file.name.split('.').pop().toLowerCase();
      if (!allowedExt.includes(ext)) { showFormError(`"${file.name}" skipped - only PDF/DOCX allowed.`); return; }
      const isDuplicate = stagedFiles.some((f) => f.name === file.name && f.size === file.size);
      if (!isDuplicate) stagedFiles.push(file);
    });
    renderFileList();
    validateForm();
  }

  function removeFile(index) { stagedFiles.splice(index, 1); renderFileList(); validateForm(); }

  function renderFileList() {
    fileListEl.innerHTML = '';
    if (stagedFiles.length > 0 && clearResumesBtn) {
        clearResumesBtn.hidden = false;
    } else if (clearResumesBtn) {
        clearResumesBtn.hidden = true;
    }
    stagedFiles.forEach((file, index) => {
      const li = document.createElement('li');
      const nameSpan = document.createElement('span');
      nameSpan.textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
      const removeSpan = document.createElement('span');
      removeSpan.textContent = '\u2715';
      removeSpan.className = 'remove-file';
      removeSpan.addEventListener('click', (e) => { e.stopPropagation(); removeFile(index); });
      li.appendChild(nameSpan);
      li.appendChild(removeSpan);
      fileListEl.appendChild(li);
    });
  }

  function validateForm() {
    const hasFiles = stagedFiles.length > 0;
    const hasSkills = skillsInput.value.trim().length > 0;
    analyzeBtn.disabled = !(hasFiles && hasSkills);
    hideFormError();
  }

  skillsInput.addEventListener('input', validateForm);

  if (clearResumesBtn) {
      clearResumesBtn.addEventListener('click', () => {
          stagedFiles = [];
          fileInput.value = '';
          renderFileList();
          validateForm();
      });
  }

  function showFormError(message) { formError.textContent = message; formError.hidden = false; }
  function hideFormError() { formError.hidden = true; formError.textContent = ''; }

  // =======================================================================
  // ANALYZE
  // =======================================================================
  analyzeBtn.addEventListener('click', async () => {
    if (analyzeBtn.disabled) return;
    setLoading(true);
    hideFormError();

    const formData = new FormData();
    stagedFiles.forEach((file) => formData.append('resumes', file));
    formData.append('skills', skillsInput.value.trim());
    if (wTfidf && wSkill && wDense) {
      formData.append('w_tfidf', wTfidf.value);
      formData.append('w_skill', wSkill.value);
      formData.append('w_dense', wDense.value);
    }
    
    const blindModeToggle = document.getElementById('blind-mode-toggle');
    if (blindModeToggle) {
      formData.append('blind_mode', blindModeToggle.checked);
    }

    try {
      const response = await fetch('/analyze', { method: 'POST', body: formData });
      
      // If the server redirected us to the login page (session expired)
      if (response.redirected && response.url.includes('/login')) {
        window.location.href = '/login';
        return;
      }
      
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.indexOf("application/json") !== -1) {
        const data = await response.json();
        if (!response.ok) { showFormError(data.error || 'Failed analyzing resumes.'); renderSkippedFiles(data.skipped || []); return; }
        lastCandidates = data.candidates || [];
        renderResults(lastCandidates);
        renderSkippedFiles(data.skipped || []);
      } else {
        // If we received an HTML page instead of JSON (e.g. 500 error page or unhandled redirect)
        showFormError('Server returned an invalid response. Please refresh the page and log in again.');
        return;
      }
      const hasCandidates = lastCandidates.length > 0;
      exportBtn.hidden = !hasCandidates;
      if (exportCsvBtn) exportCsvBtn.hidden = !hasCandidates;
      if (compareBtn) compareBtn.hidden = !(hasCandidates && lastCandidates.length >= 2);
      if (shortlistBtn) shortlistBtn.hidden = !hasCandidates;
      if (selectAllBtn) selectAllBtn.hidden = !hasCandidates;
      if (analyticsBtn) analyticsBtn.hidden = !hasCandidates;
      if (chatBtn) chatBtn.hidden = !hasCandidates;
      if (resultsFilters) resultsFilters.hidden = !hasCandidates;
      
      // Populate Kanban Board
      if (typeof renderKanbanBoard === 'function') {
        renderKanbanBoard(lastCandidates);
      }

      // Smoothly switch to results tab automatically
      if (hasCandidates) {
        const resultsTabBtn = document.querySelector('[data-tab="tab-results"]');
        if (resultsTabBtn) resultsTabBtn.click();
      }
      
    } catch (err) {
      console.error(err);
      showFormError('Error: ' + err.message + ' at ' + err.stack);
    } finally {
      setLoading(false);
    }
  });

  function setLoading(isLoading) {
    analyzeBtn.disabled = isLoading || stagedFiles.length === 0 || !skillsInput.value.trim();
    spinner.hidden = !isLoading;
    btnLabel.textContent = isLoading ? 'Analyzing...' : 'Analyze Candidates';
  }

  function renderSkippedFiles(skipped) {
    if (!skipped.length) { skippedFilesEl.hidden = true; skippedFilesEl.innerHTML = ''; return; }
    const items = skipped.map((s) => `<li><strong>${escapeHtml(s.name)}</strong>: ${escapeHtml(s.reason)}</li>`).join('');
    skippedFilesEl.innerHTML = `<strong>${skipped.length} file(s) skipped:</strong><ul style="margin:6px 0 0; padding-left:18px;">${items}</ul>`;
    skippedFilesEl.hidden = false;
  }

  // =======================================================================
  // RENDER RESULTS
  // =======================================================================
  function renderResults(candidates) {
    resultsList.innerHTML = '';
    
    // Apply filters
    const searchTerm = (candidateSearch ? candidateSearch.value.trim().toLowerCase() : '');
    const topOnly = (filterTopMatches ? filterTopMatches.checked : false);
    
    const filteredCandidates = candidates.filter(c => {
      if (topOnly && c.score < 70) return false;
      if (searchTerm) {
        const textToSearch = [
            c.name,
            c.contact.email,
            c.contact.phone,
            ...(c.matched_skills || []),
            ...(c.missing_skills || []),
            ...((c.entities && c.entities.job_roles) || [])
        ].join(' ').toLowerCase();
        if (!textToSearch.includes(searchTerm)) return false;
      }
      return true;
    });

    if (!candidates.length) { 
        emptyState.hidden = false; 
        if (resultsFilters) resultsFilters.hidden = true;
        return; 
    }
    emptyState.hidden = true;
    if (resultsFilters) resultsFilters.hidden = false;

    if (!filteredCandidates.length) {
        resultsList.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">No candidates match the current filters.</p>';
        return;
    }

    filteredCandidates.forEach((candidate, index) => {
      const card = cardTemplate.content.cloneNode(true);

      card.querySelector('.rank-badge').textContent = `#${candidates.indexOf(candidate) + 1}`;
      card.querySelector('.candidate-name').textContent = candidate.name;
      card.querySelector('.candidate-email').textContent = `Email: ${candidate.contact.email}`;
      card.querySelector('.candidate-phone').textContent = `Phone: ${candidate.contact.phone}`;

      // Shortlist checkbox stores candidate data
      const checkbox = card.querySelector('.shortlist-checkbox');
      checkbox.dataset.index = index;

      // Timeline alert
      if (candidate.timeline_audit && candidate.timeline_audit.timeline_alert) {
        const alertBadge = document.createElement('div');
        alertBadge.className = 'timeline-alert-badge';
        alertBadge.innerHTML = `⚠️ <strong>Timeline Alert:</strong> ${escapeHtml(candidate.timeline_audit.alert_reason)}`;
        card.querySelector('.candidate-meta').appendChild(alertBadge);
      }

      // NER Entities
      const entities = candidate.entities || {};
      const entitySection = card.querySelector('.entity-section');
      const hasDegrees = entities.degrees && entities.degrees.length > 0;
      const hasUniversities = entities.universities && entities.universities.length > 0;
      const hasRoles = entities.job_roles && entities.job_roles.length > 0;

      if (hasDegrees || hasUniversities || hasRoles) {
        entitySection.hidden = false;
        if (hasDegrees) {
          const degreesList = card.querySelector('.degrees-list');
          entities.degrees.forEach(d => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-degree';
            tag.textContent = d;
            degreesList.appendChild(tag);
          });
        } else {
          card.querySelector('[data-type="degrees"]').hidden = true;
        }
        if (hasUniversities) {
          const uniList = card.querySelector('.universities-list');
          entities.universities.forEach(u => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-university';
            tag.textContent = u;
            uniList.appendChild(tag);
          });
        } else {
          card.querySelector('[data-type="universities"]').hidden = true;
        }
        if (hasRoles) {
          const rolesList = card.querySelector('.roles-list');
          entities.job_roles.forEach(r => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.textContent = r;
            rolesList.appendChild(tag);
          });
        } else {
          card.querySelector('[data-type="roles"]').hidden = true;
        }
        
        const hasSoftSkills = entities.soft_skills && entities.soft_skills.length > 0;
        if (hasSoftSkills) {
          const softList = card.querySelector('.soft-skills-list');
          entities.soft_skills.forEach(s => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.textContent = s;
            softList.appendChild(tag);
          });
        } else if (card.querySelector('[data-type="soft-skills"]')) {
          card.querySelector('[data-type="soft-skills"]').hidden = true;
        }

        const hasActionVerbs = entities.action_verbs && entities.action_verbs.length > 0;
        if (hasActionVerbs) {
          const actionList = card.querySelector('.action-verbs-list');
          entities.action_verbs.forEach(v => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.style.background = 'hsla(40, 82%, 55%, 0.15)';
            tag.style.color = 'var(--warning)';
            tag.style.borderColor = 'hsla(40, 82%, 55%, 0.25)';
            tag.textContent = v;
            actionList.appendChild(tag);
          });
        } else if (card.querySelector('[data-type="action-verbs"]')) {
          card.querySelector('[data-type="action-verbs"]').hidden = true;
        }

        const hasMetrics = entities.metrics && entities.metrics.length > 0;
        if (hasMetrics) {
          const metricsList = card.querySelector('.metrics-list');
          entities.metrics.forEach(m => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.style.background = 'hsla(158, 60%, 46%, 0.15)';
            tag.style.color = 'var(--success)';
            tag.style.borderColor = 'hsla(158, 60%, 46%, 0.25)';
            tag.textContent = m;
            metricsList.appendChild(tag);
          });
        } else if (card.querySelector('[data-type="metrics"]')) {
          card.querySelector('[data-type="metrics"]').hidden = true;
        }

        const hasCerts = entities.certifications && entities.certifications.length > 0;
        if (hasCerts) {
          const certsList = card.querySelector('.certifications-list');
          entities.certifications.forEach(c => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.textContent = c;
            certsList.appendChild(tag);
          });
        } else if (card.querySelector('[data-type="certifications"]')) {
          card.querySelector('[data-type="certifications"]').hidden = true;
        }

        const hasLanguages = entities.languages && entities.languages.length > 0;
        if (hasLanguages) {
          const langList = card.querySelector('.languages-list');
          entities.languages.forEach(l => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.textContent = l;
            langList.appendChild(tag);
          });
        } else if (card.querySelector('[data-type="languages"]')) {
          card.querySelector('[data-type="languages"]').hidden = true;
        }

        const hasDomains = entities.domains && entities.domains.length > 0;
        if (hasDomains) {
          const domainList = card.querySelector('.domains-list');
          entities.domains.forEach(d => {
            const tag = document.createElement('span');
            tag.className = 'entity-tag entity-role';
            tag.style.background = 'hsla(252, 80%, 65%, 0.15)';
            tag.style.color = 'var(--accent)';
            tag.style.borderColor = 'hsla(252, 80%, 65%, 0.3)';
            tag.textContent = d;
            domainList.appendChild(tag);
          });
        } else if (card.querySelector('[data-type="domains"]')) {
          card.querySelector('[data-type="domains"]').hidden = true;
        }
      }

      // Gauge
      const gaugeFill = card.querySelector('.gauge-fill');
      const score = Math.max(0, Math.min(100, candidate.score));
      gaugeFill.style.stroke = colorForScore(score);

      // Score bars
      const tfidfScore = Math.max(0, Math.min(100, candidate.tfidf_score || 0));
      const denseScore = Math.max(0, Math.min(100, candidate.dense_score || 0));
      const skillScore = Math.max(0, Math.min(100, candidate.skill_match_score || score));

      card.querySelector('.tfidf-value').textContent = `${Math.round(tfidfScore)}%`;
      card.querySelector('.skill-value').textContent = `${Math.round(skillScore)}%`;
      card.querySelector('.dense-value').textContent = `${Math.round(denseScore)}%`;

      // Skill badges
      renderBadgeGroup(card.querySelector('.matched-skills'), candidate.matched_skills, 'matched');
      renderRelatedBadgeGroup(card.querySelector('.related-skills'), candidate.related_skills || []);
      renderBadgeGroup(card.querySelector('.missing-skills'), candidate.missing_skills, 'missing');

      // AI TL;DR and Interview Questions
      const tldrEl = card.querySelector('.tldr-summary');
      if (tldrEl) tldrEl.textContent = candidate.tldr_summary || "No summary available.";
      
      const qListEl = card.querySelector('.interview-questions');
      if (qListEl) {
        if (candidate.interview_questions && candidate.interview_questions.length) {
          candidate.interview_questions.forEach(q => {
            const li = document.createElement('li');
            li.textContent = q;
            li.style.marginBottom = '4px';
            qListEl.appendChild(li);
          });
        } else {
          qListEl.innerHTML = "<li>No specific questions generated.</li>";
        }
      }
      
      const outreachEl = card.querySelector('.outreach-email');
      if (outreachEl && candidate.outreach_email) {
        outreachEl.value = candidate.outreach_email;
      }
      
      const softSkillsEl = card.querySelector('.soft-skills-profile');
      if (softSkillsEl && candidate.soft_skills_profile) {
        for (const [skill, score] of Object.entries(candidate.soft_skills_profile)) {
          const li = document.createElement('li');
          li.innerHTML = `<strong>${skill}:</strong> ${score}`;
          softSkillsEl.appendChild(li);
        }
      }
      
      const velocityEl = card.querySelector('.career-velocity');
      if (velocityEl && candidate.velocity_analysis) {
        velocityEl.innerHTML = candidate.velocity_analysis.is_fast_tracker 
          ? `🚀 <span style="color:var(--success);font-weight:600;">${candidate.velocity_analysis.velocity_notes}</span>`
          : candidate.velocity_analysis.velocity_notes;
      }

      const cultureFitEl = card.querySelector('.culture-fit');
      if (cultureFitEl && candidate.culture_fit) {
        cultureFitEl.innerHTML = `<strong>${candidate.culture_fit.alignment} Alignment</strong><br>Trait: ${candidate.culture_fit.dominant_trait}`;
      }
      
      const salaryEl = card.querySelector('.salary-prediction');
      if (salaryEl && candidate.salary_prediction) {
        salaryEl.textContent = candidate.salary_prediction;
      }



      // Take-home Assignment Generator
      const genBtn = card.querySelector('.generate-assignment-btn');
      const assignOut = card.querySelector('.assignment-output');
      if (genBtn && assignOut) {
        genBtn.addEventListener('click', () => {
          genBtn.innerHTML = '🪄 Generating Custom Assignment...';
          genBtn.disabled = true;
          
          setTimeout(() => {
            const skills = candidate.matched_skills.slice(0, 3).join(', ') || 'Core Technologies';
            const assignment = `### AI-Generated Technical Assessment\n\n**Candidate:** ${candidate.name.replace(/\.(pdf|docx)$/i, '')}\n**Target Skills:** ${skills}\n\n**Scenario:**\nWe are experiencing rapid scale. Using your expertise in ${skills}, design and implement a scalable microservice that ingests 10,000 requests per minute, processes them asynchronously, and returns a calculated result.\n\n**Requirements:**\n1. Implement the core logic.\n2. Ensure it is containerized (Dockerfile).\n3. Provide unit tests.\n\n**Estimated Time:** 3 Hours`;
            
            assignOut.textContent = assignment;
            assignOut.style.display = 'block';
            genBtn.style.display = 'none';
          }, 1200); // Simulate AI generation delay
        });
      }

      // Animation delay
      const article = card.querySelector('.candidate-card');
      article.style.animationDelay = `${index * 0.08}s`;

      resultsList.appendChild(card);
      const insertedCard = resultsList.lastElementChild;

      requestAnimationFrame(() => {
        const insertedGaugeFill = insertedCard.querySelector('.gauge-fill');
        const offset = GAUGE_CIRCUMFERENCE * (1 - score / 100);
        insertedGaugeFill.style.strokeDashoffset = offset;
        const insertedGauge = insertedCard.querySelector('.gauge');
        insertedGauge.style.filter = `drop-shadow(0 0 8px ${colorForScore(score)}40)`;

        const tfidfBar = insertedCard.querySelector('.score-bar-fill.tfidf');
        const skillBar = insertedCard.querySelector('.score-bar-fill.skill');
        const denseBar = insertedCard.querySelector('.score-bar-fill.dense');
        if (tfidfBar) tfidfBar.style.width = `${tfidfScore}%`;
        if (skillBar) skillBar.style.width = `${skillScore}%`;
        if (denseBar) denseBar.style.width = `${denseScore}%`;

        // Initialize Radar Chart (must happen after card is attached to DOM to avoid getComputedStyle error)
        const radarCanvas = insertedCard.querySelector('.candidate-radar');
        if (radarCanvas) {
          let softScore = 40;
          if (candidate.soft_skills_profile && Object.keys(candidate.soft_skills_profile).includes('Leadership')) softScore += 30;
          if (candidate.soft_skills_profile && Object.keys(candidate.soft_skills_profile).includes('Communication')) softScore += 30;
          
          new Chart(radarCanvas, {
            type: 'radar',
            data: {
              labels: ['Tech Match', 'Semantic', 'Culture', 'Velocity', 'Soft Skills'],
              datasets: [{
                data: [
                  candidate.score, 
                  candidate.dense_score, 
                  candidate.culture_fit?.score || 0, 
                  candidate.velocity_analysis?.is_fast_tracker ? 90 : 50, 
                  softScore
                ],
                backgroundColor: 'rgba(56, 189, 248, 0.2)',
                borderColor: 'rgba(56, 189, 248, 1)',
                pointBackgroundColor: 'rgba(56, 189, 248, 1)',
                pointBorderColor: '#fff',
                borderWidth: 1.5,
                pointRadius: 2
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                r: {
                  angleLines: { color: 'rgba(255,255,255,0.1)' },
                  grid: { color: 'rgba(255,255,255,0.1)' },
                  pointLabels: { color: '#94a3b8', font: { size: 9, family: 'Inter' } },
                  ticks: { display: false, min: 0, max: 100, stepSize: 25 }
                }
              },
              plugins: { legend: { display: false }, tooltip: { enabled: false } }
            }
          });
        }
      });

      animateCountUp(insertedCard.querySelector('.gauge-value'), 0, score, 900);
    });
  }

  function animateCountUp(element, start, end, duration) {
    const startTime = performance.now();
    function tick(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + (end - start) * eased);
      element.textContent = `${current}%`;
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function renderBadgeGroup(container, skills, type) {
    container.innerHTML = '';
    if (!skills || !skills.length) {
      const empty = document.createElement('span');
      empty.className = 'badge empty';
      empty.textContent = 'None';
      container.appendChild(empty);
      return;
    }
    skills.forEach((skill) => {
      const badge = document.createElement('span');
      badge.className = `badge ${type}`;
      badge.textContent = skill;
      container.appendChild(badge);
    });
  }

  function renderRelatedBadgeGroup(container, relatedSkills) {
    container.innerHTML = '';
    if (!relatedSkills || !relatedSkills.length) {
      const empty = document.createElement('span');
      empty.className = 'badge empty';
      empty.textContent = 'None';
      container.appendChild(empty);
      return;
    }
    relatedSkills.forEach((item) => {
      const badge = document.createElement('span');
      badge.className = 'badge related';
      badge.textContent = item.required;
      badge.title = `Required: ${item.required} → Has: ${item.found}`;
      const foundTag = document.createElement('span');
      foundTag.className = 'related-found-tag';
      foundTag.textContent = `→ ${item.found}`;
      badge.appendChild(foundTag);
      container.appendChild(badge);
    });
  }

  function colorForScore(score) {
    if (score >= 70) return '#1b9e5a';
    if (score >= 40) return '#e0a83e';
    return '#d64545';
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // =======================================================================
  // EXPORT
  // =======================================================================
  exportBtn.addEventListener('click', () => { window.location.href = '/export-report'; });
  if (exportCsvBtn) exportCsvBtn.addEventListener('click', () => { window.location.href = '/export-csv'; });
  
  if (analyticsBtn) {
    analyticsBtn.addEventListener('click', () => {
      const analyticsTabBtn = document.querySelector('[data-tab="tab-analytics"]');
      if (analyticsTabBtn) analyticsTabBtn.click();
    });
  }

  const loadAnalyticsBtn = document.getElementById('load-analytics-btn');
  if (loadAnalyticsBtn) {
    loadAnalyticsBtn.addEventListener('click', async () => {
      const content = document.getElementById('analytics-content');
      loadAnalyticsBtn.disabled = true;
      loadAnalyticsBtn.textContent = 'Loading...';
      try {
        const response = await fetch('/analytics');
        const data = await response.json();
        if (data.error) { content.innerHTML = data.error; return; }
        let html = `<p><strong>Average Match Score:</strong> ${data.average_score}%</p>`;
        html += `<p><strong>Total Candidates:</strong> ${data.total_candidates}</p>`;
        html += `<p><strong>Fast Trackers Detected:</strong> ${data.fast_trackers}</p>`;
        
        if (data.top_missing_skills && data.top_missing_skills.length) {
          html += `<h4>Top Missing Skills</h4><ul>`;
          data.top_missing_skills.forEach(s => { html += `<li>${s[0]} (Missing in ${s[1]} candidates)</li>`; });
          html += `</ul>`;
        }
        if (data.top_matched_skills && data.top_matched_skills.length) {
          html += `<h4>Top Matched Skills</h4><ul>`;
          data.top_matched_skills.forEach(s => { html += `<li>${s[0]} (Found in ${s[1]} candidates)</li>`; });
          html += `</ul>`;
        }
        content.innerHTML = html;
      } catch (e) {
        content.innerHTML = 'Failed to load analytics.';
      } finally {
        loadAnalyticsBtn.disabled = false;
        loadAnalyticsBtn.textContent = 'Refresh Analytics';
      }
    });
  }

  if (chatBtn) {
    chatBtn.addEventListener('click', () => {
      const chatTabBtn = document.querySelector('[data-tab="tab-chat"]');
      if (chatTabBtn) chatTabBtn.click();
    });
  }

  const chatSubmit = document.getElementById('chat-submit-btn');
  if (chatSubmit) {
    chatSubmit.addEventListener('click', async () => {
      const input = document.getElementById('chat-input').value.trim();
      if (!input) return;
      const resEl = document.getElementById('chat-result');
      resEl.textContent = 'Searching...';
      chatSubmit.disabled = true;
      try {
        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: input })
        });
        const data = await response.json();
        resEl.innerHTML = data.answer || 'No response.';
      } catch (e) {
        resEl.textContent = 'Error connecting to AI.';
      } finally {
        chatSubmit.disabled = false;
      }
    });
  }

  // =======================================================================
  // SIDE-BY-SIDE COMPARISON GRID
  // =======================================================================
  function getSelectedFullCandidates() {
    const checkboxes = document.querySelectorAll('.shortlist-checkbox:checked');
    const selected = [];
    checkboxes.forEach((cb) => {
      const idx = parseInt(cb.dataset.index);
      if (lastCandidates[idx]) {
        selected.push(lastCandidates[idx]);
      }
    });
    return selected;
  }

  if (compareBtn) {
    compareBtn.addEventListener('click', () => {
      const selected = getSelectedFullCandidates();
      if (selected.length < 2) {
        alert('Please select at least 2 candidates using the checkboxes to compare them.');
        return;
      }
      renderComparisonGrid(selected);
      compareOverlay.hidden = false;
      document.body.style.overflow = 'hidden';
    });
  }

  if (closeCompare) closeCompare.addEventListener('click', closeComparisonGrid);
  if (compareOverlay) compareOverlay.addEventListener('click', (e) => { if (e.target === compareOverlay) closeComparisonGrid(); });

  function closeComparisonGrid() {
    compareOverlay.hidden = true;
    document.body.style.overflow = '';
  }

  function renderComparisonGrid(candidates) {
    compareGrid.innerHTML = '';
    const allSkillsSet = new Set();
    candidates.forEach((c) => {
      (c.matched_skills || []).forEach((s) => allSkillsSet.add(s));
      (c.related_skills || []).forEach((r) => allSkillsSet.add(r.required));
      (c.missing_skills || []).forEach((s) => allSkillsSet.add(s));
    });
    const allSkills = Array.from(allSkillsSet).sort();
    if (!allSkills.length) {
      compareGrid.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">No skills to compare.</p>';
      return;
    }

    const table = document.createElement('table');
    table.className = 'compare-table';
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    const skillTh = document.createElement('th');
    skillTh.textContent = 'Required Skill';
    skillTh.className = 'compare-skill-header';
    headerRow.appendChild(skillTh);

    candidates.forEach((c, idx) => {
      const th = document.createElement('th');
      th.className = 'compare-candidate-header';
      const name = c.name.replace(/\.(pdf|docx)$/i, '');
      th.innerHTML = `<span class="compare-rank">#${idx + 1}</span> ${escapeHtml(name)}`;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    allSkills.forEach((skill) => {
      const row = document.createElement('tr');
      const skillTd = document.createElement('td');
      skillTd.className = 'compare-skill-name';
      skillTd.textContent = skill;
      row.appendChild(skillTd);

      candidates.forEach((c) => {
        const td = document.createElement('td');
        td.className = 'compare-cell';
        const matched = (c.matched_skills || []).includes(skill);
        const relatedEntry = (c.related_skills || []).find((r) => r.required === skill);
        const missing = (c.missing_skills || []).includes(skill);

        if (matched) {
          td.classList.add('compare-has');
          td.innerHTML = '<span class="compare-dot compare-dot-green"></span>';
          td.title = 'Has this skill';
        } else if (relatedEntry) {
          td.classList.add('compare-related');
          td.innerHTML = `<span class="compare-dot compare-dot-yellow"></span><span class="compare-found-text">has ${escapeHtml(relatedEntry.found)}</span>`;
          td.title = `Has related: ${relatedEntry.found}`;
        } else if (missing) {
          td.classList.add('compare-missing');
          td.innerHTML = '<span class="compare-dot compare-dot-red"></span>';
          td.title = 'Missing this skill';
        } else {
          td.innerHTML = '<span class="compare-dot compare-dot-gray"></span>';
        }
        row.appendChild(td);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    compareGrid.appendChild(table);
  }

  // =======================================================================
  // SHORTLIST & EMAIL
  // =======================================================================
  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
        const checkboxes = document.querySelectorAll('.shortlist-checkbox');
        let allChecked = true;
        checkboxes.forEach(cb => { if (!cb.checked) allChecked = false; });
        checkboxes.forEach(cb => { cb.checked = !allChecked; });
    });
  }

  if (shortlistBtn) {
    shortlistBtn.addEventListener('click', () => {
      const selected = getShortlistedCandidates();
      if (!selected.length) {
        alert('Please select at least one candidate using the checkboxes on the cards.');
        return;
      }
      if (emailCountEl) {
        emailCountEl.textContent = selected.length;
        const namesUl = document.getElementById('email-selected-names');
        if (namesUl) {
          namesUl.innerHTML = '';
          selected.forEach(c => {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${escapeHtml(c.name)}</strong> — Match: ${c.score}% (TF-IDF: ${c.tfidf_score}%)`;
            namesUl.appendChild(li);
          });
        }
      }
      if (emailResult) { emailResult.hidden = true; emailResult.innerHTML = ''; }
      emailOverlay.hidden = false;
      document.body.style.overflow = 'hidden';
    });
  }

  if (closeEmail) closeEmail.addEventListener('click', closeEmailModal);
  if (emailOverlay) emailOverlay.addEventListener('click', (e) => { if (e.target === emailOverlay) closeEmailModal(); });

  function closeEmailModal() {
    emailOverlay.hidden = true;
    document.body.style.overflow = '';
  }

  function getShortlistedCandidates() {
    const checkboxes = document.querySelectorAll('.shortlist-checkbox:checked');
    const selected = [];
    checkboxes.forEach((cb) => {
      const idx = parseInt(cb.dataset.index);
      if (lastCandidates[idx]) {
        const c = lastCandidates[idx];
        selected.push({
          name: c.name.replace(/\.(pdf|docx)$/i, ''),
          email: c.contact.email,
          score: c.score,
          tfidf_score: Math.round(c.tfidf_score || 0)
        });
      }
    });
    return selected;
  }

  if (sendEmailBtn) {
    sendEmailBtn.addEventListener('click', async () => {
      const selected = getShortlistedCandidates();
      if (!selected.length) return;

      const smtpEmail = document.getElementById('smtp-email').value.trim();
      const smtpPassword = document.getElementById('smtp-password').value;
      const demoEmail = document.getElementById('demo-redirect-email') ? document.getElementById('demo-redirect-email').value.trim() : '';
      const subject = document.getElementById('email-subject').value.trim();
      const body = document.getElementById('email-body').value;

      if (!smtpEmail || !smtpPassword) {
        alert('Please enter your SMTP email and password.');
        return;
      }

      const emailSpinner = sendEmailBtn.querySelector('.spinner');
      const emailBtnLabel = sendEmailBtn.querySelector('.btn-label');
      sendEmailBtn.disabled = true;
      emailSpinner.hidden = false;
      emailBtnLabel.textContent = 'Sending...';

      try {
        const response = await fetch('/send-shortlist-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidates: selected,
            subject: subject,
            body: body,
            smtp_email: smtpEmail,
            smtp_password: smtpPassword,
            demo_email: demoEmail
          })
        });
        const data = await response.json();

        emailResult.hidden = false;
        if (response.ok) {
          let html = `<div class="email-success">Success: ${data.message}</div>`;
          if (data.failed && data.failed.length) {
            html += '<div class="email-failures">';
            data.failed.forEach(f => { html += `<p>Error: ${escapeHtml(f.name)}: ${escapeHtml(f.reason)}</p>`; });
            html += '</div>';
          }
          emailResult.innerHTML = html;
        } else {
          emailResult.innerHTML = `<div class="email-error">Error: ${escapeHtml(data.error || 'Failed to send emails.')}</div>`;
        }
      } catch (err) {
        emailResult.hidden = false;
        emailResult.innerHTML = `<div class="email-error">Error: Network error: ${escapeHtml(err.message)}</div>`;
      } finally {
        sendEmailBtn.disabled = false;
        emailSpinner.hidden = true;
        emailBtnLabel.textContent = 'Send Emails';
      }
    });
  }

  // =======================================================================
  // Kanban Pipeline Logic
  // =======================================================================
  
  function renderKanbanBoard(candidates) {
    const appliedZone = document.querySelector('.kanban-column[data-status="applied"] .kanban-dropzone');
    const otherZones = document.querySelectorAll('.kanban-dropzone');
    if (!appliedZone) return;
    
    // Clear all zones
    otherZones.forEach(z => { z.innerHTML = ''; });
    
    candidates.forEach(c => {
      const card = document.createElement('div');
      card.className = 'kanban-card';
      card.draggable = true;
      card.dataset.name = c.name;
      card.style = 'background: rgba(30, 30, 40, 0.9); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); cursor: grab; user-select: none; transition: transform 0.2s;';
      
      card.innerHTML = `
        <div style="font-weight: 600; font-size: 0.95rem; color: var(--text);">${escapeHtml(c.name.replace(/\.(pdf|docx)$/i, ''))}</div>
        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">Match: <span style="color:var(--accent); font-weight:bold;">${c.score}%</span></div>
        <div style="font-size: 0.8rem; color: var(--text-muted);">Exp: ${c.timeline_audit?.provable_years || 0} yrs</div>
      `;
      
      // Drag Events
      card.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('text/plain', c.name);
        e.dataTransfer.effectAllowed = 'move';
        setTimeout(() => card.style.opacity = '0.5', 0);
      });
      
      card.addEventListener('dragend', () => {
        card.style.opacity = '1';
      });
      
      appliedZone.appendChild(card);
    });
    
    updateKanbanCounts();
  }

  function setupKanbanZones() {
    const zones = document.querySelectorAll('.kanban-dropzone');
    zones.forEach(zone => {
      zone.addEventListener('dragover', (e) => {
        e.preventDefault(); 
        e.dataTransfer.dropEffect = 'move';
        zone.style.background = 'rgba(255,255,255,0.05)';
      });
      
      zone.addEventListener('dragleave', (e) => {
        zone.style.background = 'transparent';
      });
      
      zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.style.background = 'transparent';
        const name = e.dataTransfer.getData('text/plain');
        const card = document.querySelector(`.kanban-card[data-name="${name.replace(/"/g, '\\"')}"]`);
        if (card) {
          zone.appendChild(card);
          updateKanbanCounts();
        }
      });
    });
  }

  function updateKanbanCounts() {
    document.querySelectorAll('.kanban-column').forEach(col => {
      const count = col.querySelectorAll('.kanban-card').length;
      const countEl = col.querySelector('.col-count');
      if (countEl) countEl.textContent = count;
    });
  }

  setupKanbanZones();

  window.renderKanbanBoard = renderKanbanBoard;

  // =======================================================================
  // Floating AI Chatbot Logic
  // =======================================================================
  const chatbotBtn = document.getElementById('floating-chatbot-btn');
  const chatbotWindow = document.getElementById('floating-chatbot-window');
  const chatbotClose = document.getElementById('chatbot-close-btn');
  const chatbotInput = document.getElementById('chatbot-input');
  const chatbotSend = document.getElementById('chatbot-send-btn');
  const chatbotMessages = document.getElementById('chatbot-messages');

  let isChatbotOpen = false;

  function toggleChatbot() {
    isChatbotOpen = !isChatbotOpen;
    if (isChatbotOpen) {
      chatbotWindow.style.opacity = '1';
      chatbotWindow.style.pointerEvents = 'all';
      chatbotWindow.style.transform = 'translateY(0)';
      chatbotInput.focus();
    } else {
      chatbotWindow.style.opacity = '0';
      chatbotWindow.style.pointerEvents = 'none';
      chatbotWindow.style.transform = 'translateY(20px)';
    }
  }

  if (chatbotBtn) chatbotBtn.addEventListener('click', toggleChatbot);
  if (chatbotClose) chatbotClose.addEventListener('click', toggleChatbot);

  async function handleChatbotSend() {
    const text = chatbotInput.value.trim();
    if (!text) return;
    
    // Append user message
    chatbotMessages.innerHTML += `
      <div style="background: var(--accent); padding: 12px; border-radius: 8px; align-self: flex-end; max-width: 85%; color: white; margin-bottom: 8px;">
        ${escapeHtml(text)}
      </div>
    `;
    chatbotInput.value = '';
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

    // Append loading bubble
    const loadingId = 'msg-' + Date.now();
    chatbotMessages.innerHTML += `
      <div id="${loadingId}" style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; align-self: flex-start; max-width: 85%; color: var(--text-muted); margin-bottom: 8px;">
        <span class="spinner" style="display:inline-block; width:12px; height:12px; border-width:2px;"></span> Thinking...
      </div>
    `;
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;

    try {
      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      });
      const data = await response.json();
      document.getElementById(loadingId).outerHTML = `
        <div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; align-self: flex-start; max-width: 85%; color: var(--text); line-height: 1.5; margin-bottom: 8px;">
          ${escapeHtml(data.answer || 'No response.')}
        </div>
      `;
    } catch (e) {
      document.getElementById(loadingId).outerHTML = `
        <div style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; align-self: flex-start; max-width: 85%; color: var(--danger); margin-bottom: 8px;">
          Connection error to AI engine.
        </div>
      `;
    }
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
  }

  if (chatbotSend) chatbotSend.addEventListener('click', handleChatbotSend);
  if (chatbotInput) {
    chatbotInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleChatbotSend();
    });
  }

  // Global Escape key handler
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (compareOverlay && !compareOverlay.hidden) closeComparisonGrid();
      if (emailOverlay && !emailOverlay.hidden) closeEmailModal();
      if (isChatbotOpen) toggleChatbot();
    }
  });

})();