/* Public pages: login, IPT self-registration, application status, password reset, account activation. */
'use strict';
(() => {
  const field = (name, label, { type = 'text', req = true, help = '', attrs = '', value = '', col = 'col-12' } = {}) => `
    <div class="${col}"><label class="form-label" for="f-${name}">${label}${req ? ' <span class="text-danger" aria-hidden="true">*</span>' : ''}</label>
    <input class="form-control" id="f-${name}" name="${name}" type="${type}" value="${P.esc(value)}" ${req ? 'required' : ''} ${attrs}>
    ${help ? `<div class="form-text">${help}</div>` : ''}</div>`;
  const PW_HELP = 'Sekurang-kurangnya 12 aksara dengan huruf besar, huruf kecil dan nombor.';

  /* -------------------------------------------------------------- login */
  P.route('/login', async () => {
    P.layoutPublic(`
    <div class="pub-card">
      <h2>Log Masuk</h2><p class="lead-sub">Gunakan akaun yang telah diluluskan.</p>
      <div id="loginMsg"></div>
      <form data-form="login" novalidate>
        <div class="row g-3">
          ${field('email', 'Emel', { type: 'email', attrs: 'autocomplete="username" maxlength="200" autofocus' })}
          ${field('password', 'Kata laluan', { type: 'password', attrs: 'autocomplete="current-password" maxlength="200"' })}
        </div>
        <div class="d-grid gap-2 mt-4">
          <button class="btn btn-primary btn-lg" type="submit">Log masuk</button>
          <a class="btn btn-outline-primary" href="#/daftar">Daftar institusi baharu</a>
        </div>
      </form>
      <div class="pub-links"><a href="#/lupa">Lupa kata laluan</a><a href="#/status">Semak status permohonan</a></div>
    </div>`);
  }, { public: true, publicOnly: true });

  P.forms.login = async form => {
    const d = P.formData(form);
    const box = P.$('#loginMsg');
    box.innerHTML = '';
    if (!d.email || !d.password) { box.innerHTML = `<div class="callout danger">Sila isi emel dan kata laluan.</div>`; return; }
    try {
      const r = await P.api('/login', { method: 'POST', body: { email: d.email, password: d.password }, quiet401: true });
      P.state.me = r.user;
      await P.refreshCounters();
      P.toast('Selamat datang, ' + r.user.name + '.');
      P.go(P.home());
    } catch (e) {
      box.innerHTML = `<div class="callout ${e.status === 403 ? 'warn' : 'danger'}" role="alert">${P.esc(e.message)}</div>`;
      form.password.value = ''; form.password.focus();
    }
  };

  /* -------------------------------------------------------------- self-registration */
  P.route('/daftar', async () => {
    const cats = Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}">${P.esc(v)}</option>`).join('');
    const states = (P.state.config?.states || []).map(s => `<option>${P.esc(s)}</option>`).join('');
    P.layoutPublic(`
    <div class="pub-card wide" id="regCard">
      <h2>Permohonan Akaun IPT</h2>
      <p class="lead-sub">Permohonan institusi dan pengguna perlu diluluskan oleh Penyelaras KPT.</p>
      <form data-form="register" novalidate>
        <div class="section-title"><span class="step">A</span> Maklumat Institusi</div>
        <div class="btn-group mb-3" role="group" aria-label="Sumber maklumat institusi">
          <input type="radio" class="btn-check" name="inst_mode" id="m-new" value="new" checked data-on="change:inst-mode"><label class="btn btn-outline-primary btn-sm" for="m-new">Institusi baharu</label>
          <input type="radio" class="btn-check" name="inst_mode" id="m-existing" value="existing" data-on="change:inst-mode"><label class="btn btn-outline-primary btn-sm" for="m-existing">Pilih institusi sedia ada</label>
        </div>
        <div id="instExisting" class="d-none mb-2">
          <label class="form-label" for="instSearch">Cari institusi (nama atau kod) <span class="text-danger">*</span></label>
          <input class="form-control" id="instSearch" placeholder="Contoh: UiTM" data-on="input:inst-search" autocomplete="off">
          <input type="hidden" name="existing_institution_id" id="existingId">
          <div id="instResults" class="list-group mt-1"></div>
          <div class="form-text">Gunakan pilihan ini jika institusi anda telah berdaftar dalam direktori, bagi mengelakkan rekod institusi berganda.</div>
        </div>
        <div id="instNew" class="row g-3">
          ${field('inst_name', '1. Nama rasmi IPT', { col: 'col-md-8', attrs: 'maxlength="200"' })}
          ${field('inst_code', '2. Kod institusi', { col: 'col-md-4', attrs: 'maxlength="40"', help: 'Kod rasmi IPT (contoh: UITM).' })}
          <div class="col-md-4"><label class="form-label" for="f-inst_category">3. Kategori IPT <span class="text-danger">*</span></label><select class="form-select" id="f-inst_category" name="inst_category" required><option value="">— Pilih —</option>${cats}</select></div>
          ${field('inst_address', '4. Alamat institusi', { col: 'col-md-8', attrs: 'maxlength="500"' })}
          <div class="col-md-4"><label class="form-label" for="f-inst_state">5. Negeri <span class="text-danger">*</span></label><select class="form-select" id="f-inst_state" name="inst_state" required><option value="">— Pilih —</option>${states}</select></div>
          ${field('inst_email', '6. Emel rasmi institusi', { type: 'email', col: 'col-md-8', attrs: 'maxlength="200"' })}
        </div>
        <div class="section-title"><span class="step">B</span> Maklumat Penyelaras IPT</div>
        <div class="row g-3">
          ${field('coordinator_name', '1. Nama penuh penyelaras', { col: 'col-md-6', attrs: 'maxlength="150" autocomplete="name"' })}
          ${field('position', '2. Jawatan', { col: 'col-md-6', attrs: 'maxlength="150"' })}
          ${field('department', '3. Bahagian / Jabatan', { col: 'col-md-6', attrs: 'maxlength="150"' })}
          ${field('official_email', '4. Emel rasmi pegawai', { type: 'email', col: 'col-md-6', attrs: 'maxlength="200"' })}
          ${field('phone', '5. Nombor telefon pejabat', { type: 'tel', col: 'col-md-6', attrs: 'maxlength="40" autocomplete="tel"', help: 'Contoh: 03-5544 2000' })}
        </div>
        <div class="section-title"><span class="step">C</span> Maklumat Akaun</div>
        <div class="row g-3">
          ${field('account_email', '1. Emel pengguna', { type: 'email', col: 'col-md-12', attrs: 'maxlength="200" autocomplete="username"', help: 'Emel ini digunakan untuk log masuk. Disyorkan menggunakan emel rasmi institusi.' })}
          ${field('password', '2. Kata laluan', { type: 'password', col: 'col-md-6', attrs: 'maxlength="128" autocomplete="new-password"', help: PW_HELP })}
          ${field('confirm_password', '3. Sahkan kata laluan', { type: 'password', col: 'col-md-6', attrs: 'maxlength="128" autocomplete="new-password"' })}
        </div>
        <div id="regMsg" class="mt-3"></div>
        <div class="d-flex flex-wrap gap-2 mt-3">
          <button class="btn btn-primary btn-lg" type="submit">Hantar permohonan</button>
          <a class="btn btn-link" href="#/login">Sudah berdaftar? Log masuk</a>
        </div>
      </form>
    </div>`);
  }, { public: true, publicOnly: true });

  P.inputs['inst-mode'] = el => {
    const existing = el.value === 'existing';
    P.$('#instExisting').classList.toggle('d-none', !existing);
    P.$('#instNew').classList.toggle('d-none', existing);
    P.$$('#instNew [required]').forEach(i => i.disabled = existing);
    if (!existing) P.$('#existingId').value = '';
  };
  let searchTimer;
  P.inputs['inst-search'] = el => {
    clearTimeout(searchTimer);
    P.$('#existingId').value = '';
    searchTimer = setTimeout(async () => {
      const q = el.value.trim(); const box = P.$('#instResults');
      if (q.length < 2) { box.innerHTML = ''; return; }
      const rows = await P.api('/public/institutions?q=' + encodeURIComponent(q));
      box.innerHTML = rows.length ? rows.map(r => `<button type="button" class="list-group-item list-group-item-action" data-act="pick-inst" data-id="${r.id}" data-label="${P.esc(r.code + ' — ' + r.name)}">${P.esc(r.code)} — ${P.esc(r.name)} <span class="text-muted small">${P.esc(P.CATS()[r.category] || '')}</span></button>`).join('')
        : '<div class="list-group-item text-muted small">Tiada padanan. Gunakan "Institusi baharu".</div>';
    }, 250);
  };
  P.actions['pick-inst'] = el => {
    P.$('#existingId').value = el.dataset.id; P.$('#instSearch').value = el.dataset.label; P.$('#instResults').innerHTML =
      `<div class="callout ok mt-2 mb-0">Dipilih: ${P.esc(el.dataset.label)}</div>`;
  };

  P.forms.register = async form => {
    const d = P.formData(form); const box = P.$('#regMsg'); box.innerHTML = '';
    const existing = d.inst_mode === 'existing';
    const missing = [];
    if (existing && !d.existing_institution_id) missing.push('Pilih institusi daripada senarai');
    if (!existing) ['inst_name', 'inst_code', 'inst_category', 'inst_address', 'inst_state', 'inst_email'].forEach(k => { if (!d[k]) missing.push(P.$(`label[for=f-${k}]`).textContent.replace('*', '').trim()); });
    ['coordinator_name', 'position', 'department', 'official_email', 'phone', 'account_email', 'password', 'confirm_password'].forEach(k => { if (!d[k]) missing.push(P.$(`label[for=f-${k}]`).textContent.replace('*', '').trim()); });
    if (d.password && d.password !== d.confirm_password) missing.push('Pengesahan kata laluan tidak sepadan');
    if (missing.length) { box.innerHTML = `<div class="callout danger" role="alert"><b>Sila lengkapkan:</b><br>${missing.map(P.esc).join('<br>')}</div>`; return; }
    const body = { ...d, existing_institution_id: existing ? +d.existing_institution_id : null };
    delete body.inst_mode;
    try {
      const r = await P.api('/register', { method: 'POST', body });
      P.$('#regCard').innerHTML = `
        <h2>Permohonan Dihantar</h2>
        <div class="callout ok mt-3" role="status"><b>${P.esc(r.message)}</b></div>
        <div class="refbox my-3">Simpan maklumat berikut untuk menyemak status permohonan:<br>
          No. Permohonan: <code>${P.esc(r.ref_no)}</code><br>Kod Semakan: <code>${P.esc(r.status_code)}</code><br>
          Status: ${P.badge('PENDING_APPROVAL')}</div>
        <p class="text-muted small">Anda belum boleh log masuk sehingga permohonan diluluskan oleh Penyelaras KPT. Notifikasi akan dihantar ke emel anda.</p>
        <div class="d-flex gap-2"><a class="btn btn-primary" href="#/status?ref=${encodeURIComponent(r.ref_no)}">Semak status permohonan</a><a class="btn btn-outline-primary" href="#/login">Kembali ke Log Masuk</a></div>`;
    } catch (e) { box.innerHTML = `<div class="callout danger" role="alert">${P.esc(e.message)}</div>`; }
  };

  /* -------------------------------------------------------------- application status */
  P.route('/status', async (_, q) => {
    P.layoutPublic(`<div class="pub-card"><h2>Semak Status Permohonan</h2>
      <p class="lead-sub">Masukkan No. Permohonan dan Kod Semakan yang dipaparkan semasa permohonan dihantar.</p>
      <form data-form="status" novalidate><div class="row g-3">
        ${field('ref_no', 'No. Permohonan', { value: q.ref || '', attrs: 'maxlength="40" placeholder="REG-2026-XXXXXX"' })}
        ${field('status_code', 'Kod Semakan', { attrs: 'maxlength="40" autocomplete="off"' })}</div>
        <div class="d-grid mt-4"><button class="btn btn-primary" type="submit">Semak status</button></div></form>
      <div id="statusOut" class="mt-3"></div>
      <div class="pub-links"><a href="#/login">← Log masuk</a><a href="#/daftar">Daftar institusi baharu</a></div></div>`);
  }, { public: true });
  P.forms.status = async form => {
    const d = P.formData(form); const out = P.$('#statusOut');
    try {
      const r = await P.api('/register/status', { method: 'POST', body: d });
      out.innerHTML = `<div class="detail"><dl class="kv"><dt>No. Permohonan</dt><dd>${P.esc(r.ref_no)}</dd><dt>Institusi</dt><dd>${P.esc(r.institution)}</dd>
        <dt>Status</dt><dd>${P.badge(r.status, r.status_label)}</dd><dt>Tarikh permohonan</dt><dd>${P.date(r.submitted_at)}</dd>
        ${r.decided_at ? `<dt>Tarikh keputusan</dt><dd>${P.date(r.decided_at)}</dd>` : ''}${r.reason ? `<dt>Sebab</dt><dd>${P.esc(r.reason)}</dd>` : ''}</dl>
        ${r.status === 'APPROVED' ? '<a class="btn btn-primary btn-sm mt-2" href="#/login">Log masuk sekarang</a>' : ''}</div>`;
    } catch (e) { out.innerHTML = `<div class="callout danger">${P.esc(e.message)}</div>`; }
  };

  /* -------------------------------------------------------------- forgot / reset password */
  P.route('/lupa', async () => {
    P.layoutPublic(`<div class="pub-card"><h2>Lupa Kata Laluan</h2><p class="lead-sub">Pautan tetapan semula sekali guna akan dihantar ke emel akaun yang aktif.</p>
      <form data-form="forgot" novalidate><div class="row g-3">${field('email', 'Emel akaun', { type: 'email', attrs: 'maxlength="200"' })}</div>
      <div class="d-grid mt-4"><button class="btn btn-primary" type="submit">Hantar pautan tetapan semula</button></div></form>
      <div id="forgotOut" class="mt-3"></div><div class="pub-links"><a href="#/login">← Log masuk</a></div></div>`);
  }, { public: true });
  P.forms.forgot = async form => {
    const r = await P.api('/password/forgot', { method: 'POST', body: P.formData(form) });
    P.$('#forgotOut').innerHTML = `<div class="callout info">${P.esc(r.message)}${P.state.config?.smtp_enabled ? '' :
      '<br><span class="devbadge">PEMBANGUNAN</span> SMTP belum dikonfigurasi: emel tidak dihantar sebenar. Pentadbir boleh melihat pratonton emel dalam sistem.'}</div>`;
  };
  P.route('/reset', async (_, q) => {
    P.layoutPublic(`<div class="pub-card"><h2>Tetapkan Semula Kata Laluan</h2><p class="lead-sub">Masukkan kata laluan baharu anda.</p>
      <form data-form="reset" novalidate><input type="hidden" name="token" value="${P.esc(q.token || '')}"><div class="row g-3">
      ${field('password', 'Kata laluan baharu', { type: 'password', attrs: 'autocomplete="new-password" maxlength="128"', help: PW_HELP })}
      ${field('confirm_password', 'Sahkan kata laluan', { type: 'password', attrs: 'autocomplete="new-password" maxlength="128"' })}</div>
      <div class="d-grid mt-4"><button class="btn btn-primary" type="submit">Simpan kata laluan</button></div></form><div id="resetOut" class="mt-3"></div></div>`);
  }, { public: true });
  P.forms.reset = async form => {
    try {
      const r = await P.api('/password/reset', { method: 'POST', body: P.formData(form) });
      P.$('#resetOut').innerHTML = `<div class="callout ok">${P.esc(r.message)} <a href="#/login">Log masuk</a></div>`; form.remove();
    } catch (e) { P.$('#resetOut').innerHTML = `<div class="callout danger">${P.esc(e.message)}</div>`; }
  };

  /* -------------------------------------------------------------- activation (KPT pre-registration) */
  P.route('/aktif', async (_, q) => {
    P.layoutPublic(`<div class="pub-card" id="actCard">${P.loading()}</div>`);
    let d;
    try { d = await P.api('/activation/details', { method: 'POST', body: { token: q.token || '' } }); }
    catch (e) {
      P.$('#actCard').innerHTML = `<h2>Pengaktifan Akaun</h2><div class="callout danger mt-3">${P.esc(e.message)}</div><div class="pub-links"><a href="#/login">← Log masuk</a></div>`; return;
    }
    P.$('#actCard').innerHTML = `<h2>Pengaktifan Akaun</h2><p class="lead-sub">Akaun anda telah dipra-daftar oleh Penyelaras KPT. Sahkan maklumat dan tetapkan kata laluan.</p>
      <div class="detail mb-3"><dl class="kv"><dt>Nama</dt><dd>${P.esc(d.name)}</dd><dt>Emel</dt><dd>${P.esc(d.email)}</dd>
      ${d.institution ? `<dt>Institusi</dt><dd>${P.esc(d.institution.code)} — ${P.esc(d.institution.name)}</dd>` : ''}
      ${d.position ? `<dt>Jawatan</dt><dd>${P.esc(d.position)}</dd>` : ''}${d.department ? `<dt>Bahagian / Jabatan</dt><dd>${P.esc(d.department)}</dd>` : ''}
      ${d.phone ? `<dt>Telefon</dt><dd>${P.esc(d.phone)}</dd>` : ''}<dt>Pautan sah sehingga</dt><dd>${P.date(d.expires_at)}</dd></dl></div>
      <form data-form="activate" novalidate><input type="hidden" name="token" value="${P.esc(q.token)}">
        <div class="form-check mb-3"><input class="form-check-input" type="checkbox" id="f-confirm" name="confirm_details"><label class="form-check-label" for="f-confirm">Saya mengesahkan maklumat di atas adalah tepat. Jika tidak tepat, sila hubungi Penyelaras KPT.</label></div>
        <div class="row g-3">${field('password', 'Kata laluan', { type: 'password', attrs: 'autocomplete="new-password" maxlength="128"', help: PW_HELP })}
        ${field('confirm_password', 'Sahkan kata laluan', { type: 'password', attrs: 'autocomplete="new-password" maxlength="128"' })}</div>
        <div class="d-grid mt-4"><button class="btn btn-primary" type="submit">Aktifkan akaun</button></div></form><div id="actOut" class="mt-3"></div>`;
  }, { public: true });
  P.forms.activate = async form => {
    try {
      const r = await P.api('/activation', { method: 'POST', body: P.formData(form) });
      P.$('#actCard').innerHTML = `<h2>Akaun Diaktifkan</h2><div class="callout ok mt-3">${P.esc(r.message)}</div><a class="btn btn-primary" href="#/login">Log masuk</a>`;
    } catch (e) { P.$('#actOut').innerHTML = `<div class="callout danger">${P.esc(e.message)}</div>`; }
  };

  /* -------------------------------------------------------------- my account */
  P.route('/akaun-saya', async () => {
    P.layoutApp({ title: 'Akaun Saya', html: `<div class="panel" style="max-width:560px"><div class="paneltitle"><h3>Tukar kata laluan</h3></div>
      <form data-form="chpw" novalidate><div class="row g-3">${field('current_password', 'Kata laluan semasa', { type: 'password', attrs: 'autocomplete="current-password"' })}
      ${field('new_password', 'Kata laluan baharu', { type: 'password', attrs: 'autocomplete="new-password" maxlength="128"', help: PW_HELP })}
      ${field('confirm_password', 'Sahkan kata laluan baharu', { type: 'password', attrs: 'autocomplete="new-password" maxlength="128"' })}</div>
      <button class="btn btn-primary mt-3" type="submit">Simpan</button></form></div>` });
  });
  P.forms.chpw = async form => { const r = await P.api('/me/password', { method: 'POST', body: P.formData(form) }); P.toast(r.message); form.reset(); };
})();
