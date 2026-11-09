/* Boot: load configuration, restore session, start router. */
'use strict';
P.refreshCounters = async () => {
  if (!P.state.me) return;
  try {
    const n = await P.api('/notifications'); P.state.unread = n.unread;
    if (P.can('submissions.verify')) P.state.pending = (await P.api('/submissions?status=SUBMITTED')).length;
    if (P.can('accounts.review')) P.state.apps = (await P.api('/kpt/applications?status=PENDING_APPROVAL')).length;
  } catch (e) { /* counters are best-effort */ }
};
(async () => {
  try { P.state.config = await P.api('/public/config'); }
  catch (e) { P.$('#app').innerHTML = `<div class="pub-main"><div class="callout danger">${P.esc(e.message)}</div></div>`; return; }
  P.state.year = P.state.config.default_year || 2026;
  try { P.state.me = await P.api('/me', { quiet401: true }); await P.refreshCounters(); } catch (e) { P.state.me = null; }
  window.addEventListener('hashchange', P.render);
  setInterval(async () => { if (P.state.me) { const before = P.state.unread; await P.refreshCounters(); if (P.state.unread !== before) { const b = P.$('.bell'); if (b) b.innerHTML = '🔔' + (P.state.unread ? `<span class="dot">${P.state.unread}</span>` : ''); } } }, 60000);
  P.render();
})();
