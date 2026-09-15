(() => {
  const root = document.querySelector('[data-ai-root]');
  if (!root) return;
  const form = root.querySelector('[data-ai-form]');
  const input = form.querySelector('textarea');
  const submit = form.querySelector('[type=submit]');
  const thread = root.querySelector('[data-ai-thread]');
  const conversation = root.querySelector('[data-ai-conversation]');
  const key = `enginex-ai-v1-${document.body.dataset.userId}`;
  let turns = [];
  let busy = false;
  let currentController;

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function safeLink(url) { return typeof url === 'string' && /^\/(?:contracts|records|reports|feedback)\//.test(url) && !url.includes('\\') ? url : null; }
  function save() {
    try { sessionStorage.setItem(key, JSON.stringify(turns.slice(-12))); } catch (_) { /* The conversation still works when browser storage is disabled. */ }
  }
  function open() {
    if (conversation) conversation.hidden = false;
    root.classList.add('is-open');
    thread.scrollTop = thread.scrollHeight;
  }
  function resizeInput() {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 125)}px`;
  }
  function format(value, unit = '') {
    if (value === null || value === undefined) return 'Not stated';
    const n = Number(value);
    if (!Number.isFinite(n)) return 'Not stated';
    return `${unit === 'AED' ? 'AED ' : ''}${n.toLocaleString('en-US', { maximumFractionDigits: unit === '%' ? 2 : unit === 'NPS points' ? 1 : 0 })}${unit === '%' ? '%' : ''}`;
  }
  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement('a'); link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function svgNode(tag, attrs = {}, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([name, value]) => node.setAttribute(name, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  const palette = ['#285d50', '#a58c50', '#8ab39a', '#486a79', '#c1b784', '#708f75', '#b78f69', '#879cad'];
  const chartSource = chart => chart.display_source || 'Portfolio records; document evidence and summary metrics are separate.';
  function drawChart(chart, host) {
    const rows = chart.rows.filter(row => typeof row.label === 'string' && (row.value === null || Number.isFinite(Number(row.value))));
    const width = Math.max(285, Math.min(800, host.clientWidth || 550));
    const font = { 'font-family': 'Arial, sans-serif', 'font-size': 11, fill: '#64806b' };
    let height = chart.type === 'bar' ? Math.max(150, rows.length * 49 + 40) : chart.type === 'doughnut' ? 240 + rows.length * 43 : 300;
    const svg = svgNode('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': `${chart.title}. ${chartSource(chart)}` });
    svg.append(svgNode('title', {}, chart.title), svgNode('rect', { width, height, fill: '#ffffff' }));
    if (!rows.length) { svg.append(svgNode('text', { ...font, x: 18, y: 55 }, 'No matching records to plot.')); host.replaceChildren(svg); return svg; }
    const valid = rows.filter(row => row.value !== null);
    const min = Math.min(0, ...valid.map(row => Number(row.value)));
    const max = Math.max(1, ...valid.map(row => Number(row.value)));
    if (chart.type === 'bar') {
      const left = Math.min(150, width * 0.34), right = width - 20, plotWidth = right - left;
      const x = value => left + (value - min) / (max - min) * plotWidth;
      rows.forEach((row, i) => {
        const y = i * 49 + 16;
        const words = row.label.match(/.{1,19}(?:\s|$)|.{1,19}/g) || [row.label];
        words.slice(0, 2).forEach((part, line) => svg.append(svgNode('text', { ...font, x: 0, y: y + 15 + line * 12 }, part.trim())));
        svg.append(svgNode('rect', { x: left, y, width: plotWidth, height: 23, rx: 4, fill: '#f0f4eb' }));
        if (row.value !== null) {
          const rect = svgNode('rect', { x: Math.min(x(0), x(row.value)), y, width: Math.max(1, Math.abs(x(row.value) - x(0))), height: 23, rx: 4, fill: palette[i % palette.length] });
          rect.append(svgNode('title', {}, `${row.label}: ${format(row.value, chart.unit)}`)); svg.append(rect);
        }
        svg.append(svgNode('text', { ...font, x: left, y: y + 37, 'font-size': 10, fill: '#385d42' }, format(row.value, chart.unit)));
      });
    } else if (chart.type === 'doughnut') {
      const sum = valid.reduce((total, row) => total + Math.max(0, Number(row.value)), 0);
      const cx = width / 2, cy = 108, radius = 78, circumference = 2 * Math.PI * radius;
      let offset = 0;
      svg.append(svgNode('circle', { cx, cy, r: radius, fill: 'none', stroke: '#edf2e7', 'stroke-width': 29 }));
      valid.forEach((row, i) => {
        const length = sum ? Math.max(0, Number(row.value)) / sum * circumference : 0;
        const arc = svgNode('circle', { cx, cy, r: radius, fill: 'none', stroke: palette[i % palette.length], 'stroke-width': 29, 'stroke-dasharray': `${length} ${circumference - length}`, 'stroke-dashoffset': -offset, transform: `rotate(-90 ${cx} ${cy})` });
        arc.append(svgNode('title', {}, `${row.label}: ${format(row.value, chart.unit)}`)); svg.append(arc); offset += length;
      });
      svg.append(svgNode('text', { ...font, x: cx, y: cy + 1, 'text-anchor': 'middle', 'font-size': 24, fill: '#294e3b' }, format(sum)), svgNode('text', { ...font, x: cx, y: cy + 23, 'text-anchor': 'middle', 'font-size': 10 }, chart.unit));
      rows.forEach((row, i) => { const y = 237 + i * 43; const chars = Math.floor((width - 30) / 6); svg.append(svgNode('rect', { x: 6, y: y - 9, width: 8, height: 8, rx: 2, fill: palette[i % palette.length] }), svgNode('text', { ...font, x: 23, y }, row.label.length > chars ? row.label.slice(0, chars - 1) + '…' : row.label), svgNode('text', { ...font, x: 23, y: y + 16, fill: '#365a43' }, format(row.value, chart.unit))); });
    } else {
      const left = 50, right = width - 14, top = 30, bottom = 246;
      const x = i => left + i / Math.max(1, rows.length - 1) * (right - left);
      const y = value => bottom - (value - min) / (max - min) * (bottom - top);
      for (let i = 0; i < 5; i++) {
        const value = min + (max - min) * i / 4;
        svg.append(svgNode('line', { x1: left, x2: right, y1: y(value), y2: y(value), stroke: '#e5edde' }), svgNode('text', { ...font, x: left - 8, y: y(value) + 4, 'text-anchor': 'end', 'font-size': 9 }, Math.abs(value) >= 1000000 ? `${(value / 1000000).toFixed(1)}M` : Math.abs(value) >= 1000 ? `${(value / 1000).toFixed(0)}k` : value.toFixed(chart.unit === '%' ? 1 : 0)));
      }
      let path = '', connected = false;
      rows.forEach((row, i) => {
        if (row.value === null) { connected = false; return; }
        path += `${connected ? 'L' : 'M'}${x(i)},${y(row.value)} `; connected = true;
      });
      svg.append(svgNode('path', { d: path, fill: 'none', stroke: '#497e60', 'stroke-width': 2.5 }));
      rows.forEach((row, i) => {
        if (row.value !== null) { const dot = svgNode('circle', { cx: x(i), cy: y(row.value), r: 4, fill: '#ae995b', stroke: '#fff', 'stroke-width': 1.5 }); dot.append(svgNode('title', {}, `${row.label}: ${format(row.value, chart.unit)}`)); svg.append(dot); }
        if (i % Math.max(1, Math.ceil(rows.length / Math.max(3, Math.floor(width / 80)))) === 0) svg.append(svgNode('text', { ...font, x: x(i), y: bottom + 23, 'text-anchor': 'middle', 'font-size': 9 }, row.label.slice(0, 12)));
      });
      svg.append(svgNode('text', { ...font, x: left, y: 14, 'font-size': 10 }, chart.unit));
    }
    host.replaceChildren(svg);
    return svg;
  }
  function addChart(chart, parent) {
    if (!['bar', 'line', 'doughnut'].includes(chart.type) || !Array.isArray(chart.rows)) return;
    const card = element('section', 'ai-chart');
    const header = element('div', 'ai-chart-header'); header.append(element('h3', '', chart.title), element('span', '', chart.record_label ? 'RESIDENT FEEDBACK' : 'PORTFOLIO DATA'));
    const plot = element('div', 'ai-chart-plot');
    const scope = `${chart.matched_records} matching ${chart.record_label || 'records'} · ${chart.location || 'all'} · ${chart.metric === 'nps' ? 'NPS' : chart.metric + ' ' + (chart.metric === 'count' ? (chart.record_label || 'records') : (chart.metric_field || '').replaceAll('_', ' '))}${chart.as_of ? ' · ' + chart.as_of : ''}`;
    const note = element('p', 'ai-chart-note', `${scope}. ${chartSource(chart)}${chart.total_groups > chart.rows.length ? ` Showing ${chart.rows.length} of ${chart.total_groups} groups.` : ''}`);
    const actions = element('div', 'ai-chart-actions');
    const tableWrap = element('div', 'ai-chart-data'); tableWrap.hidden = true;
    const table = element('table'); const tr = element('tr'); ['Group', chart.unit, chart.record_label || 'Records'].forEach(value => tr.append(element('th', '', value))); table.append(tr);
    chart.rows.forEach(row => { const tr = element('tr'); [row.label, format(row.value, chart.unit), row.records].forEach(value => tr.append(element('td', '', value))); table.append(tr); }); tableWrap.append(table);
    const show = element('button', '', 'View values'); show.type = 'button'; show.setAttribute('aria-expanded', 'false'); show.addEventListener('click', () => { tableWrap.hidden = !tableWrap.hidden; show.setAttribute('aria-expanded', String(!tableWrap.hidden)); });
    const exportCSV = element('button', '', 'Download CSV ↓'); exportCSV.type = 'button';
    exportCSV.addEventListener('click', () => {
      const cell = value => { let s = String(value ?? ''); if (/^[=+@\-\t\r]/.test(s)) s = "'" + s; return '"' + s.replaceAll('"', '""') + '"'; };
      const rows = [['group', 'value', 'unit', 'records', 'provenance', 'as_of', 'location', 'filters'], ...chart.rows.map(row => [row.label, row.value, chart.unit, row.records, chart.provenance, chart.as_of || '', chart.location || 'all', JSON.stringify(chart.filters || [])])];
      download('enginex-analysis.csv', rows.map(row => row.map(cell).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
    });
    const exportSVG = element('button', '', 'Download chart ↓'); exportSVG.type = 'button'; exportSVG.addEventListener('click', () => {
      const source = plot.querySelector('svg').cloneNode(true);
      source.querySelector('title').textContent += ` — ${scope}. ${chartSource(chart)}`;
      const { width, height } = source.viewBox.baseVal;
      source.setAttribute('viewBox', `0 0 ${width} ${height + 30}`);
      source.append(svgNode('rect', { x: 0, y: height, width, height: 30, fill: '#fff' }), svgNode('text', { x: 8, y: height + 17, 'font-family': 'Arial, sans-serif', 'font-size': 9, fill: '#597563' }, `Portfolio · ${chart.matched_records} records · ${chart.as_of || 'Date not stated'}`));
      download('enginex-analysis.svg', new XMLSerializer().serializeToString(source), 'image/svg+xml;charset=utf-8');
    });
    actions.append(show, exportCSV, exportSVG); card.append(header, plot, note, actions, tableWrap); parent.append(card);
    drawChart(chart, plot);
    let lastWidth = plot.clientWidth, resizeFrame;
    const observer = new ResizeObserver(() => {
      if (plot.clientWidth <= 0 || plot.clientWidth === lastWidth) return;
      lastWidth = plot.clientWidth;
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => drawChart(chart, plot));
    });
    observer.observe(plot);
    card._resizeObserver = { disconnect() { observer.disconnect(); cancelAnimationFrame(resizeFrame); } };
  }
  function renderResponse(turn, answerNode, response) {
    answerNode.classList.remove('is-pending');
    answerNode.textContent = response.answer;
    (response.charts || []).forEach(chart => addChart(chart, turn));
    const coverage = response.coverage;
    if (coverage) {
      const note = element('p', 'ai-query-note'); note.append(element('i'), document.createTextNode(`Entire portfolio · ${coverage.records} records · ${coverage.contracts} contracts${coverage.feedback_transcripts !== undefined ? ' · ' + coverage.feedback_transcripts + ' resident transcripts' : ''} · ${(response.queries || []).length} data queries${response.retrieved_at ? ' · ' + new Date(response.retrieved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}`)); turn.append(note);
    }
    const sources = (response.sources || []).filter(source => safeLink(source.url));
    if (sources.length || response.queries?.length) {
      const details = element('details', 'ai-source-details'); details.append(element('summary', '', `Data & sources${sources.length ? ` · ${sources.length} links` : ''}`));
      (response.queries || []).forEach(query => details.append(element('p', '', `${query.tool.replaceAll('_', ' ')} · ${query.location} · ${query.matched ?? '—'} matches · ${query.returned} returned${query.has_more ? ' · More results available' : ''}`)));
      const list = element('div', 'ai-source-list'); sources.forEach(source => { const a = element('a', '', (source.display_label || source.label) + (source.page ? ` · p. ${source.page} ↗` : ' ↗')); a.href = source.url; a.target = '_blank'; a.rel = 'noopener'; if (source.review || source.origin) a.append(element('small', '', source.review || source.display_origin || (source.origin === 'synthetic' ? 'Portfolio record' : source.origin))); list.append(a); }); details.append(list); turn.append(details);
    }
  }
  function renderTurn(item, pending = false) {
    root.querySelector('[data-ai-welcome]')?.remove(); thread.querySelector('.ai-empty-message')?.remove();
    const turn = element('article', 'ai-turn'); turn.append(element('div', 'ai-user-message', item.question));
    const header = element('div', 'ai-answer-header'); header.append(element('span', '', '✦'), document.createTextNode('EnginexAI')); turn.append(header);
    const answerNode = element('div', 'ai-answer-text' + (pending ? ' is-pending' : ''), pending ? 'Reading your question and checking the portfolio…' : item.error || ''); turn.append(answerNode); thread.append(turn);
    if (item.response) renderResponse(turn, answerNode, item.response);
    if (item.error) answerNode.classList.add('is-error');
    return { turn, answerNode };
  }
  function clear() {
    if (busy) return;
    thread.querySelectorAll('.ai-chart').forEach(card => card._resizeObserver?.disconnect());
    turns = []; save(); thread.replaceChildren(element('div', 'ai-empty-message', 'A fresh conversation. Ask about the portfolio, request a chart, or explore a contract.')); input.value = ''; resizeInput(); input.focus();
  }
  root.querySelectorAll('[data-ai-new]').forEach(button => button.addEventListener('click', clear));
  root.querySelector('[data-ai-close]')?.addEventListener('click', () => { conversation.hidden = true; root.classList.remove('is-open'); input.blur(); });
  document.querySelectorAll('[data-chat-open]').forEach(button => button.addEventListener('click', () => { open(); input.focus(); }));
  document.querySelectorAll('[data-ai-prompt]').forEach(button => button.addEventListener('click', () => { if (busy) return; input.value = button.dataset.aiPrompt; resizeInput(); open(); input.focus(); form.requestSubmit(); }));
  input.addEventListener('focus', open);
  input.addEventListener('input', resizeInput);
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); form.requestSubmit(); } });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && conversation && !conversation.hidden) { conversation.hidden = true; root.classList.remove('is-open'); input.blur(); } });
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || '[]');
    if (Array.isArray(saved)) turns = saved.filter(item => item && typeof item.question === 'string' && item.question.length <= 4000 && (item.response?.answer || item.error)).slice(-12);
    turns.forEach(item => renderTurn(item));
  } catch (_) { turns = []; }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const question = input.value.trim(); if (!question || busy) return;
    const history = turns.filter(item => item.response).slice(-4).flatMap(item => [{ role: 'user', content: item.question }, { role: 'assistant', content: item.response.answer.slice(0, 6000) }]);
    busy = true; submit.disabled = true; root.querySelectorAll('[data-ai-new]').forEach(button => { button.disabled = true; }); open();
    const item = { question }; const { turn, answerNode } = renderTurn(item, true); turns.push(item); input.value = ''; resizeInput(); thread.scrollTop = thread.scrollHeight;
    currentController = new AbortController(); const timer = setTimeout(() => currentController.abort(), 190000);
    try {
      const body = { message: question, history }; if (root.dataset.currentLocation) body.current_location = root.dataset.currentLocation;
      const response = await fetch(form.action, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name=ai-csrf-token]').content }, body: JSON.stringify(body), signal: currentController.signal });
      if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw Error('Your session may have expired. Sign in again and retry.');
      const payload = await response.json(); if (!response.ok) throw Error(payload.error || 'The analysis could not be completed. Please retry.');
      if (typeof payload.answer !== 'string') throw Error('The assistant returned an incomplete response. Please retry.');
      item.response = payload; renderResponse(turn, answerNode, payload);
    } catch (error) {
      item.error = error.name === 'AbortError' ? 'This analysis took too long. Try a more focused question.' : error.message || 'The assistant could not be reached. Please retry.';
      answerNode.textContent = item.error; answerNode.classList.remove('is-pending'); answerNode.classList.add('is-error');
      if (!input.value.trim()) input.value = question;
      resizeInput();
    } finally {
      clearTimeout(timer); currentController = null; busy = false; submit.disabled = false; root.querySelectorAll('[data-ai-new]').forEach(button => { button.disabled = false; }); save();
      // Keep the answer's beginning visible even when a chart makes it tall.
      thread.scrollTo({ top: Math.max(0, turn.offsetTop - thread.offsetTop - 16), behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth' });
    }
  });
  window.addEventListener('pagehide', event => { currentController?.abort(); if (!event.persisted) thread.querySelectorAll('.ai-chart').forEach(card => card._resizeObserver?.disconnect()); });
})();
