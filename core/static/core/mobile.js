(() => {
  const viewport = window.visualViewport;
  let frame = 0;
  function update() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const height = viewport?.height || innerHeight;
      const top = viewport?.offsetTop || 0;
      const inset = Math.max(0, innerHeight - height - top);
      document.documentElement.style.setProperty('--visual-height', `${height}px`);
      document.documentElement.style.setProperty('--visual-top', `${top}px`);
      document.documentElement.style.setProperty('--keyboard-inset', `${inset}px`);
      const focused = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '');
      document.body.classList.toggle('keyboard-open', focused && innerHeight - height > 140);
    });
  }
  viewport?.addEventListener('resize', update);
  viewport?.addEventListener('scroll', update);
  window.addEventListener('resize', update);
  document.addEventListener('focusin', update);
  document.addEventListener('focusout', () => setTimeout(update, 100));
  update();
})();
