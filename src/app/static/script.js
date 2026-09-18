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

async function loadCharts() {
  try {
    const res = await fetch('/api/data');
    const data = await res.json();
    if (data.error) return;

    // Charts
    new Chart(document.getElementById('stageChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: data.failure_stages.map(d => d.stage),
        datasets: [{
          data: data.failure_stages.map(d => d.count),
          backgroundColor: '#1A73E8',
          borderRadius: 4,
        }],
      },
      options: CHART_DEFAULTS,
    });

    new Chart(document.getElementById('themeChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: data.themes.map(d => d.theme),
        datasets: [{
          data: data.themes.map(d => d.count),
          backgroundColor: '#EA4335',
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        layout: { padding: { left: 10, right: 10 } },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#F1F3F4' }, ticks: { color: '#5F6368', font: { family: 'Plus Jakarta Sans', size: 12 }, stepSize: 1 }, beginAtZero: true },
          y: { grid: { display: false }, ticks: { color: '#202124', font: { family: 'Plus Jakarta Sans', size: 12, weight: '500' } } },
        },
        responsive: true,
        maintainAspectRatio: false,
      },
    });
  } catch (err) {
    console.error('Failed to load chart data:', err);
  }
}

const chatMessages = document.getElementById('chat-messages');
const inputEl = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const suggestionsEl = document.getElementById('suggestions');
let isFirstMessage = true;

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendMessage(role, content, isMarkdown = false) {
  const wrapper = document.createElement('div');
  wrapper.classList.add('message', role);

  const avatar = document.createElement('div');
  avatar.classList.add('avatar');
  if (role === 'user') {
    avatar.textContent = 'YOU';
  } else {
    avatar.classList.add('sparkle');
    avatar.textContent = '✨';
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
    const stage = (s.failure_stage && s.failure_stage !== 'None' && s.failure_stage !== 'null') 
        ? `<span class="source-stage">${s.failure_stage}</span>` : '';
    return `
      <div class="source-card">
        <div class="source-index">${s.index}</div>
        <div class="source-body">
          <div class="source-meta">
            <span class="source-platform">${s.source_label}</span>
            ${stage}
          </div>
          <div class="source-snippet">"${s.snippet}"</div>
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
  inputEl.value = '';
  sendBtn.disabled = true;
  showTypingIndicator();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
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
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

function sendSuggestion(el) { sendMessage(el.textContent); }

inputEl.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(inputEl.value); });
sendBtn.addEventListener('click', () => sendMessage(inputEl.value));

// Mobile FAB Toggle Logic
const chatFab = document.getElementById('chat-fab');
const closeChatBtn = document.getElementById('close-chat-btn');
const chatWidget = document.querySelector('.ai-discovery-engine');

if (chatFab && closeChatBtn && chatWidget) {
  chatFab.addEventListener('click', () => {
    chatWidget.classList.add('active');
    chatFab.style.display = 'none';
  });
  
  closeChatBtn.addEventListener('click', () => {
    chatWidget.classList.remove('active');
    chatFab.style.display = ''; // restore stylesheet rule
  });
}

document.addEventListener('DOMContentLoaded', () => { loadCharts(); inputEl.focus(); });
