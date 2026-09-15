document.querySelectorAll('[data-pdf-page]').forEach(button => button.addEventListener('click', () => {
  const viewer = document.querySelector('[data-pdf-viewer]');
  viewer.src = viewer.dataset.pageTemplate.replace('/0/', '/' + button.dataset.pdfPage + '/');
  viewer.alt = 'Source PDF, page ' + button.dataset.pdfPage;
  document.querySelector('[data-page-label]').textContent = 'Page ' + button.dataset.pdfPage;
  viewer.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
}));
const search = document.querySelector('[data-record-search]');
search?.addEventListener('input', () => {
  const term = search.value.trim().toLowerCase();
  document.querySelectorAll('[data-record-select] option').forEach(option => {
    option.hidden = !option.selected && !option.textContent.toLowerCase().includes(term);
  });
});
const progress = document.querySelector('[data-extraction-status]');
if (progress) {
  const timer = window.setInterval(async () => {
    try {
      const response = await fetch(progress.dataset.extractionStatus);
      if (!response.ok) return;
      const result = await response.json();
      progress.querySelector('strong').textContent = result.label;
      if (!['queued','running'].includes(result.status)) {
        clearInterval(timer);
        const link = document.createElement('a');
        link.href = window.location.pathname;
        link.className = 'text-link';
        link.textContent = result.status === 'completed' ? ' View extracted fields →' : ' View extraction result →';
        progress.replaceChildren(document.createTextNode(result.label + '. ' + (result.association_label || '') + '. '), link);
      }
    } catch (_) { /* The visible PDF and forms remain usable while disconnected. */ }
  }, 4000);
}
