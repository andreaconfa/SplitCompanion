/* Blocking, self-hosted bootstrap: theme is applied before CSS/React paint. */
(function () {
  var preference = null;
  try { preference = localStorage.getItem('split-companion-theme'); } catch (_) {}
  var theme = preference === 'dark' || preference === 'light'
    ? preference
    : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  var accent = null;
  try { accent = localStorage.getItem('split-companion-accent'); } catch (_) {}
  document.documentElement.dataset.accent = ['indigo', 'ocean', 'forest', 'rose', 'amber'].indexOf(accent) >= 0 ? accent : 'indigo';
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#000000' : '#f2f2f7';
})();
