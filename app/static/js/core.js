/* PSKG Monitor 2030 — core utilities (API client, router, layout, UI helpers).
   No inline event handlers are used (Content-Security-Policy: script-src 'self');
   interaction is wired through data-act / data-form / data-on delegation. */
'use strict';
const P = window.P = {
  state: { me: null, config: null, kpis: null, year: 2026, charts: [], unread: 0 },
  routes: [], actions: {}, forms: {}, inputs: {}, pages: {},
};

/* ------------------------------------------------------------------ basics */
P.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
P.$ = (sel, root = document) => root.querySelector(sel);
P.$$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
P.fmt = (n, d = 2) => (n === null || n === undefined || n === '' || Number.isNaN(+n)) ? '—'
  : new Intl.NumberFormat('ms-MY', { maximumFractionDigits: d }).format(+n);
P.val = (v, unit) => {
  if (v === null || v === undefined) return '—';
  if (unit === 'percent' || unit === 'index%') return P.fmt(v, 2) + '%';
  if (unit === 'index') return P.fmt(v, 2);
  return P.fmt(v, 0);
};
P.targetText = (t, unit) => {
  if (!t || t.value === null || t.value === undefined) return '—';
  if (t.kind === 'milestone') return P.esc(t.label || (P.fmt(t.value) + '% milestone'));
  if (unit === 'count') return P.fmt(t.value, 0);
  return P.fmt(t.value, 2) + '%';
};
P.date = iso => iso ? new Date(iso).toLocaleString('ms-MY', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
P.dateOnly = iso => iso ? new Date(iso).toLocaleDateString('ms-MY', { dateStyle: 'medium' }) : '—';
P.STATUS = {
  NOT_STARTED: 'Belum diisi', DRAFT: 'Draf', SUBMITTED: 'Menunggu semakan', RETURNED: 'Perlu pembetulan',
  VERIFIED: 'Disahkan', NOT_APPLICABLE: 'Tidak berkenaan', PENDING_APPROVAL: 'Menunggu Kelulusan', APPROVED: 'Diluluskan',
  REJECTED: 'Ditolak', REOPENED: 'Dibuka semula', pending: 'Menunggu kelulusan', invited: 'Menunggu pengaktifan', active: 'Aktif',
  inactive: 'Dinyahaktifkan', rejected: 'Ditolak', ACTIVE: 'Aktif', INACTIVE: 'Tidak aktif', PENDING: 'Menunggu',
  OPEN: 'Dibuka', CLOSED: 'Ditutup', PLANNED: 'Dirancang'
};
P.badge = (status, label) => `<span class="badge-s st-${P.esc(status)}">${P.esc(label || P.STATUS[status] || status)}</span>`;
P.UNIT = { percent: 'Peratus', count: 'Bilangan', index: 'Indeks khas' };
P.CATS = () => (P.state.config && P.state.config.categories) || {};
P.yearOptions = (sel) => (P.state.config?.years || [2026, 2027, 2028, 2029, 2030]).map(y => `<option value="${y}" ${+sel === y ? 'selected' : ''}>${y}</option>`).join('');
P.terasNames = { 1: 'Bakat Global dan Progresif', 2: 'Pendidikan Berteraskan Kemahiran', 3: 'Pencipta Inovatif', 4: 'Sinergi Industri-Akademia', 5: 'Tanggungjawab dan Pembinaan Negara' };
P.can = perm => !!(P.state.me && P.state.me.permissions.includes(perm));

/* ------------------------------------------------------------------ API */
P.api = async (path, opts = {}) => {
  const init = { method: opts.method || 'GET', credentials: 'same-origin', headers: { 'X-Requested-With': 'PSKG' } };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers['Content-Type'] = 'application/json'; }
  let r;
  try { r = await fetch('/api' + path, init); }
  catch (e) { throw new Error('Tidak dapat menghubungi pelayan. Pastikan pelayan sedang berjalan.'); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map(d => (d.loc ? d.loc.slice(-1)[0] + ': ' : '') + (d.msg || '')).join('; ');
    const err = new Error(typeof msg === 'string' ? msg : 'Ralat ' + r.status);
    err.status = r.status;
    if (r.status === 401 && !opts.quiet401 && P.state.me) { P.state.me = null; P.toast('Sesi telah tamat. Sila log masuk semula.', 'warning'); P.go('/login'); }
    throw err;
  }
  return data;
};

/* ------------------------------------------------------------------ UI feedback */
P.toast = (msg, type = 'success') => {
  const id = 't' + Math.random().toString(36).slice(2);
  const cls = { success: 'text-bg-success', danger: 'text-bg-danger', warning: 'text-bg-warning', info: 'text-bg-primary' }[type] || 'text-bg-secondary';
  P.$('#toasts').insertAdjacentHTML('beforeend', `<div id="${id}" class="toast align-items-center ${cls} border-0" role="alert" aria-live="assertive"><div class="d-flex"><div class="toast-body">${P.esc(msg)}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Tutup"></button></div></div>`);
  const el = P.$('#' + id); const t = new bootstrap.Toast(el, { delay: type === 'danger' ? 8000 : 4500 }); t.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
};
P.err = e => P.toast(e.message || String(e), 'danger');

P.modal = ({ title, body, footer = '', size = '' }) => {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div class="modal fade" tabindex="-1" aria-modal="true" role="dialog"><div class="modal-dialog modal-dialog-scrollable ${size}"><div class="modal-content">
    <div class="modal-header"><h5 class="modal-title">${title}</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Tutup"></button></div>
    <div class="modal-body">${body}</div>${footer ? `<div class="modal-footer">${footer}</div>` : ''}</div></div></div>`;
  const el = wrap.firstElementChild; document.body.appendChild(el);
  const bs = new bootstrap.Modal(el); bs.show();
  el.addEventListener('hidden.bs.modal', () => el.remove());
  return { el, bs, close: () => bs.hide() };
};

/** Ask for a (possibly mandatory) reason / comment. Resolves to the text, or null if cancelled. */
P.ask = ({ title, label, help = '', required = true, minLen = 5, ok = 'Sahkan', okClass = 'btn-primary', value = '' }) => new Promise(resolve => {
  let done = false;
  const m = P.modal({
    title: P.esc(title),
    body: `<label class="form-label" for="askText">${P.esc(label)}${required ? ' <span class="text-danger">*</span>' : ''}</label>
      <textarea id="askText" class="form-control" rows="4" maxlength="2000">${P.esc(value)}</textarea>
      ${help ? `<div class="form-text">${help}</div>` : ''}<div class="invalid-feedback">Sila isi sekurang-kurangnya ${minLen} aksara.</div>`,
    footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn ${okClass}" id="askOk">${P.esc(ok)}</button>`
  });
  const ta = P.$('#askText', m.el);
  m.el.addEventListener('shown.bs.modal', () => ta.focus());
  P.$('#askOk', m.el).addEventListener('click', () => {
    const v = ta.value.trim();
    if (required && v.length < minLen) { ta.classList.add('is-invalid'); return; }
    done = true; m.close(); resolve(v);
  });
  m.el.addEventListener('hidden.bs.modal', () => { if (!done) resolve(null); });
});

P.confirm = ({ title, body, ok = 'Teruskan', okClass = 'btn-primary' }) => new Promise(resolve => {
  let done = false;
  const m = P.modal({ title: P.esc(title), body, footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn ${okClass}" id="cfOk">${P.esc(ok)}</button>` });
  P.$('#cfOk', m.el).addEventListener('click', () => { done = true; m.close(); resolve(true); });
  m.el.addEventListener('hidden.bs.modal', () => { if (!done) resolve(false); });
});

P.formData = form => {
  const o = {};
  P.$$('input,select,textarea', form).forEach(el => {
    if (!el.name || el.disabled) return;
    if (el.type === 'checkbox') o[el.name] = el.checked;
    else if (el.type === 'radio') { if (el.checked) o[el.name] = el.value; }
    else if (el.type !== 'file') o[el.name] = el.value;
  });
  return o;
};

/* ------------------------------------------------------------------ charts */
P.chart = (canvas, config) => {
  const el = typeof canvas === 'string' ? P.$(canvas) : canvas;
  if (!el || !window.Chart) return null;
  config.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: { duration: 350 } }, config.options || {});
  const c = new Chart(el, config); P.state.charts.push(c); return c;
};
P.clearCharts = () => { P.state.charts.forEach(c => { try { c.destroy(); } catch (e) { } }); P.state.charts = []; };
P.COL = { navy: '#10284a', blue: '#1c4c87', teal: '#009e99', amber: '#d3a147', red: '#c34749', grey: '#a9b6c6', green: '#2a9d6f', light: '#dbe4ef' };
if (window.Chart) { Chart.defaults.font.family = '"Segoe UI",Inter,system-ui,Arial,sans-serif'; Chart.defaults.color = '#5f7189'; Chart.defaults.font.size = 11; }

/* ------------------------------------------------------------------ router */
P.route = (pattern, handler, opts = {}) => {
  const keys = []; const rx = new RegExp('^' + pattern.replace(/:([a-z]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '$');
  P.routes.push({ pattern, rx, keys, handler, opts });
};
P.parseHash = () => {
  const raw = (location.hash || '#/').slice(1);
  const [path, qs = ''] = raw.split('?');
  return { path: path || '/', query: Object.fromEntries(new URLSearchParams(qs)) };
};
P.go = (path) => { if (location.hash === '#' + path) P.render(); else location.hash = path; };
P.home = () => {
  const r = P.state.me?.role;
  return r === 'ipt' ? '/ipt' : r === 'executive' ? '/eksekutif' : r ? '/kpt' : '/login';
};
P.render = async () => {
  P.clearCharts();
  P.$$('.modal.show').forEach(m => bootstrap.Modal.getInstance(m)?.hide());
  const { path, query } = P.parseHash();
  for (const r of P.routes) {
    const m = path.match(r.rx);
    if (!m) continue;
    const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
    if (!r.opts.public && !P.state.me) { P.go('/login'); return; }
    if (r.opts.publicOnly && P.state.me) { P.go(P.home()); return; }
    if (r.opts.perm && !r.opts.perm.split('|').some(P.can)) { P.go(P.home()); return; }
    try { await r.handler(params, query); }
    catch (e) { if (e.status !== 401) { P.err(e); console.error(e); } }
    window.scrollTo(0, 0);
    return;
  }
  P.go(P.state.me ? P.home() : '/login');
};

/* ------------------------------------------------------------------ layouts */
P.pilotNotice = () => P.state.config?.pilot_notice_enabled
  ? `<div class="pilot" role="note">${P.esc(P.state.config.pilot_notice)}</div>` : '';

P.layoutPublic = (inner) => {
  document.title = 'PSKG Monitor 2030';
  P.$('#app').innerHTML = `
  <header class="pub-header"><div class="wrap"><div class="brandmark" aria-hidden="true">KPT</div>
    <div><h1>PSKG Monitor 2030</h1><small>Pelan Strategik Kebolehpasaran Graduan 2026–2030</small></div></div></header>
  <main class="pub-main" id="main">${P.pilotNotice()}${inner}</main>`;
};

P.NAV = [
  { label: 'Portal Pelaporan IPT', perm: 'ipt.report', items: [
    ['/ipt', '▦', 'Dashboard IPT'], ['/ipt/teras/1', '◎', 'Borang KPI (20)'], ['/ipt/prestasi', '✓', 'Rekod Disahkan']] },
  { label: 'Pemantauan KPT', perm: 'monitoring.view', items: [
    ['/kpt', '▦', 'Dashboard Pemantauan'], ['/kpt/status', '▤', 'Status Pelaporan IPT'],
    ['/kpt/semakan', '✓', 'Semakan & Pengesahan', 'pending'], ['/eksekutif', '◔', 'Prestasi Nasional']] },
  { label: 'Pengurusan Tertinggi', perm: 'dashboard.executive', exclude: 'monitoring.view', items: [['/eksekutif', '◔', 'Dashboard Eksekutif']] },
  { label: 'Akaun IPT', perm: 'accounts.review', items: [
    ['/kpt/permohonan', '✉', 'Permohonan Akaun IPT', 'apps'], ['/kpt/pradaftar', '＋', 'Pra-Daftar Akaun IPT'],
    ['/kpt/akaun', '☰', 'Senarai Akaun IPT'], ['/kpt/akaun?status=invited', '⧗', 'Status Pengaktifan Akaun'],
    ['/kpt/sejarah', '⟲', 'Sejarah Kelulusan'], ['/kpt/institusi', '⌂', 'Direktori Institusi']] },
  { label: 'Pentadbiran', perm: 'admin.users', items: [
    ['/admin/pengguna', '👤', 'Pengguna & Peranan'], ['/admin/tempoh', '▣', 'Tempoh Pelaporan'], ['/admin/kpi', '◎', 'KPI & Sasaran'],
    ['/admin/audit', '⚑', 'Log Audit'], ['/admin/tetapan', '⚙', 'Tetapan Sistem']] },
  { label: 'Umum', perm: '*', items: [['/laporan', '⇩', 'Laporan & Eksport'], ['/notifikasi', '🔔', 'Notifikasi', 'unread'], ['/kpt/emel', '✉', 'Pratonton Emel (Dev)', null, 'notifications.outbox']] },
];

P.layoutApp = ({ title, subtitle = '', html }) => {
  const me = P.state.me; const cur = '#' + (location.hash.slice(1) || '/');
  document.title = title + ' — PSKG Monitor 2030';
  // the single best-matching (longest) nav entry is highlighted
  const allHrefs = P.NAV.flatMap(g => g.items.map(i => i[0]));
  const matches = h => cur === '#' + h || cur.startsWith('#' + h + '/') || cur.startsWith('#' + h + '?');
  const best = (cur.startsWith('#/ipt/') && !cur.startsWith('#/ipt/prestasi')) ? '/ipt/teras/1'
    : allHrefs.filter(matches).sort((a, b) => b.length - a.length)[0];
  const nav = P.NAV.filter(g => (g.perm === '*' || P.can(g.perm)) && !(g.exclude && P.can(g.exclude))).map(g => `
    <div class="navlabel">${P.esc(g.label)}</div>${g.items.filter(it => !it[4] || P.can(it[4])).map(([href, ico, label, counter]) => {
      const active = href === best;
      const cnt = counter === 'unread' && P.state.unread ? `<span class="count">${P.state.unread}</span>` :
        counter === 'pending' && P.state.pending ? `<span class="count">${P.state.pending}</span>` :
        counter === 'apps' && P.state.apps ? `<span class="count">${P.state.apps}</span>` : '';
      return `<a class="navbtn ${active ? 'active' : ''}" href="#${href}" ${active ? 'aria-current="page"' : ''}><span class="ico" aria-hidden="true">${ico}</span><span>${P.esc(label)}</span>${cnt}</a>`;
    }).join('')}`).join('');
  const initials = (me.name || '?').split(/\s+/).slice(0, 2).map(s => s[0]).join('').toUpperCase();
  P.$('#app').innerHTML = `
  <div class="shell">
    <nav class="sidebar" id="sidebar" aria-label="Navigasi utama">
      <div class="brand"><div class="brandmark" aria-hidden="true">KPT</div><div><strong>PSKG Monitor</strong><small>PELAN STRATEGIK 2026–2030</small></div></div>
      ${nav}
      <div class="sidefoot">${P.esc(me.role_label)}${me.institution ? '<br>' + P.esc(me.institution.name) : ''}<br>Versi MVP · Data diluluskan sahaja dalam dashboard rasmi.</div>
    </nav>
    <div class="workspace">
      <header class="topbar">
        <div class="d-flex align-items-center gap-2"><button class="btn btn-light btn-sm menu-toggle" data-act="toggle-menu" aria-label="Menu">☰</button>
          <div><h1>${P.esc(title)}</h1>${subtitle ? `<p>${subtitle}</p>` : '<p>Sistem Pemantauan Prestasi, Pelaporan dan Analitik Kebolehpasaran Graduan Peringkat Nasional</p>'}</div></div>
        <div class="tools">
          <a class="bell d-grid place-items-center text-decoration-none text-center" href="#/notifikasi" aria-label="Notifikasi" style="line-height:36px">🔔${P.state.unread ? `<span class="dot">${P.state.unread}</span>` : ''}</a>
          <div class="dropdown">
            <button class="userchip dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false"><span class="av">${P.esc(initials)}</span><span class="text-start"><span class="nm d-block">${P.esc(me.name)}</span><span class="rl d-block">${P.esc(me.role_label)}</span></span></button>
            <ul class="dropdown-menu dropdown-menu-end"><li><span class="dropdown-item-text small text-muted">${P.esc(me.email)}</span></li>
              <li><a class="dropdown-item" href="#/akaun-saya">Tukar kata laluan</a></li><li><hr class="dropdown-divider"></li>
              <li><button class="dropdown-item text-danger" data-act="logout">Log keluar</button></li></ul>
          </div>
        </div>
      </header>
      <main class="content" id="main">${P.pilotNotice() ? `<div class="mb-3">${P.pilotNotice()}</div>` : ''}${html}</main>
    </div>
  </div>`;
};

P.heading = (title, sub, right = '') => `<div class="heading"><div><h2>${title}</h2><p>${sub}</p></div>${right ? `<div class="filters">${right}</div>` : ''}</div>`;
P.emptyState = (msg, icon = '◌') => `<div class="empty"><div class="big" aria-hidden="true">${icon}</div><div>${msg}</div></div>`;
P.loading = () => `<div class="empty"><div class="spinner-border spinner-border-sm text-primary"></div> Memuatkan…</div>`;

/* ------------------------------------------------------------------ event delegation */
document.addEventListener('click', async ev => {
  const el = ev.target.closest('[data-act]');
  if (!el) return;
  const fn = P.actions[el.dataset.act];
  if (!fn) return;
  ev.preventDefault();
  if (el.dataset.busy) return;
  el.dataset.busy = '1';
  try { await fn(el, ev); } catch (e) { if (e.status !== 401) P.err(e); } finally { delete el.dataset.busy; }
});
document.addEventListener('submit', async ev => {
  const form = ev.target.closest('form[data-form]');
  if (!form) return;
  ev.preventDefault();
  const fn = P.forms[form.dataset.form];
  if (!fn) return;
  const btns = P.$$('button[type=submit],button:not([type])', form);
  btns.forEach(b => b.disabled = true);
  try { await fn(form, ev); } catch (e) { if (e.status !== 401) P.err(e); } finally { btns.forEach(b => b.disabled = false); }
});
['input', 'change'].forEach(type => document.addEventListener(type, ev => {
  const el = ev.target.closest('[data-on]');
  if (!el) return;
  const [evt, name] = el.dataset.on.split(':');
  if (evt !== type) return;
  const fn = P.inputs[name];
  if (fn) Promise.resolve(fn(el, ev)).catch(P.err);
}));
P.actions['toggle-menu'] = () => P.$('#sidebar')?.classList.toggle('open');
P.actions['go'] = el => P.go(el.dataset.href);
P.actions['logout'] = async () => {
  try { await P.api('/logout', { method: 'POST', quiet401: true }); } catch (e) { }
  P.state.me = null; P.toast('Anda telah log keluar.', 'info'); P.go('/login');
};
