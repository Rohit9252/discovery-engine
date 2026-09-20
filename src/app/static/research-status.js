// Render research progress without treating unfinished work as a failed run.
function renderStatusList(id, values) {
  const list = document.getElementById(id);
  if (!list) return;
  const rows = (Array.isArray(values) && values.length) ? values : ['Status details are unavailable.'];
  list.replaceChildren(...rows.map(value => {
    const item = document.createElement('li');
    item.textContent = value;
    return item;
  }));
}

function renderResearchStatus(status) {
  if (!status || !['pending_review', 'no_data', 'running', 'partial', 'completed', 'paused'].includes(status.state)) {
    throw new Error('Research status response is missing or unsupported.');
  }
  const labels = {no_data:'No data', pending_review:'Ready to analyze', running:'Analyzing', partial:'Needs resume', completed:'AI analysis complete', paused:'Paused by you'};
  const stateLabel = document.getElementById('analysis-state-label');
  if (stateLabel) stateLabel.textContent = status.state === 'running' && status.run_phase === 'interpretation_check' ? 'Checking evidence' : labels[status.state];
  const statStages = document.getElementById('stat-stages');
  if (statStages) statStages.textContent = status.retrieval_count === undefined ? 'Not assessed' : status.retrieval_count.toLocaleString();
  const heroTitle = document.getElementById('hero-title-text');
  if (heroTitle) heroTitle.textContent = status.title;
  renderStatusList('hero-pain-points', status.details);
  renderStatusList('hero-opportunities', status.next_steps);
  if (status.catalog_mode) {
    const checklist = [
      `${status.analyzed_count ?? 0} / ${status.total ?? 0} catalog rows assessed; ${status.pending_count ?? 0} pending; ${status.failed_count ?? 0} failed.`,
      `${status.retrieval_count ?? 0} possible user-report issues need a relevance check before they count as findings.`,
      'Web summaries and generated scenarios remain separate from user reports.',
    ];
    renderStatusList('analysis-checklist', checklist);
    return;
  }
  const checklist = [
    `${status.analyzed_count ?? 0} / ${status.total ?? 0} records analyzed; ${status.pending_count ?? 0} pending; ${status.failed_count ?? 0} failed.`,
    `${status.failed_provider_limit_count ?? 0} provider-limit retries; ${status.failed_evidence_validation_count ?? 0} evidence checks; ${status.failed_batch_output_count ?? 0} batch output checks.`,
    `${status.retrieval_count ?? 0} AI-screened reported issues; ${status.incomplete_memory_count ?? 0} explicitly involve incomplete memory; ${status.adjacent_issue_count ?? 0} are adjacent retrieval problems.`,
    `${status.context_count ?? 0} context or positive records excluded from issue findings; ${status.insufficient_context_count ?? 0} lack enough source context.`,
    'Issue evidence spans match source text. AI interpretation still needs human review and interviews.',
  ];
  if (status.phase_scheduled !== undefined && status.phase_scheduled !== null) {
    checklist.splice(1, 0, `Issue screening: ${status.phase_done} / ${status.phase_scheduled} processed; ${status.phase_failed} failed in this pass.`);
  }
  renderStatusList('analysis-checklist', checklist);
}
