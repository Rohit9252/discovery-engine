// Inspect saved research labels and their literal source evidence.
let evidenceOffset = 0;
let evidenceLoading = false;

function evidenceField(label, values) {
  const field = document.createElement('div');
  const name = document.createElement('dt');
  name.textContent = label;
  const value = document.createElement('dd');
  value.textContent = values.length ? values.join(' | ') : 'Not reported in this record';
  field.append(name, value);
  return field;
}

function evidenceCard(record) {
  const card = document.createElement('article');
  card.className = 'insight-card research-evidence-card';
  const meta = document.createElement('p');
  meta.className = 'evidence-reference';
  meta.textContent = `${record.source} · ${record.relevance === 'incomplete_memory' ? 'Explicit incomplete memory' : 'Retrieval feedback'}`;
  const title = document.createElement('h3');
  title.textContent = record.rationale;
  const quote = document.createElement('blockquote');
  quote.textContent = record.evidence_quotes.join(' / ');
  const fields = document.createElement('dl');
  fields.className = 'evidence-fields';
  fields.append(evidenceField('Remembered clues', record.remembered_clues),
    evidenceField('Explicitly missing details', record.missing_details),
    evidenceField('Attempted queries / actions', record.attempted_queries),
    evidenceField('Workarounds used', record.workarounds));
  const outcome = document.createElement('p');
  outcome.className = 'evidence-reference';
  outcome.textContent = `Outcome: ${record.outcome.replaceAll('_', ' ')} · ${record.failure_mechanism === 'not_reported' ? 'Interpretation' : 'Failure mechanism'}: ${record.interpretation}`;
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Read original feedback';
  const source = document.createElement('p');
  source.className = 'original-feedback';
  source.textContent = record.source_text;
  details.append(summary, source);
  const identity = document.createElement('p');
  identity.className = 'evidence-reference';
  identity.textContent = `Record ${record.review_id} · AI assessed, not human reviewed`;
  card.append(meta, title, quote, fields, outcome, details, identity);
  try {
    const url = new URL(record.url);
    if (['http:', 'https:'].includes(url.protocol)) {
      const link = document.createElement('a');
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.className = 'source-url';
      link.textContent = record.source === 'app_store' ? 'Open app listing (individual review link unavailable) ↗' : 'View source ↗';
      card.append(link);
    }
  } catch { /* Original stored feedback remains inspectable without a direct URL. */ }
  return card;
}

async function loadResearchEvidence(reset = false) {
  if (evidenceLoading) return;
  evidenceLoading = true;
  const grid = document.getElementById('research-evidence-grid');
  const button = document.getElementById('evidence-load-more');
  const status = document.getElementById('evidence-status');
  const category = document.getElementById('evidence-category').value;
  try {
    if (reset) evidenceOffset = 0;
    button.disabled = true;
    const response = await fetch(`/api/research/evidence?category=${category}&offset=${evidenceOffset}&limit=6`);
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || 'Evidence request failed.');
    if (reset) grid.replaceChildren();
    grid.append(...data.records.map(evidenceCard));
    evidenceOffset += data.records.length;
    status.textContent = data.total ? `Showing ${evidenceOffset} of ${data.total} matching AI-assessed records. Missing fields mean the author did not report them.` :
      (data.analysis_status === 'completed' ? 'No records match this filter. Try all retrieval feedback.' : 'Evidence will appear as analysis batches finish. This page updates automatically.');
    button.hidden = evidenceOffset >= data.total;
  } catch (error) {
    status.textContent = `Could not load evidence: ${error.message}`;
  } finally {
    evidenceLoading = false;
    button.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('evidence-category').addEventListener('change', () => loadResearchEvidence(true));
  document.getElementById('evidence-load-more').addEventListener('click', () => loadResearchEvidence());
  loadResearchEvidence(true);
});
