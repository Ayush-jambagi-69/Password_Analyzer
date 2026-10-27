/* PasswordLab frontend. Vanilla JS. Passwords are inspected locally; only derived metrics go to the local Python API.
   Nothing is written to localStorage/sessionStorage/cookies. No console logging of input. */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const DEFAULT_SYMBOLS = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~';
const debounce = (f, ms = 200) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; };
const bits = v => Number(v).toFixed(2);
const RATES = [[10, 'Online, rate-limited (10 per second)'], [1e3, 'Online, no limiting (1,000 per second)'], [1e5, 'Offline, deliberately slow hash (100,000 per second)'], [1e10, 'Offline, fast hash on a GPU rig (10 billion per second)']];

/* ---------- API ---------- */
async function api(path, body) {
  try {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => null);
    if (!j) return { ok: false, errors: ['The server sent a response that could not be read.'] };
    return j;
  } catch (e) {
    return { ok: false, network: true, errors: ['Cannot reach the PasswordLab server. Start it with run.bat (or python backend/app.py) and open http://127.0.0.1:5000 (do not open index.html directly).'] };
  }
}
const errBox = errs => `<div class="err" role="alert"><strong>Cannot calculate</strong><ul>${errs.map(e => `<li>${esc(e)}</li>`).join('')}</ul></div>`;

/* ---------- Routing ---------- */
const views = ['analyzer', 'lab', 'compare', 'learn'];
function route() {
  const h = (location.hash || '#analyzer').slice(1);
  const v = views.includes(h) ? h : 'analyzer';
  views.forEach(n => { $('#' + n).hidden = n !== v; });
  document.querySelectorAll('#nav a').forEach(a => { if (a.getAttribute('href') === '#' + v) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  if (v === 'lab') labRun(); if (v === 'compare') cmpRun();
}
window.addEventListener('hashchange', () => { route(); $('#main').focus(); });

/* ---------- Reusable controls ---------- */
let uid = 0;
function rateControl(root, onChange, def = 1e10) {
  const id = 'r' + (++uid);
  root.innerHTML = `<div><label for="${id}s">Assumed guessing rate (illustrative presets)</label><select id="${id}s">${RATES.map(([v, t]) => `<option value="${v}" ${v === def ? 'selected' : ''}>${esc(t)}</option>`).join('')}<option value="custom">Custom rate</option></select></div>
    <div><label for="${id}n">Guesses per second</label><input id="${id}n" type="number" min="0" step="any" value="${def}"></div>`;
  const s = $('select', root), n = $('input', root);
  s.onchange = () => { if (s.value !== 'custom') n.value = s.value; onChange(); };
  n.oninput = () => { s.value = RATES.some(r => String(r[0]) === n.value) ? n.value : 'custom'; onChange(); };
  return { get: () => Number(n.value) };
}

function configForm(root, o = {}) {
  const id = 'f' + (++uid), L0 = o.length || 12;
  root.innerHTML = `
  <div class="field"><label for="${id}L">Length L</label><div class="row"><input type="range" min="1" max="64" value="${Math.min(L0, 64)}" aria-label="Length slider"><input type="number" id="${id}L" min="1" max="1024" value="${L0}"></div></div>
  <fieldset class="field"><legend>Character sets</legend><div class="checks">
    <label><input type="checkbox" data-k="lower" ${o.lower === false ? '' : 'checked'}>Lowercase <span class="chip">26</span></label>
    <label><input type="checkbox" data-k="upper" ${o.upper ? 'checked' : ''}>Uppercase <span class="chip">26</span></label>
    <label><input type="checkbox" data-k="digits" ${o.digits ? 'checked' : ''}>Digits <span class="chip">10</span></label>
    <label><input type="checkbox" data-k="symbols" ${o.symbols ? 'checked' : ''}>Symbols <span class="chip sc">32</span></label></div></fieldset>
  <div class="field"><label for="${id}S">Symbol set</label><input id="${id}S" class="mono-in" autocomplete="off" spellcheck="false"><small>Characters that are also letters or digits are counted once (set union).</small></div>
  <details class="field"><summary>Custom pool (optional)</summary><div style="margin-top:10px"><label><input type="checkbox" data-k="useCustom">Use only this custom pool</label>
    <input id="${id}C" class="mono-in" autocomplete="off" spellcheck="false" placeholder="e.g. 0123456789abcdef" aria-label="Custom pool"><small>Printable ASCII only. Duplicates are counted once.</small></div></details>
  ${o.required ? `<fieldset class="field"><legend>Policy: require at least one</legend><div class="checks">
    ${[['lower', 'Lowercase'], ['upper', 'Uppercase'], ['digit', 'Digit'], ['symbol', 'Symbol']].map(([k, t]) => `<label><input type="checkbox" data-r="${k}">${t}</label>`).join('')}</div></fieldset>` : ''}`;
  $('#' + id + 'S').value = o.symbolSet || DEFAULT_SYMBOLS;
  const num = $('#' + id + 'L'), rng = $('input[type=range]', root);
  const symInput = $('#' + id + 'S'), sc = $('.sc', root);
  const upd = () => { sc.textContent = new Set(symInput.value).size; };
  upd();
  rng.oninput = () => { num.value = rng.value; };
  num.addEventListener('input', () => { if (+num.value >= 1 && +num.value <= 64) rng.value = num.value; });
  symInput.addEventListener('input', upd);
  const get = () => ({
    length: num.value === '' ? null : Number(num.value),
    lower: $('[data-k=lower]', root).checked, upper: $('[data-k=upper]', root).checked,
    digits: $('[data-k=digits]', root).checked, symbols: $('[data-k=symbols]', root).checked,
    symbolSet: symInput.value, useCustom: $('[data-k=useCustom]', root).checked, customPool: $('#' + id + 'C').value,
    required: [...root.querySelectorAll('[data-r]:checked')].map(x => x.dataset.r)
  });
  const on = cb => { root.addEventListener('input', cb); root.addEventListener('change', cb); };
  const set = p => { Object.entries(p).forEach(([k, v]) => { const el = $(`[data-k=${k}]`, root); if (el) el.checked = v; }); if (p.length) { num.value = p.length; rng.value = Math.min(p.length, 64); } };
  return { get, on, set };
}

/* ---------- Rendering of backend reports ---------- */
const metric = (l, v, s = '') => `<div class="metric"><span>${esc(l)}</span><b class="mono">${esc(v)}</b><small>${esc(s)}</small></div>`;
function metricsHTML(d) {
  const s = d.searchSpace, g = d.guessing, p = d.pool;
  return `<div class="metrics">
    ${metric('Character pool R', p.size, `lower ${p.lower}, upper ${p.upper}, digits ${p.digits}, symbols ${p.symbols}` + (p.overlapRemoved ? `; ${p.overlapRemoved} duplicate(s) removed` : ''))}
    ${metric('Search space N = R^L', s.exact || s.scientific, `${s.scientific}, ${s.digits} digits`)}
    ${metric('Entropy H = L log2 R', bits(d.entropyBits) + ' bits', 'uniform random model')}
    ${metric('Average time N / 2G', g.average.human, g.average.seconds)}
    ${metric('Worst-case time N / G', g.worst.human, g.worst.seconds)}</div>`;
}
const stepsHTML = d => `<ul class="steps">${d.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ul><ul class="assume">${d.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul>`;
function constrainedHTML(c) {
  if (!c) return '';
  return `<h2 style="margin-top:20px">Policy-constrained count</h2>
  <div class="metrics">${metric('Valid strings', c.count, c.scientific)}${metric('Entropy of valid set', bits(c.entropyBits) + ' bits', 'log2 of the valid count')}${metric('Share of all strings', (c.fractionOfAll * 100).toFixed(c.fractionOfAll < 0.01 ? 4 : 2) + '%', 'valid / unrestricted')}</div>
  <p class="small">${esc(c.formula)}. ${esc(c.assumption)}</p>
  <div class="tw"><table><thead><tr><th>Term</th><th>Sign</th><th>|union|</th><th>(R − |union|)^L</th></tr></thead><tbody>
  ${c.terms.map(t => `<tr><td>${esc(t.subset)}</td><td class="${t.sign > 0 ? 'pos' : 'neg'}">${t.sign > 0 ? '+' : '−'}</td><td>${t.unionSize}</td><td class="mono">${esc(t.value)}</td></tr>`).join('')}</tbody></table></div>`;
}

/* ---------- Charts ---------- */
Chart.defaults.color = '#a4b0d6'; Chart.defaults.borderColor = '#243157'; Chart.defaults.font.family = 'Segoe UI, system-ui, sans-serif';
const charts = {}, PAL = ['#53d9ff', '#9b8cff', '#4ade80', '#fbbf24', '#ff6b7f'];
function draw(id, cfg) { if (charts[id]) charts[id].destroy(); cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: { duration: 250 } }, cfg.options); charts[id] = new Chart($('#' + id), cfg); }
const axis = t => ({ title: { display: true, text: t }, grid: { color: '#1c2748' } });

/* ============ ANALYZER ============ */
const WORDS = ['password', 'passw0rd', 'qwerty', 'letmein', 'welcome', 'admin', 'login', 'iloveyou', 'monkey', 'dragon', 'football', 'baseball', 'master', 'shadow', 'sunshine', 'princess', 'trustno1', 'abc123', 'secret', 'hello', 'summer', 'winter', 'india', 'cricket'];
const ROWS = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm', '1234567890'];
const LEET = { '0': 'o', '1': 'l', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's', '!': 'i' };
function inspect(pw, R) {
  const lr = Math.log2(Math.max(R, 2)), warn = [], found = []; let pen = 0;
  for (const m of pw.matchAll(/(.)\1{2,}/g)) { pen += (m[0].length - 1) * lr; warn.push(`Repeated character run "${m[0].slice(0, 12)}" (${m[0].length} in a row).`); }
  const low = pw.toLowerCase();
  let seq = 1;
  for (let i = 1; i <= low.length; i++) {
    const d = i < low.length ? low.charCodeAt(i) - low.charCodeAt(i - 1) : 0;
    const prev = i > 1 ? low.charCodeAt(i - 1) - low.charCodeAt(i - 2) : 0;
    if (i < low.length && Math.abs(d) === 1 && (seq === 1 || d === prev)) seq++;
    else { if (seq >= 3) { pen += (seq - 1) * lr * 0.9; warn.push(`Sequential run of ${seq} characters (like abc or 321).`); } seq = Math.abs(d) === 1 && i < low.length ? 2 : 1; }
  }
  for (const row of ROWS) for (let k = 4; k <= row.length; k++) for (let i = 0; i + k <= row.length; i++) {
    const s = row.slice(i, i + k), r = [...s].reverse().join('');
    if (low.includes(s) || low.includes(r)) { warn.push(`Keyboard pattern "${s}".`); pen += (k - 1) * lr * 0.9; k = 99; break; }
  }
  const norm = [...low].map(c => LEET[c] || c).join('');
  for (const w of WORDS) if (norm.includes(w) || low.includes(w)) { pen += Math.max(0, w.length * lr - 10); warn.push(`Contains the very common word "${w}" (even with look-alike substitutions).`); found.push(w); }
  if (/(19|20)\d{2}/.test(pw)) { pen += Math.max(0, 4 * lr - 7); warn.push('Contains a year-like number, which is easy to guess.'); }
  if (/^[A-Za-z]+\d{1,4}[^A-Za-z0-9]?$/.test(pw)) { pen += 6; warn.push('Shape "letters, then a few digits or one symbol" is extremely common.'); }
  return { warn, pen };
}
const LEVELS = [['Very Weak', '#ff6b7f'], ['Weak', '#fb923c'], ['Moderate', '#fbbf24'], ['Strong', '#53d9ff'], ['Very Strong', '#4ade80']];
const level = b => b < 28 ? 0 : b < 36 ? 1 : b < 60 ? 2 : b < 80 ? 3 : 4;
let anSeq = 0, anRate;
async function anRun() {
  const pw = $('#pw').value, seq = ++anSeq;
  $('#pw-count').textContent = `${[...pw].length} character${[...pw].length === 1 ? '' : 's'}`;
  $('#an-empty').hidden = !!pw; $('#an-out').hidden = !pw;
  if (!pw) { $('#an-err').innerHTML = ''; return; }
  const chars = [...pw];
  const flags = { lower: /[a-z]/.test(pw), upper: /[A-Z]/.test(pw), digits: /[0-9]/.test(pw), symbols: /[^A-Za-z0-9]/.test(pw) };
  $('#an-out').classList.add('loading');
  const d = await api('/api/analyze-config', { length: Math.min(chars.length, 1024), ...flags, guessesPerSecond: anRate.get() });
  if (seq !== anSeq) return;
  $('#an-out').classList.remove('loading');
  if (!d.ok) { $('#an-err').innerHTML = errBox(d.errors); $('#an-out').hidden = true; return; }
  $('#an-err').innerHTML = '';
  const { warn, pen } = inspect(pw, d.pool.size), eff = Math.max(0, d.entropyBits - pen), lv = level(eff);
  $('#an-label').textContent = LEVELS[lv][0]; $('#an-label').style.color = LEVELS[lv][1];
  $('#an-basis').textContent = 'heuristic rating based on the pattern-adjusted estimate';
  $('#an-meter').querySelectorAll('i').forEach((el, i) => { el.style.background = i <= lv ? LEVELS[lv][1] : ''; });
  $('#an-meter').setAttribute('aria-label', `Strength: ${LEVELS[lv][0]}`);
  $('#an-h').textContent = bits(d.entropyBits); $('#an-eff').textContent = bits(eff);
  $('#an-chips').innerHTML = [['lower', 'a–z'], ['upper', 'A–Z'], ['digits', '0–9'], ['symbols', 'symbols']].map(([k, t]) => `<span class="chip ${flags[k] ? 'yes' : ''}">${flags[k] ? '✓' : '–'} ${t}</span>`).join('') + `<span class="chip">pool R = ${d.pool.size}</span>`;
  $('#an-metrics').innerHTML = metricsHTML(d);
  if (chars.some(c => c.charCodeAt(0) > 126)) warn.push('Non-ASCII characters were counted as ordinary symbols; the real pool could be larger.');
  const sug = [];
  if (chars.length < 12) sug.push('Make it longer. Each extra random character adds log2(R) bits, which usually matters more than adding a character type.');
  if (!flags.upper || !flags.lower) sug.push('Mix letter cases only if it fits naturally; variety is a small gain compared with length and unpredictability.');
  if (warn.length) sug.push('Remove the patterns listed under Warnings: attackers try these before random guesses.');
  sug.push('Best practice: let a password manager generate a random password or use a long random passphrase of 5 or more words, and use a different one per site.');
  $('#an-warn').innerHTML = warn.length ? warn.map(w => `<li class="warn">${esc(w)}</li>`).join('') : '<li class="ok">No repeated, sequential, keyboard or common-word patterns were detected. That does not prove the password is unpredictable.</li>';
  $('#an-sug').innerHTML = sug.map(s => `<li>${esc(s)}</li>`).join('');
}

/* ============ LAB ============ */
let labForm, labRate, labSeq = 0;
async function labRun() {
  if (!labForm) return;
  const seq = ++labSeq, cfg = labForm.get(), out = $('#lab-out');
  out.classList.add('loading');
  const d = await api('/api/analyze-config', { ...cfg, guessesPerSecond: labRate.get() });
  if (seq !== labSeq) return;
  out.classList.remove('loading');
  if (!d.ok) { out.innerHTML = errBox(d.errors); return; }
  out.innerHTML = `<div class="card"><h2>Results</h2>${metricsHTML(d)}<h2>How it is calculated</h2>${stepsHTML(d)}${constrainedHTML(d.constrained)}
    <p class="small" style="margin-top:14px">Guessing times are theoretical estimates for exhaustive search at a fixed rate, not predictions. Real speed depends on the hashing algorithm, hardware, rate limits, attack method and how predictable the password is.</p></div>`;
  const maxL = Math.min(128, Math.max(24, cfg.length + 6)), base = { ...cfg, required: [], useCustom: false, symbolSet: cfg.symbolSet };
  const cum = [['Lowercase', { lower: true, upper: false, digits: false, symbols: false }], ['+ Uppercase', { lower: true, upper: true, digits: false, symbols: false }], ['+ Digits', { lower: true, upper: true, digits: true, symbols: false }], ['+ Symbols', { lower: true, upper: true, digits: true, symbols: true }]];
  const s = await api('/api/sweep', { maxLength: maxL, configs: [{ ...cfg, label: 'Current' }, ...cum.map(([label, f]) => ({ ...base, ...f, label }))] });
  if (seq !== labSeq || !s.ok) return;
  const [cur, ...rest] = s.series, L = cfg.length;
  draw('ch-space', { type: 'line', data: { labels: cur.lengths, datasets: [{ label: `log10 N, R = ${cur.poolSize}`, data: cur.log10N, borderColor: PAL[0], backgroundColor: PAL[0], pointRadius: cur.lengths.map(x => x === L ? 6 : 0), tension: .1 }] }, options: { scales: { x: axis('Length L'), y: axis('log10(N)') } } });
  draw('ch-ent', { type: 'line', data: { labels: cur.lengths, datasets: rest.map((r, i) => ({ label: `${r.label} (R=${r.poolSize})`, data: r.entropyBits, borderColor: PAL[i + 1 > 4 ? 0 : i + 1], pointRadius: 0, tension: .1 })) }, options: { scales: { x: axis('Length L'), y: axis('Entropy (bits)') } } });
  const at = Math.min(L, maxL) - 1;
  $('#lab-cat-sub').textContent = `Entropy at L = ${Math.min(L, maxL)} for pools built up category by category (symbol set as entered).`;
  draw('ch-cat', { type: 'bar', data: { labels: rest.map(r => `${r.label} (R=${r.poolSize})`), datasets: [{ label: 'Entropy (bits)', data: rest.map(r => r.entropyBits[at]), backgroundColor: PAL.slice(1) }] }, options: { plugins: { legend: { display: false } }, scales: { y: axis('Entropy (bits)') } } });
}

/* ============ COMPARE ============ */
let cmpA, cmpB, cmpRate, cmpSeq = 0;
const PRESETS = [
  ['8 lowercase vs 12 lowercase', { length: 8 }, { length: 12 }],
  ['8 mixed vs 12 mixed', { length: 8, lower: true, upper: true, digits: true, symbols: true }, { length: 12, lower: true, upper: true, digits: true, symbols: true }],
  ['12 lowercase vs 8 mixed', { length: 12 }, { length: 8, lower: true, upper: true, digits: true, symbols: true }],
  ['8 lowercase vs 8 mixed', { length: 8 }, { length: 8, lower: true, upper: true, digits: true, symbols: true }]];
const NONE = { lower: false, upper: false, digits: false, symbols: false };
const reset = p => ({ ...{ lower: true }, ...NONE, lower: true, ...p });
function cmpCol(d) {
  const s = d.searchSpace, g = d.guessing;
  return [['Length', d.length], ['Pool size R', d.pool.size], ['Search space N', s.exact || s.scientific], ['Entropy', bits(d.entropyBits) + ' bits'], ['Average time', g.average.human], ['Worst-case time', g.worst.human]];
}
async function cmpRun() {
  if (!cmpA) return;
  const seq = ++cmpSeq, out = $('#cmp-out');
  out.classList.add('loading');
  const d = await api('/api/compare', { a: cmpA.get(), b: cmpB.get(), guessesPerSecond: cmpRate.get() });
  if (seq !== cmpSeq) return;
  out.classList.remove('loading');
  if (!d.ok) { out.innerHTML = errBox(d.errors); return; }
  const A = cmpCol(d.a), B = cmpCol(d.b), c = d.comparison, cats = r => ['lower', 'upper', 'digits', 'symbols'].filter(k => r.pool[k] > 0).join(', ') || '–';
  const mag = c.orderOfMagnitudeDifference;
  out.innerHTML = `<div class="card"><h2>Side by side</h2><div class="tw"><table><thead><tr><th></th><th>A</th><th>B</th></tr></thead><tbody>
    ${A.map((r, i) => `<tr><td>${r[0]}</td><td class="mono">${esc(r[1])}</td><td class="mono">${esc(B[i][1])}</td></tr>`).join('')}
    <tr><td>Character categories</td><td>${esc(cats(d.a))}</td><td>${esc(cats(d.b))}</td></tr></tbody></table></div></div>
  <div class="card"><h2>What changed the search space?</h2>
    <p>B has ${bits(Math.abs(c.deltaBits))} bits ${c.deltaBits >= 0 ? 'more' : 'less'} theoretical entropy than A, which is a factor of about 10<sup>${Math.abs(mag).toFixed(1)}</sup> ${mag >= 0 ? 'larger' : 'smaller'} search space.</p>
    <div class="formula">ΔH = (L_B − L_A)·log2 R_A + L_B·(log2 R_B − log2 R_A)</div>
    <p>Length term: <b class="mono">${bits(c.fromLengthBits)} bits</b>. Pool term: <b class="mono">${bits(c.fromPoolBits)} bits</b>. ${esc(c.verdict)}</p>
    <p class="small">Both configurations assume uniformly random generation. The comparison says nothing about human-chosen passwords.</p></div>
  <div class="card"><h2>Entropy comparison</h2><div class="chart short"><canvas id="ch-cmp" role="img" aria-label="Bar chart comparing entropy of A and B"></canvas></div></div>`;
  draw('ch-cmp', { type: 'bar', data: { labels: ['Entropy (bits)', 'log10 search space'], datasets: [{ label: 'A', data: [d.a.entropyBits, d.a.searchSpace.log10], backgroundColor: PAL[0] }, { label: 'B', data: [d.b.entropyBits, d.b.searchSpace.log10], backgroundColor: PAL[1] }] }, options: { scales: { y: axis('value') } } });
}

/* ============ LEARN ============ */
function learnWidget(root, required) {
  root.innerHTML = '<div class="widget"><div class="lw-form"></div><div class="lw-out" style="margin-top:14px"></div></div>';
  const f = configForm($('.lw-form', root), { length: 8, required });
  let seq = 0;
  const run = async () => {
    const s = ++seq, d = await api('/api/analyze-config', { ...f.get(), guessesPerSecond: 1e10 });
    if (s !== seq) return;
    $('.lw-out', root).innerHTML = d.ok ? `<ul class="steps">${d.steps.slice(0, 3).map(x => `<li>${esc(x)}</li>`).join('')}</ul>${constrainedHTML(d.constrained)}` : errBox(d.errors);
  };
  f.on(debounce(run)); run();
}
const TOPICS = [
  ['1. Fundamental Principle of Counting', `<p>If a task has L independent stages and stage i can be done in n<sub>i</sub> ways, the whole task can be done in n<sub>1</sub>·n<sub>2</sub>···n<sub>L</sub> ways. A password position can hold any of R characters regardless of the others, so there are R·R···R = R<sup>L</sup> strings. Change the length or the sets below and watch R and N update (calculated by the Python engine).</p><div class="formula">N = R<sup>L</sup></div>`, r => learnWidget(r, false)],
  ['2. Sets and Set Operations', `<p>Lowercase (26), uppercase (26), digits (10) and a symbol set are sets. The pool is their <b>union</b>, and a union counts each element once: |A ∪ B| = |A| + |B| − |A ∩ B|. Standard sets are disjoint, so R = 26 + 26 + 10 + S. Try typing <code>a</code> into the symbol set with symbols and lowercase both on: the engine reports the duplicate it removed.</p><div class="formula">R = |Lower ∪ Upper ∪ Digits ∪ Symbols|</div>`, r => learnWidget(r, false)],
  ['3. Logarithms and Entropy', `<p>Entropy answers "how many yes/no questions pick out one password among N equally likely ones?" That number is log<sub>2</sub> N, measured in bits. Because log<sub>2</sub>(R<sup>L</sup>) = L·log<sub>2</sub> R, the engine multiplies instead of computing the huge number first, so it never overflows. Each extra character adds exactly log<sub>2</sub> R bits.</p><div class="formula">H = log2(N) = L × log2(R)</div><p class="small">Example: R = 26, L = 8 gives N = 208,827,064,576 and H ≈ 37.60 bits. This is the entropy of a <i>uniform random</i> generator, not of a human-chosen password.</p>`, r => learnWidget(r, false)],
  ['4. Permutations and Combinatorial Counting', `<p>Passwords allow repetition, so we count <i>strings</i> (arrangements with repetition) rather than permutations without repetition. A policy such as "at least one digit" removes the strings with no digit: all strings minus the strings made only from the other R − A characters. This is the <b>complement</b> counting method.</p><div class="formula">N_valid = R<sup>L</sup> − (R − A)<sup>L</sup></div><p class="small">Assumption: every character is equally likely and the A "required" characters are all in the pool. Tick one requirement below to see the two terms.</p>`, r => { learnWidget(r, true); }],
  ['5. Inclusion-Exclusion Principle', `<p>With several requirements, subtracting each failure separately double-counts strings that fail more than one. Inclusion-exclusion fixes this by adding back overlaps. For two requirements P and Q: |P ∩ Q| = N − |¬P| − |¬Q| + |¬P ∧ ¬Q|. The engine applies this over every subset of the chosen requirements; the table below lists each term. If a set of characters belongs to two requirements, its union is counted once.</p><div class="formula">N_valid = Σ over S ⊆ requirements of (−1)<sup>|S|</sup> (R − |∪S|)<sup>L</sup></div><p class="small">Test: tick two or more requirements. The engine's results are verified against brute-force enumeration in the unit tests.</p>`, r => { learnWidget(r, true); }],
  ['6. Mathematical Logic and Predicates', `<p>A password policy is a compound proposition. With predicates len(p) ≥ 8, hasUpper(p), hasDigit(p), hasSymbol(p), a policy might be <code>len ≥ 8 ∧ hasUpper ∧ (hasDigit ∨ hasSymbol)</code>. The set of passwords that satisfy it is its truth set, and counting that set is the combinatorics problem above. Type a test string to evaluate each predicate.</p>
   <div class="widget"><label for="lg">Test string</label><input id="lg" autocomplete="off" spellcheck="false" value="Hello2026"><div id="lg-out" style="margin-top:12px"></div></div>`, r => {
      const run = () => { const p = $('#lg', r).value, t = [[`len ≥ 8`, p.length >= 8], ['hasUpper', /[A-Z]/.test(p)], ['hasDigit', /\d/.test(p)], ['hasSymbol', /[^A-Za-z0-9]/.test(p)]], v = Object.fromEntries(t.map(([k, b]) => [k, b]));
        const pol = v['len ≥ 8'] && v.hasUpper && (v.hasDigit || v.hasSymbol);
        $('#lg-out', r).innerHTML = t.map(([k, b]) => `<span class="pill ${b ? 't' : 'f'}">${esc(k)} = ${b ? 'T' : 'F'}</span>`).join('') + `<p>Policy <code>len ≥ 8 ∧ hasUpper ∧ (hasDigit ∨ hasSymbol)</code> evaluates to <b class="${pol ? 'pos' : 'neg'}">${pol ? 'True' : 'False'}</b>.</p>`; };
      $('#lg', r).oninput = run; run(); }]
];
function buildLearn() {
  $('#learn-body').innerHTML = TOPICS.map(([t, html], i) => `<details class="topic" ${i === 0 ? 'open' : ''}><summary>${esc(t)}</summary><div class="topic-body">${html}<div class="live"></div></div></details>`).join('');
  document.querySelectorAll('#learn-body details').forEach((d, i) => { const inLogic = i === 5; TOPICS[i][2](inLogic ? $('.topic-body', d) : $('.live', d)); });
}

/* ---------- Init ---------- */
function init() {
  anRate = rateControl($('#an-rate'), debounce(anRun, 100));
  const pw = $('#pw'), tg = $('#pw-toggle');
  pw.addEventListener('input', debounce(anRun, 120));
  tg.onclick = () => { const show = pw.type === 'password'; pw.type = show ? 'text' : 'password'; tg.textContent = show ? 'Hide' : 'Show'; tg.setAttribute('aria-pressed', show); };
  $('#pw-copy').onclick = async () => {
    const m = $('#pw-copied');
    if (!pw.value) { m.textContent = 'Nothing to copy.'; return; }
    try { await navigator.clipboard.writeText(pw.value); m.textContent = 'Copied. Clear your clipboard when you are done.'; } catch { m.textContent = 'Copy was blocked by the browser.'; }
    setTimeout(() => { m.textContent = ''; }, 3500);
  };
  labForm = configForm($('#lab-form'), { length: 12, required: true });
  labRate = rateControl($('#lab-rate'), debounce(labRun, 150));
  labForm.on(debounce(labRun, 200));
  cmpA = configForm($('#cmp-a'), { length: 8 }); cmpB = configForm($('#cmp-b'), { length: 12 });
  cmpRate = rateControl($('#cmp-rate'), debounce(cmpRun, 150));
  cmpA.on(debounce(cmpRun, 200)); cmpB.on(debounce(cmpRun, 200));
  $('#cmp-presets').innerHTML = PRESETS.map(([t], i) => `<button class="btn" type="button" data-i="${i}">${esc(t)}</button>`).join('');
  $('#cmp-presets').onclick = e => { const b = e.target.closest('button'); if (!b) return; const [, a, c] = PRESETS[b.dataset.i]; cmpA.set(reset(a)); cmpB.set(reset(c)); cmpRun(); };
  buildLearn(); route(); anRun();
}
init();
