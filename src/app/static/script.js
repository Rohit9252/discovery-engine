function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }
function safeSourceLink(value) { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? `<a class="source-url" href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer">View source ↗</a>` : ''; } catch { return '<p class="evidence-reference">Direct source link unavailable</p>'; } }

function isMobileViewport() {
  return window.matchMedia('(max-width: 768px)').matches;
}

function truncateChartLabel(value, maxLen) {
  const text = String(value ?? '');
  if (text.length <= maxLen) return text;
  return `${text.slice(0, Math.max(0, maxLen - 1))}...`;
}

// Discovery Engine - Frontend Logic

const CHART_DEFAULTS = {
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: '#F1F3F4' }, ticks: { color: '#5F6368', font: { family: 'Plus Jakarta Sans', size: 12 } } },
    y: { grid: { color: '#F1F3F4' }, ticks: { color: '#5F6368', font: { family: 'Plus Jakarta Sans', size: 12 }, stepSize: 1 }, beginAtZero: true },
  },
  animation: { duration: 800, easing: 'easeOutQuart' },
  responsive: true,
  maintainAspectRatio: false,
};
let themeChart = null;
let researchSignature = '';
let researchPollBusy = false;

async function loadCharts() {
  try {
    const res = await fetch('/api/data');
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || 'Dashboard request failed.');

    // Update live data elements
    const updateEl = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    
    updateEl('stat-total-reviews', (data.stored_count ?? data.total_reviews)?.toLocaleString() || '0');
    updateEl('stat-cleaned', data.cleaned_count?.toLocaleString() || '0');
    updateEl('stat-themes', data.themes_count || '0');
    
    // We intentionally ignore stat-stages now, as it's not strictly necessary for the new redesign layout.
    // If we wanted it, we'd render it here.

    if (typeof renderResearchStatus === 'function') {
      renderResearchStatus(data.research_status);
    }
    
    researchSignature = JSON.stringify(data.research_status);
    const catalogMode = data.analysis_method === 'phase1_catalog_assessment';
    const assessed = data.analysis_method === 'source_grounded_issue_assessment' || catalogMode;
    updateEl('insights-section-title', catalogMode ? 'Findings awaiting relevance check' : assessed ? 'Reported Retrieval Issues' : 'Provisional Feedback Topics');
    updateEl('stat-themes-label', catalogMode ? 'Possible Issue Patterns' : assessed ? 'Issue Research Groups' : 'Provisional Topics');
    updateEl('stat-total-label', catalogMode ? 'Phase 1 Catalog Rows' : 'Collected Feedback Records');
    updateEl('stat-cleaned-label', catalogMode ? 'AI Assessed Rows' : 'Available Feedback Records');
    updateEl('stat-stages-label', catalogMode ? 'Possible User Reports' : 'Reported Issue Candidates');
    updateEl('theme-chart-title', catalogMode ? 'Early Retrieval Patterns' : assessed ? 'Reported Retrieval Barriers' : 'Topic Mentions (Keyword Counts)');
    
    updateEl('chart-n-label', catalogMode ? `N=${data.research_status?.retrieval_count || 0} possible user-report issues; tags can overlap` : assessed ? `N=${data.research_status?.retrieval_count || 0} AI-screened issue records` : `N=${data.total_reviews} available records`);
    updateEl('hero-count', data.total_reviews?.toLocaleString() || '0');
    updateEl('context-total-records', data.total_reviews?.toLocaleString() || '0');
    updateEl('hero-sources', data.sources_connected || '0');

    // Charts

    // data-status elements were removed from UI to clean up layout.
    // The dataset cards show the key metrics instead.


    // Initialize Charts
    if (typeof ChartDataLabels !== 'undefined') Chart.register(ChartDataLabels);
    if (window.signalsChartInstance) window.signalsChartInstance.destroy();
    if (window.severityChartInstance) window.severityChartInstance.destroy();
    if (window.entitiesChartInstance) window.entitiesChartInstance.destroy();
    if (window.methodsChartInstance) window.methodsChartInstance.destroy();

    const mobile = isMobileViewport();
    const barLabelMax = mobile ? 28 : 48;
    const barPadding = mobile
      ? { left: 8, right: 28 }
      : { left: 40, right: 40 };
    const barTickFont = { family: 'Plus Jakarta Sans', size: mobile ? 10 : 11 };
    const doughnutLegend = {
      position: mobile ? 'bottom' : 'right',
      labels: { font: { family: 'Plus Jakarta Sans', size: mobile ? 10 : 11 }, usePointStyle: true, padding: mobile ? 12 : 16 },
    };

    const ctxSignals = document.getElementById('signalsChart');
    if (ctxSignals && data.themes) {
      window.signalsChartInstance = new Chart(ctxSignals, {
        type: 'bar',
        data: {
          labels: data.themes.map(t => t.theme),
          datasets: [{
            label: 'Items',
            data: data.themes.map(t => t.count),
            backgroundColor: '#1967D2',
            borderRadius: 4
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: barPadding },
          plugins: { 
            legend: { display: false },
            datalabels: {
              anchor: 'end',
              align: 'right',
              color: '#1967D2',
              font: { weight: 'bold', family: 'Plus Jakarta Sans', size: mobile ? 11 : 12 },
              formatter: function(value) { return value; }
            }
          },
          scales: {
            x: { display: false, grid: { display: false } },
            y: {
              grid: { display: false },
              ticks: {
                font: barTickFont,
                autoSkip: false,
                callback: function(value) {
                  return truncateChartLabel(this.getLabelForValue(value), barLabelMax);
                },
              },
            },
          },
        }
      });
    }

    const ctxSeverity = document.getElementById('severityChart');
    if (ctxSeverity && data.frustration_severity) {
      window.severityChartInstance = new Chart(ctxSeverity, {
        type: 'doughnut',
        data: {
          labels: data.frustration_severity.map(s => s.level),
          datasets: [{
            data: data.frustration_severity.map(s => s.count),
            backgroundColor: ['#EA4335', '#FBBC04', '#34A853'], /* Red, Yellow, Green */
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: doughnutLegend,
            datalabels: { color: '#ffffff', font: { weight: 'bold', family: 'Plus Jakarta Sans', size: mobile ? 11 : 12 } }
          },
          cutout: '70%'
        }
      });
    }

    const ctxEntities = document.getElementById('entitiesChart');
    if (ctxEntities && data.failing_entities) {
      window.entitiesChartInstance = new Chart(ctxEntities, {
        type: 'doughnut',
        data: {
          labels: data.failing_entities.map(e => e.entity),
          datasets: [{
            data: data.failing_entities.map(e => e.count),
            backgroundColor: ['#1967D2', '#1A73E8', '#4285F4', '#8AB4F8', '#D2E3FC'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: doughnutLegend,
            datalabels: { color: '#ffffff', font: { weight: 'bold', family: 'Plus Jakarta Sans', size: mobile ? 11 : 12 } }
          },
          cutout: '70%'
        }
      });
    }

    const ctxMethods = document.getElementById('methodsChart');
    if (ctxMethods && data.search_methods) {
      window.methodsChartInstance = new Chart(ctxMethods, {
        type: 'bar',
        data: {
          labels: data.search_methods.map(m => m.method),
          datasets: [{
            data: data.search_methods.map(m => m.count),
            backgroundColor: '#34A853',
            borderRadius: 4
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: barPadding },
          plugins: { 
            legend: { display: false },
            datalabels: {
              anchor: 'end',
              align: 'right',
              color: '#34A853',
              font: { weight: 'bold', family: 'Plus Jakarta Sans', size: mobile ? 11 : 12 },
              formatter: function(value) { return value; }
            }
          },
          scales: {
            x: { display: false, grid: { display: false } },
            y: {
              grid: { display: false },
              ticks: {
                font: barTickFont,
                autoSkip: false,
                callback: function(value) {
                  return truncateChartLabel(this.getLabelForValue(value), barLabelMax);
                },
              },
            },
          },
        }
      });
    }

    // Hydrate Verbatims
    const verbatimsList = document.getElementById('verbatims-list');
    if (verbatimsList) {
      if (data.verbatims && data.verbatims.length > 0) {
verbatimsList.innerHTML = data.verbatims.map(v => `
          <div class="verbatim-card" style="padding: 16px; background: #F8F9FA; border-left: 3px solid var(--google-blue); margin-bottom: 12px; border-radius: 4px;">
            <p style="margin: 0 0 8px 0; font-size: 14px; font-style: italic; color: var(--text-primary);">"${escapeHtml(v.text)}"</p>
            <div style="font-size: 12px; font-weight: 600;">
              <a href="${v.url || '#'}" target="_blank" style="color: var(--google-blue); text-decoration: none;">↗ ${escapeHtml(v.source)}</a>
            </div>
          </div>
        `).join('');
      } else {
        verbatimsList.innerHTML = `
          <div style="display: flex; align-items: center; gap: 12px; padding: 16px; background: #E8F0FE; border-radius: 8px; color: var(--google-blue);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 8v4"></path><path d="M12 16h.01"></path></svg>
            <span style="font-weight: 500; font-size: 14px;">AI is currently extracting user quotes...</span>
          </div>
        `;
      }
    }
  } catch (err) {
    const dataStatus = document.getElementById('data-status');
    if (dataStatus) dataStatus.textContent = `Could not load feedback: ${err.message} Refresh after checking the server.`;
    ['stat-total-reviews', 'stat-cleaned', 'stat-themes', 'stat-stages'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'Unavailable';
    });
    const stateLabel = document.getElementById('analysis-state-label');
    if (stateLabel) stateLabel.textContent = 'Status unavailable';
    if (typeof renderStatusList === 'function') {
      renderStatusList('analysis-checklist', ['Could not load analysis status. Check the server and refresh.']);
    }
  }
}

const chatMessages = document.getElementById('chat-messages');
const inputEl = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const suggestionsEl = document.getElementById('suggestions');
let isFirstMessage = true;

function scrollToBottom() {
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function sendSuggestion(text) {
  if (!text) return;
  const input = document.getElementById('chat-input');
  if (input) {
    input.value = text;
    // Switch to chat tab if not active
    switchTab('chat');
    document.getElementById('send-btn').click();
  }
}

function appendMessage(role, content, isMarkdown = false) {
  if (!chatMessages) return null;
  const wrapper = document.createElement('div');
  wrapper.classList.add('message', role);


  const avatar = document.createElement('div');
  avatar.classList.add('avatar');
  if (role === 'user') {
    avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>';
  } else {
    avatar.classList.add('sparkle');
    avatar.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="var(--google-blue)"><path d="M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z"/></svg>';
  }


  const bubble = document.createElement('div');
  bubble.classList.add('bubble');

  if (isMarkdown && typeof marked !== 'undefined') {
    bubble.innerHTML = marked.parse(content);
  } else {
    bubble.textContent = content;
  }

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
  return bubble;
}

function showTypingIndicator() {
  if (!chatMessages) return null;
  const wrapper = document.createElement('div');
  wrapper.classList.add('message', 'assistant');
  wrapper.id = 'typing-indicator';

  const avatar = document.createElement('div');
  avatar.classList.add('avatar', 'sparkle');
  avatar.textContent = '✨';

  const bubble = document.createElement('div');
  bubble.classList.add('bubble');
  bubble.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function renderSources(sources, rewrittenQuestion, originalQuestion) {
  if (!sources || sources.length === 0) return '';
  const cards = sources.map(s => {
    const displayStage = (s.failure_stage && s.failure_stage !== 'None' && s.failure_stage !== 'null') 
        ? s.failure_stage : 'Uncategorized';
    const stage = `<span class="source-stage" style="background-color: #f1f3f4; color: #5f6368;">${escapeHtml(displayStage)}</span>`;
    return `
      <div class="source-card">
        <div class="source-index">${s.index}</div>
        <div class="source-body">
          <div class="source-meta">
            <span class="source-platform">${escapeHtml(s.source_label)}</span>
            ${safeSourceLink(s.url)}
            ${stage}
          </div>
          <div class="source-snippet">
            <span class="snippet-short">"${escapeHtml(s.snippet)}"</span>
            ${s.full_text && s.full_text.length > 160 ? `<span class="snippet-full" style="display:none;">"${escapeHtml(s.full_text)}"</span><a href="#" onclick="this.previousElementSibling.style.display='inline'; this.previousElementSibling.previousElementSibling.style.display='none'; this.style.display='none'; return false;" style="color: var(--google-blue); text-decoration: none; font-size: 11px; margin-left: 4px; font-weight: 500;">See more</a>` : ''}
          </div>
        </div>
      </div>`;
  }).join('');

  return `
    <div class="sources-section">
      <div class="sources-label">Research Evidence Retrieved</div>
      <div class="source-cards">${cards}</div>
    </div>`;
}

async function sendMessage(text) {
  const question = text.trim();
  if (!question) return;
  
  if (isFirstMessage) {
    const welcomeMsg = document.getElementById('welcome-msg');
    if (welcomeMsg) welcomeMsg.style.display = 'none';
    isFirstMessage = false;
  }
  
  if (suggestionsEl) suggestionsEl.style.display = 'none';

  appendMessage('user', question);
  if (inputEl) inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  showTypingIndicator();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || 'Chat request failed.');
    document.getElementById('typing-indicator')?.remove();
    
    const sourcesHtml = renderSources(data.sources, data.rewritten_question, question);
    let answerMd = data.answer || 'No response returned.';
    
    // Highlight citations like [1], [2] in the markdown text
    answerMd = answerMd.replace(/\[\d+\]/g, match => `<span class="citation-highlight">${match}</span>`);
    
    const bubble = appendMessage('assistant', '', true);
    if (typeof marked !== 'undefined') {
      bubble.innerHTML = marked.parse(answerMd) + sourcesHtml;
    } else {
      bubble.innerHTML = answerMd + sourcesHtml;
    }
    scrollToBottom();
  } catch (err) {
    document.getElementById('typing-indicator')?.remove();
    appendMessage('assistant', `Error: ${err.message}`, false);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
  }
}

// --- UI Redesign Logic ---

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  
  const activeBtn = document.querySelector(`button[onclick="switchTab('${tabId}')"]`);
  if (activeBtn) activeBtn.classList.add('active');
  
  const activePane = document.getElementById(`tab-${tabId}`);
  if (activePane) activePane.classList.add('active');

  document.body.classList.toggle('chat-tab-active', tabId === 'chat');
}

function closeModal() {
  const modal = document.getElementById('instruction-modal');
  if (modal) {
    modal.classList.add('hidden');
    localStorage.setItem('discovery_modal_seen', 'true');
  }
}

async function loadInsights() {
  try {
    const res = await fetch('/api/insights');
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || 'Evidence request failed.');
    
    // Inject strongest signal hero card
    if (data.strongest_signal) {
      const updateEl = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
      updateEl('hero-title-text', data.strongest_signal.title);
      
      const descEl = document.getElementById('hero-description');
      if (descEl) descEl.textContent = data.strongest_signal.description;
      
      if (typeof renderStatusList === 'function') {
        renderStatusList('hero-pain-points', data.strongest_signal.pain_points);
        renderStatusList('hero-opportunities', data.strongest_signal.opportunities);
      }
    }

    const insights = data.insights || [];
    if (!Array.isArray(insights)) return;

    const grid = document.getElementById('insights-grid');
    if (!grid) return;
    grid.innerHTML = '';
    if (!insights.length) grid.textContent = 'The catalog is connected. Source examples will appear after the relevance check.';

    insights.forEach((insight, index) => {
      const card = document.createElement('div');
      card.className = 'insight-card';
      card.innerHTML = `
        <h3 class="blue-title">${escapeHtml(insight.title?.toUpperCase() || '')}</h3>
        <p>${escapeHtml(insight.summary)}</p>
        <blockquote>"${escapeHtml(insight.quote)}"${insight.quote_truncated ? " (excerpt)" : ""}</blockquote>
        <p class="evidence-reference">${escapeHtml(insight.source)} · Record ${escapeHtml(insight.evidence_id)}</p>
        ${safeSourceLink(insight.url)}
        <span class="pill-tag">${insight.review_count} records • ${escapeHtml(insight.theme_tag)}</span>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    const grid = document.getElementById('insights-grid');
    if (grid) grid.textContent = `Could not load evidence: ${err.message}`;
    const titleText = document.getElementById('hero-title-text');
    if (titleText) titleText.textContent = 'Evidence unavailable';
    const desc = document.getElementById('hero-description');
    if (desc) desc.textContent = 'Check the server and refresh.';
    ['hero-pain-points', 'hero-opportunities'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'Unavailable';
    });
  }
}

if (inputEl) {
  inputEl.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(inputEl.value); });
}
if (sendBtn) {
  sendBtn.addEventListener('click', () => sendMessage(inputEl.value));
}

document.addEventListener('DOMContentLoaded', () => { 
  const modal = document.getElementById('instruction-modal');
  if (modal) {
    modal.classList.remove('hidden');
  }
  loadCharts(); 
  loadInsights(); 
  if (inputEl) inputEl.focus(); 
});

setInterval(async () => {
  if (document.hidden || researchPollBusy) return;
  researchPollBusy = true;
  try {
    const response = await fetch('/api/data');
    if (!response.ok) return;
    const data = await response.json();
    if (JSON.stringify(data.research_status) !== researchSignature) {
      await loadCharts();
      await loadInsights();
    }
  } catch { /* Existing saved findings remain visible during a brief network interruption. */ }
  finally { researchPollBusy = false; }
}, 15000);
