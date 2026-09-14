(() => {
  const root = document.querySelector('[data-spatial-explorer]');
  if (!root) return;
  function fallback() {
    if (root.dataset.sceneState === 'ready') return;
    root.dataset.sceneState = 'unavailable';
    root.querySelector('[data-scene-loading]').hidden = true;
    root.querySelector('[data-scene-fallback]').hidden = false;
    root.querySelector('[data-scene-error]').hidden = false;
    root.querySelectorAll('[data-view], [data-scene-action]').forEach(button => { button.disabled = true; });
  }
  const timer = setTimeout(fallback, 20000);
  const source = new URL('property-scene.js', document.currentScript.src).href;
  import(source).then(() => clearTimeout(timer)).catch(() => { clearTimeout(timer); fallback(); });
})();
