function renderDatabaseEvaluation(result) {
  const panel = document.getElementById('panel-evaluation');
  if (!result || !['recorded', 'stale'].includes(result.status)) {
    panel.innerHTML = `<div class="card"><h3>Evaluation has not been recorded</h3><p>${esc(result?.message || 'No result file is available.')}</p><p>Run the isolated evaluation command on the target database engines. Live constraint checks alone do not establish concurrency, recovery or performance.</p><pre>python scripts/run_database_evaluation.py --full-suite</pre><p>For the portable Docker installation, run:</p><pre>docker compose --env-file .env.laptop -f compose.laptop.yaml --profile evaluation run --build --rm evaluate</pre></div>`;
    return;
  }
  const areas = ['MongoDB operations', 'Cross-database behaviour', 'Concurrency and recovery', 'Controlled benchmarks', 'Evidence integrity'];
  const experiments = result.experiments || [];
  const summaries = areas.map(area => {
    const rows = experiments.filter(row => row.evidence.area === area);
    return [area, rows.length ? `${rows.filter(row => row.outcome === 'passed').length}/${rows.length} experiments passed` : 'No experiments recorded'];
  });
  const current = result.currentSource === true;
  const engine = experiments.find(row => row.evidence.engines)?.evidence.engines || {};
  const summary = result.passed && current ? 'Recorded experiments passed' : 'Review the evaluation status';
  panel.innerHTML = `<div class="card accent"><p class="eyebrow">Correctness before features</p><h3>${summary}</h3><p>Recorded ${esc(new Date(result.finishedAt).toLocaleString())} · ${esc(result.environment.sqlTarget)} ${esc(engine.sql)} · MongoDB ${esc(engine.mongo)}</p><p>${esc(result.scope)}</p>${table(['Evaluation area','Recorded result'], summaries)}<p class="caption">${esc(result.fullSuite ? 'Full regression suite' : 'Focused evaluation')}: ${esc(JSON.stringify(result.summary))} · ${esc(result.seconds)} seconds. ${current ? 'Source fingerprint matches this backend and test suite.' : 'STALE: the code changed after this run; repeat the evaluation.'}</p><details><summary>Reproduce this evaluation</summary><div class="detail-body"><pre>python scripts/run_database_evaluation.py --full-suite</pre><p>Configure MARIADB_TEST_ADMIN_URL and MONGODB_TEST_URI privately. Each experiment uses new disposable databases. For the local SQLite/Mongo preview, add --env .env.demo.</p><p>No load or outage experiment is run against the live catalogue by this page. Refresh data reads the latest recorded file; Run all checks runs only the existing safe live probes.</p><code>${esc(result.sourceSha256)}</code></div></details></div>`;
  for (const area of areas) {
    const rows = experiments.filter(row => row.evidence.area === area);
    panel.innerHTML += `<div class="card"><h3>${esc(area)}</h3>${rows.length ? rows.map(row => {
      const observation = row.evidence.observed || {};
      const benchmark = observation.indexed && observation.scan;
      return `<details open><summary>${row.outcome === 'passed' ? 'PASS' : esc(row.outcome.toUpperCase())} · ${esc(row.evidence.invariant)}</summary><div class="detail-body">${benchmark ? `<p>${esc(observation.datasetRows.toLocaleString())} records · ${esc(observation.warmupsPerVariant)} warm-ups and ${esc(observation.repetitionsPerVariant)} measured runs per variant · ${esc(observation.order)}.</p>${table(['Variant','Median ms','p95 ms','Returned','Documents examined'], ['indexed','scan'].map(name => [name, observation[name].medianMs, observation[name].p95Ms, observation.resultRows, observation[name+'Plan']?.documentsExamined ?? 'See SQL plan']))}<p>Both variants returned identical ordered results. SQL plans are optimizer estimates; MongoDB executionStats reports actual documents examined. Timing ratios are workload-specific.</p>` : ''}${pretty(observation)}<p class="caption">${esc(row.test)} · ${esc(row.seconds.toFixed(3))} seconds</p></div></details>`;
    }).join('') : '<p>No recorded experiments for this area.</p>'}</div>`;
  }
  panel.innerHTML += `<div class="card"><h3>What these results do not prove</h3><ul>${result.limits.map(item => `<li>${esc(item)}</li>`).join('')}</ul><p>A passing experiment confirms its stated invariant, including tests that expose a known limitation. It does not mean all failure modes have been solved.</p></div>`;
}
