(() => {
  'use strict';
  const key = 'pm-engine.theme';
  const root = document.documentElement;
  const media = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  let preference = 'system';
  const valid = value => value === 'light' || value === 'dark';
  try { const stored = window.localStorage.getItem(key); if (valid(stored)) preference = stored; } catch { /* Device policy can disable storage. */ }
  function apply() {
    const theme = preference === 'system' ? (media?.matches ? 'dark' : 'light') : preference;
    root.dataset.theme = theme;
    root.dataset.themePreference = preference;
    for (const select of document.querySelectorAll('[data-theme-select]')) select.value = preference;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#14212b' : '#e7ecef');
  }
  function bind() {
    for (const select of document.querySelectorAll('[data-theme-select]')) {
      select.addEventListener('change', () => {
        preference = valid(select.value) ? select.value : 'system';
        try {
          if (preference === 'system') window.localStorage.removeItem(key);
          else window.localStorage.setItem(key, preference);
        } catch { /* Use the preference for this page even if persistence is unavailable. */ }
        apply();
      });
    }
    apply();
  }
  apply();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, { once: true });
  else bind();
  if (media?.addEventListener) media.addEventListener('change', () => { if (preference === 'system') apply(); });
  else if (media?.addListener) media.addListener(() => { if (preference === 'system') apply(); });
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : 'system';
    apply();
  });
})();
