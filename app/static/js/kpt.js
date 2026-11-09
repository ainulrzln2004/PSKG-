/* Portal Pemantauan KPT: monitoring dashboard, account applications, pre-registration, IPT accounts,
   approval history, reporting-status matrix and the verification workspace. */
'use strict';
(() => {
  const yearSel = (y, on) => `<label class="visually-hidden" for="ySel">Tahun</label><select id="ySel" class="form-select" data-on="change:${on}">${P.yearOptions(y)}</select>`;
  const catOptions = (sel = '') => `<option value="">Semua kategori</option>` + Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}" ${sel === k ? 'selected' : ''}>${P.esc(v)}</option>`).join('');
  const terasOptions = (sel = '') => `<option value="">Semua 5 Teras</option>` + Object.entries(P.terasNames).map(([k, v]) => `<option value="${k}" ${+sel === +k ? 'selected' : ''}>Teras ${k}: ${P.esc(v)}</option>`).join('');
  const qs = o => Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

  /* -------------------------------------------------------------- monitoring dashboard */
  P.inputs['kpt-year'] = el => { P.state.year = +el.value; P.render(); };
  P.route('/kpt', async () => {
    const y = P.state.year;
    const d = await P.api('/monitoring/summary?year=' + y);
    const s = (label, v, cls = '', hint = '', href = '') => `<${href ? `a href="${href}" style="text-decoration:none;color:inherit"` : 'div'} class="stat ${cls}"><div class="label">${label}</div><div class="value">${v}</div>${hint ? `<div class="hint">${hint}</div>` : ''}</${href ? 'a' : 'div'}>`;
    P.layoutApp({
      title: 'Dashboard Pemantauan', subtitle: 'Portal Pemantauan KPT — status pelaporan IPT dan tindakan semakan',
      html: P.heading('Dashboard Pemantauan', `Tahun pelaporan ${y}`, yearSel(y, 'kpt-year')) + `
      <div class="stats">
        ${s('Jumlah IPT berdaftar', d.institutions_registered, 'blue', 'Semua status', '#/kpt/institusi')}
        ${s('Jumlah IPT aktif', d.institutions_active, 'blue')}
        ${s('Laporan dihantar', d.reports_submitted, '', 'Termasuk disahkan & dipulangkan')}
        ${s('Laporan disahkan', d.reports_verified, 'teal')}
        ${s('Menunggu semakan', d.reports_pending, 'amber', 'Tindakan Penyelaras KPT', '#/kpt/semakan')}
        ${s('Laporan dipulangkan', d.reports_returned, 'red')}
        ${s('IPT belum melapor', d.institutions_not_reported, 'red', 'Tiada laporan dihantar', '#/kpt/status')}
        ${s('KPI belum lengkap', d.kpis_incomplete + ' / 20', '', 'Sekurang-kurangnya satu IPT belum disahkan')}
      </div>
      ${d.pending_applications ? `<div class="callout warn"><b>${d.pending_applications}</b> permohonan akaun IPT menunggu kelulusan. <a href="#/kpt/permohonan">Semak permohonan →</a></div>` : ''}
      <div class="grid2">
        <div class="panel"><div class="paneltitle"><h3>Status pelaporan mengikut Teras</h3><span class="meta">Bilangan sel IPT × KPI</span></div><div class="chartbox"><canvas id="cTeras"></canvas></div></div>
        <div class="panel"><div class="paneltitle"><h3>Ringkasan status (${y})</h3></div><div class="chartbox"><canvas id="cDonut"></canvas></div></div>
      </div>
      <div class="panel"><div class="paneltitle"><h3>Tindakan pantas</h3></div><div class="d-flex flex-wrap gap-2">
        <a class="btn btn-primary" href="#/kpt/semakan">Semakan & Pengesahan</a><a class="btn btn-soft" href="#/kpt/status">Matriks Status Pelaporan</a>
        <a class="btn btn-soft" href="#/kpt/permohonan">Permohonan Akaun IPT</a><a class="btn btn-soft" href="#/kpt/pradaftar">Pra-Daftar Akaun IPT</a>
        <a class="btn btn-soft" href="#/eksekutif">Prestasi Nasional</a><a class="btn btn-soft" href="#/laporan">Laporan & Eksport</a></div></div>`
    });
    const SER = [['VERIFIED', 'Disahkan', P.COL.teal], ['SUBMITTED', 'Menunggu semakan', P.COL.amber], ['RETURNED', 'Dipulangkan', P.COL.red], ['DRAFT', 'Draf', '#7aa5d6'], ['NOT_STARTED', 'Belum diisi', P.COL.grey]];
    P.chart('#cTeras', {
      type: 'bar', data: { labels: d.by_teras.map(t => 'Teras ' + t.teras), datasets: SER.map(([k, l, c]) => ({ label: l, data: d.by_teras.map(t => t.counts[k] || 0), backgroundColor: c })) },
      options: { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } }, plugins: { legend: { position: 'bottom' } } }
    });
    const tot = { VERIFIED: d.reports_verified, SUBMITTED: d.reports_pending, RETURNED: d.reports_returned, DRAFT: d.reports_draft, NOT_STARTED: d.reports_not_started };
    P.chart('#cDonut', { type: 'doughnut', data: { labels: SER.map(x => x[1]), datasets: [{ data: SER.map(x => tot[x[0]] || 0), backgroundColor: SER.map(x => x[2]) }] }, options: { plugins: { legend: { position: 'bottom' } } } });
  }, { perm: 'monitoring.view' });

  /* -------------------------------------------------------------- account applications */
  P.route('/kpt/permohonan', async (_, q) => {
    const status = q.status ?? 'PENDING_APPROVAL';
    const rows = await P.api('/kpt/applications?' + qs({ status, q: q.q || '' }));
    P.layoutApp({
      title: 'Permohonan Akaun IPT', subtitle: 'Setiap permohonan pendaftaran IPT mesti diluluskan oleh Penyelaras KPT sebelum log masuk dibenarkan',
      html: P.heading('Permohonan Akaun IPT', `${rows.length} permohonan dipaparkan`, `
        <form class="filters" data-form="app-filter"><input class="form-control" name="q" placeholder="Cari IPT, kod, nama, emel…" value="${P.esc(q.q || '')}" aria-label="Carian">
        <select class="form-select" name="status" aria-label="Status"><option value="">Semua status</option>${['PENDING_APPROVAL', 'APPROVED', 'REJECTED'].map(s => `<option value="${s}" ${status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}</select>
        <button class="btn btn-primary" type="submit">Tapis</button></form>`) + `
      <div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>No. Permohonan</th><th>Nama IPT</th><th>Kod IPT</th><th>Kategori IPT</th><th>Nama Penyelaras</th><th>Emel</th><th>Tarikh Permohonan</th><th>Status</th><th>Tindakan</th></tr></thead><tbody>
      ${rows.length ? rows.map(a => `<tr><td><b>${P.esc(a.ref_no)}</b>${a.source === 'LEGACY_V2B' ? '<div class="meta">dari Pilot V2B</div>' : ''}</td><td>${P.esc(a.inst_name)}</td><td>${P.esc(a.inst_code)}</td><td>${P.esc(a.inst_category)}</td>
        <td>${P.esc(a.coordinator_name)}</td><td>${P.esc(a.email)}</td><td>${P.date(a.submitted_at)}</td><td>${P.badge(a.status, a.status_label)}</td>
        <td><button class="btn btn-sm btn-primary" data-act="app-view" data-id="${a.id}">Lihat Permohonan</button></td></tr>`).join('')
        : `<tr><td colspan="9">${P.emptyState('Tiada permohonan bagi tapisan ini.')}</td></tr>`}</tbody></table></div></div>`
    });
  }, { perm: 'accounts.review' });
  P.forms['app-filter'] = form => { const d = P.formData(form); P.go('/kpt/permohonan?' + qs({ q: d.q, status: d.status }) + (d.status === '' ? '&status=' : '')); };
  P.actions['app-view'] = async el => {
    const a = await P.api('/kpt/applications/' + el.dataset.id);
    const pending = a.status === 'PENDING_APPROVAL';
    const cats = Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}" ${a.institution.category === k ? 'selected' : ''}>${P.esc(v)}</option>`).join('');
    const m = P.modal({
      title: 'Permohonan ' + P.esc(a.ref_no), size: 'modal-lg',
      body: `<div class="mb-2">${P.badge(a.status, a.status_label)} <span class="meta">Dihantar ${P.date(a.submitted_at)}${a.decided_at ? ` · Diputuskan ${P.date(a.decided_at)} oleh ${P.esc(a.decided_by)}` : ''}</span></div>
      ${a.reason ? `<div class="callout ${a.status === 'REJECTED' ? 'danger' : 'info'}">${P.esc(a.reason)}</div>` : ''}
      <div class="section-title">A. Maklumat Institusi</div><dl class="kv"><dt>Nama rasmi IPT</dt><dd>${P.esc(a.institution.name)}</dd><dt>Kod institusi</dt><dd>${P.esc(a.institution.code)}</dd>
        <dt>Kategori IPT</dt><dd>${P.esc(a.institution.category_label)}</dd><dt>Alamat</dt><dd>${P.esc(a.institution.address || '—')}</dd><dt>Negeri</dt><dd>${P.esc(a.institution.state || '—')}</dd><dt>Emel rasmi institusi</dt><dd>${P.esc(a.institution.email || '—')}</dd></dl>
      <div class="section-title">B. Maklumat Penyelaras IPT</div><dl class="kv"><dt>Nama penuh</dt><dd>${P.esc(a.coordinator.name)}</dd><dt>Jawatan</dt><dd>${P.esc(a.coordinator.position || '—')}</dd>
        <dt>Bahagian / Jabatan</dt><dd>${P.esc(a.coordinator.department || '—')}</dd><dt>Emel rasmi pegawai</dt><dd>${P.esc(a.coordinator.official_email || '—')}</dd><dt>Telefon pejabat</dt><dd>${P.esc(a.coordinator.phone || '—')}</dd></dl>
      <div class="section-title">C. Maklumat Akaun</div><dl class="kv"><dt>Emel pengguna</dt><dd>${P.esc(a.coordinator.account_email)}</dd></dl>
      <div class="section-title">Semakan sistem</div><ul class="small">${a.checks.map(c => `<li>${P.esc(c)}</li>`).join('')}</ul>
      <div class="callout warn small mb-2">Sahkan identiti pemohon secara bebas (contoh: panggilan ke talian rasmi institusi) sebelum meluluskan. Sistem tidak mengesahkan identiti secara automatik.</div>
      ${pending && !a.institution.category ? `<label class="form-label" for="appCat">Tetapkan kategori institusi</label><select class="form-select mb-2" id="appCat"><option value="">— Pilih —</option>${cats}</select>` : ''}
      ${a.history.length ? `<div class="section-title">Sejarah</div>${a.history.map(h => `<div class="hist"><b>${P.esc(h.action)}</b> · ${P.esc(h.actor || 'Pemohon')}${h.reason ? ' — ' + P.esc(h.reason) : ''}<div class="when">${P.date(h.at)}</div></div>`).join('')}` : ''}`,
      footer: pending ? `<button class="btn btn-outline-danger" id="btnReject">Tolak Permohonan</button><button class="btn btn-teal" id="btnApprove">Luluskan Permohonan</button>` : `<button class="btn btn-light" data-bs-dismiss="modal">Tutup</button>`
    });
    if (!pending) return;
    P.$('#btnApprove', m.el).addEventListener('click', async () => {
      try {
        const cat = P.$('#appCat', m.el)?.value || null;
        await P.api(`/kpt/applications/${a.id}/approve`, { method: 'POST', body: { reason: '', category: cat } });
        m.close(); P.toast('Permohonan diluluskan. Akaun Penyelaras IPT kini aktif.'); P.refreshCounters().then(P.render);
      } catch (e) { P.err(e); }
    });
    P.$('#btnReject', m.el).addEventListener('click', async () => {
      m.close();
      const reason = await P.ask({ title: 'Tolak permohonan ' + a.ref_no, label: 'Sebab penolakan', ok: 'Tolak Permohonan', okClass: 'btn-danger', help: 'Sebab ini akan dimaklumkan kepada pemohon.' });
      if (reason === null) return;
      await P.api(`/kpt/applications/${a.id}/reject`, { method: 'POST', body: { reason } });
      P.toast('Permohonan ditolak.', 'info'); P.refreshCounters().then(P.render);
    });
  };

  /* -------------------------------------------------------------- pre-registration */
  P.route('/kpt/pradaftar', async () => {
    const cats = Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}">${P.esc(v)}</option>`).join('');
    const states = (P.state.config?.states || []).map(s => `<option>${P.esc(s)}</option>`).join('');
    const insts = await P.api('/kpt/institutions');
    P.layoutApp({
      title: 'Pra-Daftar Akaun IPT', subtitle: 'Pendaftaran dibenarkan KPT — pegawai IPT melengkapkan pengaktifan selamat',
      html: `<div class="grid-form"><div class="panel"><div class="paneltitle"><h3>Maklumat pra-daftar</h3></div>
      <form data-form="prereg" novalidate>
        <div class="section-title"><span class="step">1</span> Institusi</div>
        <div class="btn-group mb-3" role="group"><input type="radio" class="btn-check" name="pmode" id="pm-ex" value="existing" checked data-on="change:pre-mode"><label class="btn btn-outline-primary btn-sm" for="pm-ex">Pilih institusi sedia ada</label>
          <input type="radio" class="btn-check" name="pmode" id="pm-new" value="new" data-on="change:pre-mode"><label class="btn btn-outline-primary btn-sm" for="pm-new">Daftar institusi baharu</label></div>
        <div id="preEx"><label class="form-label" for="pInst">Institusi</label><select class="form-select" id="pInst" name="existing_institution_id"><option value="">— Pilih —</option>${insts.filter(i => i.status !== 'REJECTED').map(i => `<option value="${i.id}">${P.esc(i.code)} — ${P.esc(i.name)} (${i.active_users} akaun aktif)</option>`).join('')}</select></div>
        <div id="preNew" class="row g-3 d-none">
          <div class="col-md-8"><label class="form-label" for="pName">Nama rasmi IPT *</label><input class="form-control" id="pName" name="inst_name" maxlength="200"></div>
          <div class="col-md-4"><label class="form-label" for="pCode">Kod IPT *</label><input class="form-control" id="pCode" name="inst_code" maxlength="40"></div>
          <div class="col-md-6"><label class="form-label" for="pCat">Kategori IPT *</label><select class="form-select" id="pCat" name="inst_category"><option value="">— Pilih —</option>${cats}</select></div>
          <div class="col-md-6"><label class="form-label" for="pState">Negeri</label><select class="form-select" id="pState" name="inst_state"><option value="">— Pilih —</option>${states}</select></div>
        </div>
        <div class="section-title"><span class="step">2</span> Pegawai penyelaras IPT yang ditetapkan</div>
        <div class="row g-3">
          <div class="col-md-6"><label class="form-label" for="pPerson">Nama penyelaras IPT *</label><input class="form-control" id="pPerson" name="name" maxlength="150"></div>
          <div class="col-md-6"><label class="form-label" for="pEmail">Emel penyelaras IPT *</label><input class="form-control" id="pEmail" name="email" type="email" maxlength="200"></div>
          <div class="col-md-6"><label class="form-label" for="pPos">Jawatan *</label><input class="form-control" id="pPos" name="position" maxlength="150"></div>
          <div class="col-md-6"><label class="form-label" for="pDept">Bahagian / Jabatan *</label><input class="form-control" id="pDept" name="department" maxlength="150"></div>
          <div class="col-md-6"><label class="form-label" for="pPhone">Nombor telefon *</label><input class="form-control" id="pPhone" name="phone" type="tel" maxlength="40"></div>
        </div>
        <button class="btn btn-primary mt-4" type="submit">Pra-daftar & hantar jemputan</button>
      </form><div id="preOut" class="mt-3"></div></div>
      <div class="panel"><div class="paneltitle"><h3>Aliran kerja</h3></div><ol class="small mb-0" style="line-height:1.9">
        <li>Penyelaras KPT memilih/mendaftar institusi.</li><li>Memasukkan maklumat pegawai yang ditetapkan.</li><li>Sistem menyemak pendua (emel, kod & nama institusi).</li>
        <li>Rekod jemputan dibenarkan KPT dicipta.</li><li>Pautan pengaktifan sekali guna dan bertempoh (${P.esc(String(P.state.config?.invitation_hours || 72))} jam) dijana.</li>
        <li>Pegawai IPT menerima arahan pengaktifan melalui emel.</li><li>Pegawai mengesahkan maklumat dan menetapkan kata laluan.</li><li>Akaun menjadi aktif — tiada kelulusan kedua diperlukan.</li></ol>
        <div class="callout info small mt-3 mb-0">Kata laluan tidak pernah dijana atau dihantar melalui emel.</div></div></div>`
    });
  }, { perm: 'accounts.preregister' });
  P.inputs['pre-mode'] = el => { const ex = el.value === 'existing'; P.$('#preEx').classList.toggle('d-none', !ex); P.$('#preNew').classList.toggle('d-none', ex); };
  P.forms.prereg = async form => {
    const d = P.formData(form); const ex = d.pmode === 'existing';
    const body = { existing_institution_id: ex ? (+d.existing_institution_id || null) : null, inst_name: ex ? '' : d.inst_name, inst_code: ex ? '' : d.inst_code,
      inst_category: ex ? '' : d.inst_category, inst_state: ex ? '' : d.inst_state, name: d.name, email: d.email, position: d.position, department: d.department, phone: d.phone };
    if (ex && !body.existing_institution_id) { P.toast('Pilih institusi.', 'warning'); return; }
    const r = await P.api('/kpt/preregister', { method: 'POST', body });
    P.$('#preOut').innerHTML = `<div class="callout ok"><b>${P.esc(r.message)}</b><br>Pautan sah sehingga ${P.date(r.expires_at)}.</div>
      ${r.dev_activation_link ? `<div class="callout warn"><span class="devbadge">PRATONTON PEMBANGUNAN</span> SMTP belum dikonfigurasi, jadi emel <b>tidak</b> dihantar sebenar. Untuk ujian sahaja, pautan pengaktifan:<br><code class="user-select-all">${P.esc(r.dev_activation_link)}</code></div>` : ''}`;
    form.reset(); P.inputs['pre-mode']({ value: 'existing' });
  };

  /* -------------------------------------------------------------- IPT accounts & activation status */
  P.route('/kpt/akaun', async (_, q) => {
    const rows = await P.api('/kpt/accounts?' + qs({ status: q.status || '', q: q.q || '' }));
    const insts = P.can('accounts.manage') ? await P.api('/kpt/institutions') : [];
    P.state._insts = insts;
    const title = q.status === 'invited' ? 'Status Pengaktifan Akaun' : 'Senarai Akaun IPT';
    P.layoutApp({
      title, subtitle: 'Urus akaun Penyelaras IPT, tugasan institusi dan jemputan pengaktifan',
      html: P.heading(title, `${rows.length} akaun`, `<form class="filters" data-form="acc-filter"><input class="form-control" name="q" placeholder="Cari nama / emel" value="${P.esc(q.q || '')}" aria-label="Carian">
        <select class="form-select" name="status" aria-label="Status"><option value="">Semua status</option>${['active', 'invited', 'pending', 'inactive', 'rejected'].map(s => `<option value="${s}" ${q.status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}</select><button class="btn btn-primary">Tapis</button></form>`) + `
      <div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>Nama</th><th>Emel</th><th>Institusi</th><th>Status</th><th>Jemputan pengaktifan</th><th>Log masuk terakhir</th><th>Tindakan</th></tr></thead><tbody>
      ${rows.length ? rows.map(a => `<tr><td><b>${P.esc(a.name)}</b><div class="meta">${P.esc(a.position || '')}</div></td><td>${P.esc(a.email)}</td><td>${a.institution ? P.esc(a.institution.code + ' — ' + a.institution.name) : '—'}</td>
        <td>${P.badge(a.status)}</td><td>${a.invitation ? `${P.esc(a.invitation.state)}<div class="meta">${a.invitation.used_at ? 'Diaktifkan ' + P.date(a.invitation.used_at) : 'Tamat ' + P.date(a.invitation.expires_at)}</div>` : '<span class="meta">Pendaftaran sendiri</span>'}</td>
        <td>${P.date(a.last_login_at)}</td><td class="text-nowrap">
          ${a.status === 'invited' ? `<button class="btn btn-sm btn-soft" data-act="acc-reissue" data-id="${a.id}">Hantar semula jemputan</button>` : ''}
          ${['active', 'invited'].includes(a.status) ? `<button class="btn btn-sm btn-outline-danger" data-act="acc-deactivate" data-id="${a.id}">Nyahaktif</button>` : ''}
          ${a.status === 'inactive' ? `<button class="btn btn-sm btn-outline-primary" data-act="acc-reactivate" data-id="${a.id}">Aktif semula</button>` : ''}
          ${['active', 'invited', 'inactive'].includes(a.status) ? `<button class="btn btn-sm btn-light" data-act="acc-reassign" data-id="${a.id}">Tukar institusi</button>` : ''}</td></tr>`).join('')
        : `<tr><td colspan="7">${P.emptyState('Tiada akaun.')}</td></tr>`}</tbody></table></div></div>`
    });
  }, { perm: 'accounts.manage' });
  P.forms['acc-filter'] = form => { const d = P.formData(form); P.go('/kpt/akaun?' + qs(d)); };
  P.actions['acc-reissue'] = async el => {
    const r = await P.api(`/kpt/accounts/${el.dataset.id}/reissue`, { method: 'POST' });
    P.toast(r.message);
    if (r.dev_activation_link) P.modal({ title: 'Pautan pengaktifan (pratonton pembangunan)', body: `<p><span class="devbadge">PEMBANGUNAN</span> SMTP belum dikonfigurasi. Emel tidak dihantar sebenar.</p><code class="user-select-all">${P.esc(r.dev_activation_link)}</code>` });
    P.render();
  };
  P.actions['acc-deactivate'] = async el => {
    const reason = await P.ask({ title: 'Nyahaktif akaun', label: 'Sebab penyahaktifan', ok: 'Nyahaktif', okClass: 'btn-danger' });
    if (reason === null) return;
    await P.api(`/kpt/accounts/${el.dataset.id}/deactivate`, { method: 'POST', body: { reason } }); P.toast('Akaun dinyahaktifkan.'); P.render();
  };
  P.actions['acc-reactivate'] = async el => {
    const reason = await P.ask({ title: 'Aktifkan semula akaun', label: 'Catatan', required: false });
    if (reason === null) return;
    await P.api(`/kpt/accounts/${el.dataset.id}/reactivate`, { method: 'POST', body: { reason } }); P.toast('Akaun diaktifkan semula.'); P.render();
  };
  P.actions['acc-reassign'] = async el => {
    const insts = P.state._insts || [];
    const m = P.modal({
      title: 'Tukar institusi akaun', body: `<label class="form-label" for="raInst">Institusi baharu</label><select class="form-select mb-3" id="raInst">${insts.map(i => `<option value="${i.id}">${P.esc(i.code)} — ${P.esc(i.name)}</option>`).join('')}</select>
      <label class="form-label" for="raReason">Sebab *</label><textarea class="form-control" id="raReason" rows="3"></textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="raOk">Simpan</button>`
    });
    P.$('#raOk', m.el).addEventListener('click', async () => {
      try { await P.api(`/kpt/accounts/${el.dataset.id}/institution`, { method: 'POST', body: { institution_id: +P.$('#raInst', m.el).value, reason: P.$('#raReason', m.el).value } }); m.close(); P.toast('Institusi akaun dikemas kini.'); P.render(); }
      catch (e) { P.err(e); }
    });
  };

  /* -------------------------------------------------------------- approval history */
  const ACTION_LABEL = { SUBMITTED: 'Permohonan dihantar', APPROVED: 'Diluluskan', REJECTED: 'Ditolak', PRE_REGISTERED: 'Pra-daftar KPT', ACTIVATED: 'Diaktifkan oleh pegawai',
    DEACTIVATED: 'Dinyahaktifkan', REACTIVATED: 'Diaktifkan semula', INVITATION_REISSUED: 'Jemputan dihantar semula', INSTITUTION_CHANGED: 'Institusi ditukar',
    STAFF_INVITED: 'Staf KPT dijemput', USER_UPDATED: 'Pengguna dikemas kini', BOOTSTRAP_ADMIN: 'Pentadbir pertama', STAFF_CREATED_CLI: 'Staf dicipta (CLI)' };
  P.route('/kpt/sejarah', async () => {
    const rows = await P.api('/kpt/history');
    P.layoutApp({
      title: 'Sejarah Kelulusan', subtitle: 'Rekod keputusan akaun yang tidak boleh diubah',
      html: `<div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>Tarikh</th><th>Tindakan</th><th>Pegawai</th><th>Pengguna</th><th>Institusi</th><th>No. Permohonan</th><th>Sebab / catatan</th></tr></thead><tbody>
      ${rows.length ? rows.map(h => `<tr><td class="text-nowrap">${P.date(h.at)}</td><td>${P.badge(h.action.includes('REJECT') || h.action === 'DEACTIVATED' ? 'REJECTED' : h.action.includes('APPROV') || h.action === 'ACTIVATED' ? 'APPROVED' : 'DRAFT', ACTION_LABEL[h.action] || h.action)}</td>
        <td>${P.esc(h.actor)}</td><td>${P.esc(h.user || '—')}</td><td>${P.esc(h.institution || '—')}</td><td>${P.esc(h.ref_no || '—')}</td><td>${P.esc(h.reason || '')}</td></tr>`).join('')
        : `<tr><td colspan="7">${P.emptyState('Belum ada sejarah.')}</td></tr>`}</tbody></table></div></div>`
    });
  }, { perm: 'accounts.review' });

  /* -------------------------------------------------------------- institution directory */
  P.route('/kpt/institusi', async () => {
    const rows = await P.api('/kpt/institutions');
    const admin = P.can('admin.institutions');
    P.layoutApp({
      title: 'Direktori Institusi', subtitle: 'Institusi berdaftar dalam PSKG Monitor 2030',
      html: `<div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>Kod</th><th>Nama IPT</th><th>Kategori</th><th>Negeri</th><th>Status</th><th class="num">Akaun aktif</th><th>Sumber</th>${admin ? '<th></th>' : ''}</tr></thead><tbody>
      ${rows.length ? rows.map(i => `<tr><td><b>${P.esc(i.code)}</b></td><td>${P.esc(i.name)} ${i.is_demo ? '<span class="devbadge">DEMO</span>' : ''}</td><td>${P.esc(i.category_label)}</td><td>${P.esc(i.state || '—')}</td><td>${P.badge(i.status)}</td><td class="num">${i.active_users}</td><td class="meta">${P.esc(i.created_via || '')}</td>
        ${admin ? `<td><button class="btn btn-sm btn-soft" data-act="inst-edit" data-id="${i.id}" data-cat="${P.esc(i.category || '')}" data-status="${P.esc(i.status)}" data-name="${P.esc(i.name)}" data-state="${P.esc(i.state || '')}">Kemaskini</button></td>` : ''}</tr>`).join('')
        : `<tr><td colspan="8">${P.emptyState('Tiada institusi.')}</td></tr>`}</tbody></table></div>
      <p class="meta mt-2 mb-0">Rujukan populasi rasmi (slaid 38): 20 Universiti Awam, 357 IPTS, 36 Politeknik, 106 Kolej Komuniti.</p></div>`
    });
  }, { perm: 'accounts.manage|monitoring.view' });
  P.actions['inst-edit'] = async el => {
    const cats = Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}" ${el.dataset.cat === k ? 'selected' : ''}>${P.esc(v)}</option>`).join('');
    const states = (P.state.config?.states || []).map(s => `<option ${el.dataset.state === s ? 'selected' : ''}>${P.esc(s)}</option>`).join('');
    const m = P.modal({
      title: 'Kemaskini institusi', body: `<label class="form-label" for="ieName">Nama</label><input class="form-control mb-2" id="ieName" value="${P.esc(el.dataset.name)}">
      <label class="form-label" for="ieCat">Kategori</label><select class="form-select mb-2" id="ieCat"><option value="">—</option>${cats}</select>
      <label class="form-label" for="ieState">Negeri</label><select class="form-select mb-2" id="ieState"><option value="">—</option>${states}</select>
      <label class="form-label" for="ieStatus">Status</label><select class="form-select mb-2" id="ieStatus">${['ACTIVE', 'INACTIVE'].map(s => `<option value="${s}" ${el.dataset.status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}</select>
      <label class="form-label" for="ieReason">Sebab perubahan *</label><textarea class="form-control" id="ieReason" rows="2"></textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="ieOk">Simpan</button>`
    });
    P.$('#ieOk', m.el).addEventListener('click', async () => {
      const body = { name: P.$('#ieName', m.el).value, state: P.$('#ieState', m.el).value, status: P.$('#ieStatus', m.el).value, reason: P.$('#ieReason', m.el).value };
      const cat = P.$('#ieCat', m.el).value; if (cat) body.category = cat;
      try { await P.api('/admin/institutions/' + el.dataset.id, { method: 'PATCH', body }); m.close(); P.toast('Institusi dikemas kini.'); P.render(); } catch (e) { P.err(e); }
    });
  };

  /* -------------------------------------------------------------- reporting-status matrix */
  P.route('/kpt/status', async (_, q) => {
    const y = +(q.tahun || P.state.year);
    const f = { year: y, teras: q.teras || '', category: q.kategori || '', institution_id: q.ipt || '', status: q.status || '' };
    const [m, insts] = await Promise.all([P.api('/monitoring/matrix?' + qs(f)), P.api('/kpt/institutions')]);
    const SHORT = { VERIFIED: '✓', SUBMITTED: 'S', RETURNED: 'P', DRAFT: 'D', NOT_STARTED: '—', NOT_APPLICABLE: 'n/a' };
    P.layoutApp({
      title: 'Status Pelaporan IPT', subtitle: 'Matriks kelengkapan pelaporan: institusi × KPI',
      html: P.heading('Matriks status pelaporan', `Tahun ${y} · ${m.rows.length} institusi · ${m.kpis.length} KPI`, `
        <form class="filters" data-form="matrix-filter">
          <select class="form-select" name="tahun" aria-label="Tahun">${P.yearOptions(y)}</select>
          <select class="form-select" name="teras" aria-label="Teras">${terasOptions(f.teras)}</select>
          <select class="form-select" name="kategori" aria-label="Kategori">${catOptions(f.category)}</select>
          <select class="form-select" name="ipt" aria-label="Institusi"><option value="">Semua institusi</option>${insts.filter(i => i.status === 'ACTIVE').map(i => `<option value="${i.id}" ${+f.institution_id === i.id ? 'selected' : ''}>${P.esc(i.code)}</option>`).join('')}</select>
          <select class="form-select" name="status" aria-label="Status"><option value="">Semua status</option>${['NOT_STARTED', 'DRAFT', 'SUBMITTED', 'RETURNED', 'VERIFIED'].map(s => `<option value="${s}" ${f.status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}</select>
          <button class="btn btn-primary">Tapis</button></form>`) + `
      <div class="panel"><div class="legend mb-3">${Object.entries(SHORT).map(([k, v]) => `<span><span class="badge-s st-${k}">${v}</span> ${P.STATUS[k]}</span>`).join('')}
        <span class="ms-auto">Rekod tiada (—) <b>berbeza</b> daripada pencapaian sifar yang disahkan (✓ dengan nilai 0).</span></div>
      ${m.rows.length ? `<div class="tablewrap"><table class="datatable matrix"><thead><tr><th>Institusi</th><th class="num">Lengkap</th>${m.kpis.map(k => `<th title="${P.esc(k.title)}" class="text-center">${P.esc(k.code).replace(/\//g, '/<wbr>')}</th>`).join('')}</tr></thead><tbody>
      ${m.rows.map(r => `<tr><td><b>${P.esc(r.code)}</b><div class="meta">${P.esc(r.name)}</div></td><td class="num">${r.completion_pct === null ? '—' : P.fmt(r.completion_pct, 0) + '%'}<div class="meta">${r.verified} disahkan</div></td>
        ${m.kpis.map(k => { const c = r.cells[k.code]; const label = `${r.code} ${k.code}: ${P.STATUS[c.status]}${c.value !== null ? ' — ' + P.fmt(c.value) : ''}`;
          return `<td class="cell">${c.submission_id ? `<a class="sq st-${c.status}" href="#/kpt/semakan/${c.submission_id}" title="${P.esc(label)}" aria-label="${P.esc(label)}">${SHORT[c.status]}</a>` : `<span class="sq st-${c.status}" title="${P.esc(label)}" aria-label="${P.esc(label)}">${SHORT[c.status]}</span>`}</td>`; }).join('')}</tr>`).join('')}
      </tbody></table></div>` : P.emptyState('Tiada institusi aktif bagi tapisan ini.')}</div>`
    });
  }, { perm: 'monitoring.view' });
  P.forms['matrix-filter'] = form => { const d = P.formData(form); P.go('/kpt/status?' + qs(d)); };

  /* -------------------------------------------------------------- verification workspace */
  P.route('/kpt/semakan', async (_, q) => {
    const y = +(q.tahun || P.state.year); const status = q.status ?? 'SUBMITTED';
    const rows = await P.api('/submissions?' + qs({ year: y, status, teras: q.teras || '' }));
    P.layoutApp({
      title: 'Semakan & Pengesahan', subtitle: 'Rekod IPT mesti disahkan sebelum dimasukkan dalam agregat rasmi',
      html: P.heading('Semakan & Pengesahan KPT', `${rows.length} rekod`, `<form class="filters" data-form="rev-filter">
        <select class="form-select" name="tahun" aria-label="Tahun">${P.yearOptions(y)}</select><select class="form-select" name="teras" aria-label="Teras">${terasOptions(q.teras || '')}</select>
        <select class="form-select" name="status" aria-label="Status"><option value="">Semua status</option>${['SUBMITTED', 'RETURNED', 'VERIFIED', 'DRAFT'].map(s => `<option value="${s}" ${status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}</select>
        <button class="btn btn-primary">Tapis</button></form>`) + `
      ${!P.can('submissions.verify') ? '<div class="callout warn">Akaun anda tidak diberi kuasa pengesahan; paparan baca sahaja.</div>' : ''}
      <div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>IPT</th><th>KPI</th><th>Tahun</th><th class="num">Pembilang / Penyebut</th><th class="num">Pencapaian</th><th class="num">Sasaran</th><th>Status</th><th>Dihantar</th><th></th></tr></thead><tbody>
      ${rows.length ? rows.map(s => `<tr><td><b>${P.esc(s.institution.code)}</b><div class="meta">${P.esc(s.institution.name)}</div></td><td><b>${P.esc(s.kpi.code)}</b><div class="meta">${P.esc(s.kpi.title)}</div></td><td>${s.year}</td>
        <td class="num">${s.kpi.unit === 'percent' ? P.fmt(s.numerator, 0) + ' / ' + P.fmt(s.denominator, 0) : s.kpi.unit === 'count' ? P.fmt(s.numerator, 0) : 'Skor ' + P.fmt(s.index_score)}</td>
        <td class="num"><b>${s.kpi.unit === 'index' ? (s.index_excellent ? 'Cemerlang' : 'Belum cemerlang') : P.val(s.value, s.kpi.unit)}</b></td><td class="num">${P.targetText(s.target, s.kpi.unit)}</td><td>${P.badge(s.status, s.status_label)}<div class="meta">revisi ${s.revision}</div></td>
        <td>${P.date(s.submitted_at)}<div class="meta">${P.esc(s.submitted_by || '')}</div></td><td><a class="btn btn-sm btn-primary" href="#/kpt/semakan/${s.id}">${s.status === 'SUBMITTED' ? 'Semak' : 'Lihat'}</a></td></tr>`).join('')
        : `<tr><td colspan="9">${P.emptyState(status === 'SUBMITTED' ? 'Tiada laporan menunggu semakan. 🎉' : 'Tiada rekod.')}</td></tr>`}</tbody></table></div></div>`
    });
  }, { perm: 'submissions.view_all' });
  P.forms['rev-filter'] = form => { const d = P.formData(form); P.go('/kpt/semakan?' + qs(d) + (d.status === '' ? '&status=' : '')); };

  P.route('/kpt/semakan/:id', async ({ id }) => {
    const s = await P.api('/submissions/' + id);
    const k = s.kpi_full;
    const ev = s.evidence || [];
    P.layoutApp({
      title: 'Semakan Laporan ' + s.kpi.code, subtitle: `${P.esc(s.institution.name)} · Tahun ${s.year}`,
      html: `<nav aria-label="breadcrumb" class="mb-2"><ol class="breadcrumb small mb-0"><li class="breadcrumb-item"><a href="#/kpt/semakan">Semakan & Pengesahan</a></li><li class="breadcrumb-item active">${P.esc(s.kpi.code)} — ${P.esc(s.institution.code)}</li></ol></nav>
      <div class="grid-form"><div>
        <div class="panel"><div class="paneltitle"><h3>Butiran laporan</h3>${P.badge(s.status, s.status_label)}</div>
          <dl class="kv"><dt>Nama IPT</dt><dd>${P.esc(s.institution.name)} (${P.esc(s.institution.code)})</dd><dt>Kod KPI</dt><dd><b>${P.esc(s.kpi.code)}</b></dd><dt>Nama KPI</dt><dd>${P.esc(s.kpi.title)}</dd>
          <dt>Tahun pelaporan</dt><dd>${s.year}</dd>
          ${s.kpi.unit === 'percent' ? `<dt>Pembilang (A)</dt><dd>${P.fmt(s.numerator, 0)} <span class="meta">— ${P.esc(k.numerator_label)}</span></dd><dt>Penyebut (B)</dt><dd>${P.fmt(s.denominator, 0)} <span class="meta">— ${P.esc(k.denominator_label)}</span></dd>` : ''}
          ${s.kpi.unit === 'count' ? `<dt>Bilangan sebenar</dt><dd>${P.fmt(s.numerator, 0)}</dd>` : ''}
          ${s.kpi.unit === 'index' ? `<dt>Skor indeks</dt><dd>${P.fmt(s.index_score)} (${s.index_excellent ? 'Cemerlang' : 'Belum cemerlang'})</dd>` : ''}
          <dt>Nilai pencapaian</dt><dd class="fs-5 fw-bold text-success">${s.kpi.unit === 'index' ? P.fmt(s.index_score) : P.val(s.value, s.kpi.unit)}</dd>
          <dt>Sasaran ${s.year}</dt><dd>${P.targetText(s.target, s.kpi.unit)} <span class="meta">${P.esc(s.comparison.comparison || '')}</span></dd>
          <dt>Jurang sasaran</dt><dd>${s.comparison.gap === null ? '—' : `<b class="${s.comparison.achieved ? 'text-success' : 'text-danger'}">${(s.comparison.gap >= 0 ? '+' : '') + P.fmt(s.comparison.gap, 2)}${s.kpi.unit === 'percent' ? ' mata %' : ''}</b>`}</dd>
          <dt>Revisi</dt><dd>${s.revision} · dihantar ${P.date(s.submitted_at)} oleh ${P.esc(s.submitted_by || '—')}</dd></dl>
          ${s.items?.length ? `<div class="section-title">Senarai item dilaporkan</div><div class="tablewrap"><table class="datatable"><thead><tr>${(k.items_schema || []).map(f => `<th>${P.esc(f.label)}</th>`).join('')}</tr></thead><tbody>${s.items.map(it => `<tr>${(k.items_schema || []).map(f => `<td>${P.esc(it[f.key] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}
          ${k.attestations.length ? `<div class="section-title">Syarat kelayakan</div>${k.attestations.map((a, i) => `<div class="small">${s.attestations[i] ? '☑' : '☐'} ${P.esc(a)}</div>`).join('')}` : ''}
          <div class="section-title">Catatan IPT</div><div class="detail">${P.esc(s.note || '—')}</div>
        </div>
        <div class="panel"><div class="paneltitle"><h3>Dokumen sokongan (${ev.filter(e => !e.withdrawn).length})</h3></div>
          ${ev.length ? ev.map(e => `<div class="evid ${e.withdrawn ? 'withdrawn' : ''}"><span aria-hidden="true">📄</span><div class="nm"><b>${P.esc(e.name)}</b><div class="meta">${e.size < 1024 ? e.size + ' B' : P.fmt(e.size / 1024, 1) + ' KB'} · revisi ${e.revision} · SHA-256 ${P.esc(e.sha256.slice(0, 12))}… · ${P.date(e.uploaded_at)}</div></div>
            ${e.previewable && !e.withdrawn ? `<button class="btn btn-sm btn-soft" data-act="preview-evidence" data-id="${e.id}" data-name="${P.esc(e.name)}">Pratonton</button>` : ''}<a class="btn btn-sm btn-outline-primary" href="/api/evidence/${e.id}/download">Muat turun</a></div>`).join('') : P.emptyState('Tiada dokumen sokongan.', '📄')}
        </div>
        ${s.can_review ? `<div class="panel"><div class="paneltitle"><h3>Keputusan semakan</h3></div>
          <label class="form-label" for="revComment">Ulasan penyemak <span class="meta">(wajib jika dipulangkan)</span></label><textarea class="form-control mb-3" id="revComment" rows="3" maxlength="4000"></textarea>
          <div class="d-flex flex-wrap gap-2"><button class="btn btn-teal" data-act="review" data-id="${s.id}" data-decision="VERIFIED">✓ Sahkan Laporan</button>
          <button class="btn btn-outline-danger" data-act="review" data-id="${s.id}" data-decision="RETURNED">↩ Pulangkan untuk Pembetulan</button></div></div>` : ''}
        ${s.can_reopen ? `<div class="panel"><div class="paneltitle"><h3>Pentadbir: buka semula laporan disahkan</h3></div><p class="small text-muted">Laporan disahkan dikunci. Pembukaan semula memerlukan justifikasi dan direkod dalam log audit.</p><button class="btn btn-outline-danger btn-sm" data-act="reopen" data-id="${s.id}">Buka semula</button></div>` : ''}
      </div><div>
        <div class="panel"><div class="paneltitle"><h3>Takrif KPI</h3></div><div class="detail"><b>${P.esc(k.indicator)}</b><span class="formula">${P.esc(k.measurement)}</span><div class="meta">${P.esc(k.data_owner)}</div></div>
          ${k.confirmation_notes.length ? `<div class="callout warn mt-2 mb-0 small"><b>Perlu pengesahan KPT:</b><ul class="mb-0 ps-3">${k.confirmation_notes.map(n => `<li>${P.esc(n)}</li>`).join('')}</ul></div>` : ''}</div>
        <div class="panel"><div class="paneltitle"><h3>Sejarah pengesahan</h3></div>${s.verification_history.length ? s.verification_history.map(v => `<div class="hist"><div>${P.badge(v.decision)} <b>${P.esc(v.reviewer)}</b> · revisi ${v.revision} · nilai ${P.fmt(v.value)}</div>${v.comment ? `<div>${P.esc(v.comment)}</div>` : ''}<div class="when">${P.date(v.at)}</div></div>`).join('') : P.emptyState('Belum ada keputusan terdahulu.')}
          <button class="btn btn-sm btn-soft mt-2" data-act="rev-history">Sejarah penuh rekod</button></div>
      </div></div>`
    });
    P.state._rev = s;
  }, { perm: 'submissions.view_all' });
  P.actions['rev-history'] = () => P.showHistory(P.state._rev, P.state._rev.kpi.unit);
  P.actions.review = async el => {
    const decision = el.dataset.decision; const comment = P.$('#revComment').value.trim();
    if (decision === 'RETURNED' && comment.length < 5) { P.$('#revComment').classList.add('is-invalid'); P.toast('Ulasan wajib apabila memulangkan laporan.', 'warning'); return; }
    if (!await P.confirm({ title: decision === 'VERIFIED' ? 'Sahkan laporan ini?' : 'Pulangkan laporan untuk pembetulan?', body: decision === 'VERIFIED' ? 'Laporan yang disahkan akan dikunci dan dimasukkan dalam dashboard rasmi.' : 'IPT akan dimaklumkan dan boleh membetulkan serta menghantar semula.', ok: decision === 'VERIFIED' ? 'Sahkan Laporan' : 'Pulangkan', okClass: decision === 'VERIFIED' ? 'btn-teal' : 'btn-danger' })) return;
    await P.api(`/submissions/${el.dataset.id}/review`, { method: 'POST', body: { decision, comment } });
    P.toast(decision === 'VERIFIED' ? 'Laporan disahkan.' : 'Laporan dipulangkan untuk pembetulan.');
    await P.refreshCounters(); P.go('/kpt/semakan');
  };
  P.actions.reopen = async el => {
    const c = await P.ask({ title: 'Buka semula laporan disahkan', label: 'Justifikasi', minLen: 10, ok: 'Buka semula', okClass: 'btn-danger' });
    if (c === null) return;
    await P.api(`/submissions/${el.dataset.id}/reopen`, { method: 'POST', body: { comment: c } }); P.toast('Laporan dibuka semula dan dipulangkan kepada IPT.'); P.render();
  };

  /* -------------------------------------------------------------- dev e-mail preview */
  P.route('/kpt/emel', async () => {
    const d = await P.api('/kpt/outbox');
    P.layoutApp({
      title: 'Pratonton Emel', subtitle: 'Peti keluar emel sistem',
      html: `${d.smtp_enabled ? '<div class="callout ok">SMTP dikonfigurasi. Emel dihantar melalui pelayan SMTP.</div>' : '<div class="callout warn"><span class="devbadge">PEMBANGUNAN SAHAJA</span> SMTP belum dikonfigurasi. Emel di bawah <b>tidak dihantar</b> kepada penerima; ia hanya disimpan sebagai pratonton untuk ujian.</div>'}
      <div class="panel">${d.items.length ? d.items.map(e => `<details class="notif-item"><summary><b>${P.esc(e.subject)}</b> → ${P.esc(e.to)} · ${P.badge(e.status === 'SENT' ? 'APPROVED' : e.status === 'FAILED' ? 'REJECTED' : 'DRAFT', e.status)} <span class="meta">${P.date(e.created_at)}</span></summary><pre class="detail mt-2 mb-0" style="white-space:pre-wrap">${P.esc(e.body)}</pre></details>`).join('') : P.emptyState('Tiada emel.')}</div>`
    });
  }, { perm: 'notifications.outbox' });
})();
