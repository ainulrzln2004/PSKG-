/* Pentadbir KPT: users & roles, reporting periods, KPI definitions/targets, milestones, audit log, settings. */
'use strict';
(() => {
  const ROLE_LABEL = { ipt: 'Penyelaras IPT', kpt: 'Penyelaras KPT', admin: 'Pentadbir KPT', executive: 'Pengurusan Tertinggi' };

  /* -------------------------------------------------------------- users & roles */
  P.route('/admin/pengguna', async (_, q) => {
    const rows = await P.api('/admin/users?' + new URLSearchParams({ q: q.q || '', role: q.role || '' }));
    P.layoutApp({
      title: 'Pengguna & Peranan', subtitle: 'Urus akaun staf KPT dan peranan',
      html: `<div class="grid-form"><div class="panel"><div class="paneltitle"><h3>${rows.length} pengguna</h3>
        <form class="filters" data-form="usr-filter"><input class="form-control form-control-sm" name="q" value="${P.esc(q.q || '')}" placeholder="Cari" aria-label="Carian">
        <select class="form-select form-select-sm" name="role" aria-label="Peranan"><option value="">Semua peranan</option>${Object.entries(ROLE_LABEL).map(([k, v]) => `<option value="${k}" ${q.role === k ? 'selected' : ''}>${v}</option>`).join('')}</select><button class="btn btn-sm btn-primary">Tapis</button></form></div>
        <div class="tablewrap"><table class="datatable"><thead><tr><th>Nama</th><th>Peranan</th><th>Status</th><th>Boleh sahkan</th><th>Institusi</th><th>Log masuk terakhir</th><th></th></tr></thead><tbody>
        ${rows.map(u => `<tr><td><b>${P.esc(u.name)}</b><div class="meta">${P.esc(u.email)}</div></td><td>${P.esc(u.role_label)}</td><td>${P.badge(u.status)}</td><td>${u.role === 'kpt' || u.role === 'admin' ? (u.can_verify ? 'Ya' : 'Tidak') : '—'}</td>
          <td>${P.esc(u.institution || '—')}</td><td>${P.date(u.last_login_at)}</td><td>${u.role !== 'ipt' ? `<button class="btn btn-sm btn-soft" data-act="usr-edit" data-id="${u.id}" data-role="${u.role}" data-status="${u.status}" data-verify="${u.can_verify}">Ubah</button>` : '<a class="btn btn-sm btn-light" href="#/kpt/akaun">Urus</a>'}</td></tr>`).join('')}
        </tbody></table></div></div>
      <div class="panel"><div class="paneltitle"><h3>Jemput staf KPT</h3></div>
        <form data-form="staff-new" novalidate><div class="row g-2">
          <div class="col-12"><label class="form-label" for="sName">Nama penuh *</label><input class="form-control" id="sName" name="name" maxlength="150"></div>
          <div class="col-12"><label class="form-label" for="sEmail">Emel *</label><input class="form-control" id="sEmail" name="email" type="email" maxlength="200"></div>
          <div class="col-12"><label class="form-label" for="sRole">Peranan *</label><select class="form-select" id="sRole" name="role"><option value="kpt">Penyelaras KPT</option><option value="executive">Pengurusan Tertinggi (baca sahaja)</option><option value="admin">Pentadbir KPT</option></select></div>
          <div class="col-md-6"><label class="form-label" for="sPos">Jawatan</label><input class="form-control" id="sPos" name="position" maxlength="150"></div>
          <div class="col-md-6"><label class="form-label" for="sDept">Bahagian</label><input class="form-control" id="sDept" name="department" maxlength="150"></div>
          <div class="col-12 form-check ms-1"><input class="form-check-input" type="checkbox" id="sVerify" name="can_verify" checked><label class="form-check-label" for="sVerify">Dibenarkan mengesahkan laporan KPI</label></div>
        </div><button class="btn btn-primary mt-3" type="submit">Hantar jemputan</button></form><div id="staffOut" class="mt-2"></div>
        <div class="callout info small mt-3 mb-0">Akaun IPT dicipta melalui <a href="#/kpt/pradaftar">Pra-Daftar Akaun IPT</a> atau pendaftaran sendiri yang diluluskan.</div></div></div>`
    });
  }, { perm: 'admin.users' });
  P.forms['usr-filter'] = form => { const d = P.formData(form); P.go('/admin/pengguna?' + new URLSearchParams(d)); };
  P.forms['staff-new'] = async form => {
    const r = await P.api('/admin/users', { method: 'POST', body: P.formData(form) });
    P.$('#staffOut').innerHTML = `<div class="callout ok">${P.esc(r.message)}</div>${r.dev_activation_link ? `<div class="callout warn small"><span class="devbadge">PEMBANGUNAN</span> Emel tidak dihantar (SMTP belum dikonfigurasi). Pautan: <code class="user-select-all">${P.esc(r.dev_activation_link)}</code></div>` : ''}`;
    form.reset();
  };
  P.actions['usr-edit'] = el => {
    const m = P.modal({
      title: 'Ubah pengguna', body: `<label class="form-label" for="ueRole">Peranan</label><select class="form-select mb-2" id="ueRole">${['kpt', 'executive', 'admin'].map(r => `<option value="${r}" ${el.dataset.role === r ? 'selected' : ''}>${ROLE_LABEL[r]}</option>`).join('')}</select>
      <label class="form-label" for="ueStatus">Status</label><select class="form-select mb-2" id="ueStatus">${['active', 'inactive'].map(s => `<option value="${s}" ${el.dataset.status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}${el.dataset.status === 'invited' ? '<option value="invited" selected>Menunggu pengaktifan</option>' : ''}</select>
      <div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="ueVerify" ${el.dataset.verify === 'true' ? 'checked' : ''}><label class="form-check-label" for="ueVerify">Dibenarkan mengesahkan laporan</label></div>
      <label class="form-label" for="ueReason">Sebab perubahan *</label><textarea class="form-control" id="ueReason" rows="2"></textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="ueOk">Simpan</button>`
    });
    P.$('#ueOk', m.el).addEventListener('click', async () => {
      const st = P.$('#ueStatus', m.el).value;
      const body = { role: P.$('#ueRole', m.el).value, can_verify: P.$('#ueVerify', m.el).checked, reason: P.$('#ueReason', m.el).value };
      if (st !== 'invited') body.status = st;
      try { await P.api('/admin/users/' + el.dataset.id, { method: 'PATCH', body }); m.close(); P.toast('Pengguna dikemas kini.'); P.render(); } catch (e) { P.err(e); }
    });
  };

  /* -------------------------------------------------------------- reporting periods */
  P.route('/admin/tempoh', async () => {
    const rows = await P.api('/periods');
    P.layoutApp({
      title: 'Tempoh Pelaporan', subtitle: 'IPT hanya boleh menyimpan dan menghantar laporan bagi tahun yang DIBUKA',
      html: `<div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>Tahun</th><th>Status</th><th>Dibuka</th><th>Ditutup</th><th>Catatan</th><th></th></tr></thead><tbody>
      ${rows.map(p => `<tr><td><b>${p.year}</b></td><td>${P.badge(p.status === 'OPEN' ? 'VERIFIED' : p.status === 'CLOSED' ? 'RETURNED' : 'NOT_STARTED', P.STATUS[p.status])}</td><td>${P.esc(p.opens_on || '—')}</td><td>${P.esc(p.closes_on || '—')}</td><td>${P.esc(p.note || '')}</td>
        <td><button class="btn btn-sm btn-soft" data-act="period-edit" data-year="${p.year}" data-status="${p.status}" data-open="${P.esc(p.opens_on || '')}" data-close="${P.esc(p.closes_on || '')}" data-note="${P.esc(p.note || '')}">Ubah</button></td></tr>`).join('')}</tbody></table></div></div>`
    });
  }, { perm: 'admin.periods' });
  P.actions['period-edit'] = el => {
    const m = P.modal({
      title: 'Tempoh pelaporan ' + el.dataset.year, body: `<label class="form-label" for="peS">Status</label><select class="form-select mb-2" id="peS">${['PLANNED', 'OPEN', 'CLOSED'].map(s => `<option value="${s}" ${el.dataset.status === s ? 'selected' : ''}>${P.STATUS[s]}</option>`).join('')}</select>
      <div class="row g-2"><div class="col"><label class="form-label" for="peO">Tarikh buka</label><input type="date" class="form-control" id="peO" value="${el.dataset.open}"></div><div class="col"><label class="form-label" for="peC">Tarikh tutup</label><input type="date" class="form-control" id="peC" value="${el.dataset.close}"></div></div>
      <label class="form-label mt-2" for="peN">Catatan</label><textarea class="form-control" id="peN" rows="2">${el.dataset.note}</textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="peOk">Simpan</button>`
    });
    P.$('#peOk', m.el).addEventListener('click', async () => {
      try { await P.api('/admin/periods/' + el.dataset.year, { method: 'PUT', body: { status: P.$('#peS', m.el).value, opens_on: P.$('#peO', m.el).value || null, closes_on: P.$('#peC', m.el).value || null, note: P.$('#peN', m.el).value } }); m.close(); P.toast('Tempoh dikemas kini.'); P.render(); } catch (e) { P.err(e); }
    });
  };

  /* -------------------------------------------------------------- KPI definitions & targets */
  P.route('/admin/kpi', async () => {
    const [kpis, ms] = await Promise.all([P.api('/kpis'), P.api('/milestones')]);
    P.state.kpis = kpis;
    const years = ['2026', '2027', '2028', '2029', '2030'];
    P.layoutApp({
      title: 'KPI & Sasaran', subtitle: 'Kamus KPI rasmi (sumber: PSKG_final_KPI.pptx) — perubahan memerlukan justifikasi dan direkod dalam log audit',
      html: `<div class="callout warn">Sasaran dan takrif ditranskripsi daripada slaid 14, 18, 22, 26, 30 dan 33. Ubah hanya berdasarkan keputusan rasmi KPT. Semua formula kekal <b>DRAF</b> sehingga diperakukan.</div>
      <div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>Kod</th><th>KPI</th><th>Unit</th>${years.map(y => `<th class="num">${y}</th>`).join('')}<th>Formula</th><th></th></tr></thead><tbody>
      ${kpis.map(k => `<tr><td><b>${P.esc(k.code)}</b><div class="meta">T${k.teras} · ${P.esc(k.os_name)}</div></td><td>${P.esc(k.title)}<div class="meta">${P.esc(k.measurement)}</div></td><td>${P.UNIT[k.unit]}</td>
        ${years.map(y => `<td class="num"><button class="btn btn-sm btn-light" data-act="target-edit" data-kpi="${k.id}" data-year="${y}" title="Ubah sasaran ${y}">${k.targets[y].kind === 'milestone' ? P.fmt(k.targets[y].value) + '%*' : P.targetText(k.targets[y], k.unit)}</button></td>`).join('')}
        <td>${P.badge(k.formula_status === 'confirmed' ? 'VERIFIED' : 'DRAFT', k.formula_status === 'confirmed' ? 'Diperakukan' : 'Draf')}</td>
        <td><button class="btn btn-sm btn-soft" data-act="kpi-edit" data-kpi="${k.id}">Takrif</button></td></tr>`).join('')}</tbody></table></div>
        <div class="meta mt-2">* Milestone pembangunan Indeks Kepuasan Majikan.</div></div>
      <div class="panel"><div class="paneltitle"><h3>Milestone nasional — Indeks Kepuasan Majikan (T4/OS2/B)</h3></div>
        <p class="small text-muted">Tahun 2026–2027 ialah fasa pembangunan indeks. Kemajuan dicatat oleh KPT (bukan skor kepuasan majikan dan bukan dilaporkan oleh IPT).</p>
        <div class="row g-2">${kpis.filter(k => k.unit === 'index').flatMap(k => Object.entries(k.targets).filter(([, t]) => t.kind === 'milestone').map(([y, t]) => {
          const cur = ms.find(m => m.kpi_id === k.id && m.year === +y);
          return `<div class="col-md-6"><div class="detail"><b>${y}</b> — sasaran: ${P.esc(t.label)}<br>Kemajuan direkod: <b>${cur ? P.fmt(cur.progress_pct) + '%' : '—'}</b>${cur?.note ? `<div class="meta">${P.esc(cur.note)}</div>` : ''}
            <button class="btn btn-sm btn-soft mt-2" data-act="milestone-edit" data-kpi="${k.id}" data-year="${y}" data-val="${cur ? cur.progress_pct : ''}">Rekod kemajuan</button></div></div>`;
        })).join('')}</div></div>
      <div class="panel"><div class="paneltitle"><h3>Sasaran institusi (pilihan)</h3></div><p class="small text-muted mb-2">Sasaran nasional bagi KPI bilangan <b>tidak</b> dikenakan sebagai kuota yang sama kepada setiap IPT. Tetapkan sasaran institusi hanya jika KPT menetapkan peraturan peruntukan secara rasmi.</p>
        <button class="btn btn-sm btn-soft" data-act="inst-target">Tetapkan sasaran institusi</button></div>`
    });
  }, { perm: 'admin.kpis' });
  P.actions['target-edit'] = el => {
    const k = P.state.kpis.find(x => x.id === +el.dataset.kpi); const t = k.targets[el.dataset.year];
    const m = P.modal({
      title: `Sasaran ${P.esc(k.code)} — ${el.dataset.year}`, body: `<div class="row g-2"><div class="col-6"><label class="form-label" for="teV">Nilai</label><input class="form-control" type="number" step="any" min="0" id="teV" value="${t.value ?? ''}"></div>
      <div class="col-6"><label class="form-label" for="teK">Jenis</label><select class="form-select" id="teK"><option value="value" ${t.kind !== 'milestone' ? 'selected' : ''}>Nilai sasaran</option><option value="milestone" ${t.kind === 'milestone' ? 'selected' : ''}>Milestone</option></select></div>
      <div class="col-12"><label class="form-label" for="teL">Label (milestone)</label><input class="form-control" id="teL" value="${P.esc(t.label || '')}"></div>
      <div class="col-12"><label class="form-label" for="teR">Rujukan / justifikasi rasmi *</label><textarea class="form-control" id="teR" rows="2" placeholder="Contoh: Surat KPT ruj. ... bertarikh ..."></textarea></div></div>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="teOk">Simpan</button>`
    });
    P.$('#teOk', m.el).addEventListener('click', async () => {
      const v = P.$('#teV', m.el).value;
      try { await P.api(`/admin/kpis/${k.id}/targets`, { method: 'PUT', body: { year: +el.dataset.year, value: v === '' ? null : +v, kind: P.$('#teK', m.el).value, label: P.$('#teL', m.el).value || null, reason: P.$('#teR', m.el).value } }); m.close(); P.toast('Sasaran dikemas kini dan direkod dalam log audit.'); P.render(); } catch (e) { P.err(e); }
    });
  };
  P.actions['kpi-edit'] = el => {
    const k = P.state.kpis.find(x => x.id === +el.dataset.kpi);
    const m = P.modal({
      title: 'Takrif ' + P.esc(k.code), size: 'modal-lg', body: `<label class="form-label" for="keD">Takrif</label><textarea class="form-control mb-2" id="keD" rows="3">${P.esc(k.definition)}</textarea>
      <label class="form-label" for="keN">Label pembilang</label><input class="form-control mb-2" id="keN" value="${P.esc(k.numerator_label || '')}">
      ${k.unit === 'percent' ? `<label class="form-label" for="keDen">Label penyebut</label><input class="form-control mb-2" id="keDen" value="${P.esc(k.denominator_label || '')}">` : ''}
      <label class="form-label" for="keO">Pemilik data</label><input class="form-control mb-2" id="keO" value="${P.esc(k.data_owner || '')}">
      <label class="form-label" for="keS">Status formula</label><select class="form-select mb-2" id="keS"><option value="draft" ${k.formula_status !== 'confirmed' ? 'selected' : ''}>Draf</option><option value="confirmed" ${k.formula_status === 'confirmed' ? 'selected' : ''}>Diperakukan KPT</option></select>
      <label class="form-label" for="keR">Rujukan / justifikasi rasmi *</label><textarea class="form-control" id="keR" rows="2"></textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="keOk">Simpan</button>`
    });
    P.$('#keOk', m.el).addEventListener('click', async () => {
      const body = { definition: P.$('#keD', m.el).value, numerator_label: P.$('#keN', m.el).value, data_owner: P.$('#keO', m.el).value, formula_status: P.$('#keS', m.el).value, reason: P.$('#keR', m.el).value };
      if (P.$('#keDen', m.el)) body.denominator_label = P.$('#keDen', m.el).value;
      try { await P.api('/admin/kpis/' + k.id, { method: 'PATCH', body }); m.close(); P.toast('Takrif dikemas kini.'); P.render(); } catch (e) { P.err(e); }
    });
  };
  P.actions['milestone-edit'] = el => {
    const m = P.modal({
      title: 'Kemajuan pembangunan indeks ' + el.dataset.year, body: `<label class="form-label" for="miV">Kemajuan (%)</label><input class="form-control mb-2" type="number" min="0" max="100" step="1" id="miV" value="${el.dataset.val}">
      <label class="form-label" for="miN">Catatan / rujukan</label><textarea class="form-control" id="miN" rows="2"></textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="miOk">Simpan</button>`
    });
    P.$('#miOk', m.el).addEventListener('click', async () => {
      try { await P.api(`/admin/kpis/${el.dataset.kpi}/milestone`, { method: 'PUT', body: { year: +el.dataset.year, progress_pct: +P.$('#miV', m.el).value, note: P.$('#miN', m.el).value } }); m.close(); P.toast('Milestone direkod.'); P.render(); } catch (e) { P.err(e); }
    });
  };
  P.actions['inst-target'] = async () => {
    const insts = await P.api('/kpt/institutions');
    const m = P.modal({
      title: 'Sasaran institusi', body: `<label class="form-label" for="itI">Institusi</label><select class="form-select mb-2" id="itI">${insts.map(i => `<option value="${i.id}">${P.esc(i.code)} — ${P.esc(i.name)}</option>`).join('')}</select>
      <label class="form-label" for="itK">KPI</label><select class="form-select mb-2" id="itK">${P.state.kpis.map(k => `<option value="${k.id}">${P.esc(k.code)} — ${P.esc(k.title)}</option>`).join('')}</select>
      <div class="row g-2"><div class="col"><label class="form-label" for="itY">Tahun</label><select class="form-select" id="itY">${P.yearOptions(P.state.year)}</select></div><div class="col"><label class="form-label" for="itV">Nilai (kosongkan untuk padam)</label><input class="form-control" id="itV" type="number" min="0" step="any"></div></div>
      <label class="form-label mt-2" for="itR">Rujukan peruntukan KPT *</label><textarea class="form-control" id="itR" rows="2"></textarea>`,
      footer: `<button class="btn btn-light" data-bs-dismiss="modal">Batal</button><button class="btn btn-primary" id="itOk">Simpan</button>`
    });
    P.$('#itOk', m.el).addEventListener('click', async () => {
      const v = P.$('#itV', m.el).value;
      try { await P.api('/admin/institution-targets', { method: 'PUT', body: { institution_id: +P.$('#itI', m.el).value, kpi_id: +P.$('#itK', m.el).value, year: +P.$('#itY', m.el).value, value: v === '' ? null : +v, reason: P.$('#itR', m.el).value } }); m.close(); P.toast('Sasaran institusi disimpan.'); } catch (e) { P.err(e); }
    });
  };

  /* -------------------------------------------------------------- audit log */
  P.route('/admin/audit', async (_, q) => {
    const rows = await P.api('/admin/audit?' + new URLSearchParams({ q: q.q || '', event: q.event || '' }));
    P.layoutApp({
      title: 'Log Audit', subtitle: 'Rekod peristiwa keselamatan, akaun, laporan dan pentadbiran',
      html: P.heading('Log Audit', `${rows.length} peristiwa terkini`, `<form class="filters" data-form="audit-filter"><input class="form-control" name="q" value="${P.esc(q.q || '')}" placeholder="Cari rekod/butiran" aria-label="Carian"><input class="form-control" name="event" value="${P.esc(q.event || '')}" placeholder="Peristiwa (cth. login_failed)" aria-label="Peristiwa"><button class="btn btn-primary">Tapis</button></form>`) + `
      <div class="panel"><div class="tablewrap"><table class="datatable"><thead><tr><th>Masa</th><th>Pelaku</th><th>Peristiwa</th><th>Rekod</th><th>IP</th><th>Butiran</th></tr></thead><tbody>
      ${rows.map(a => `<tr><td class="text-nowrap">${P.date(a.at)}</td><td>${P.esc(a.actor)}</td><td><code>${P.esc(a.event)}</code></td><td>${P.esc(a.record)}</td><td class="meta">${P.esc(a.ip || '')}</td><td class="meta" style="max-width:380px;word-break:break-word">${P.esc(a.detail || '')}</td></tr>`).join('')}
      </tbody></table></div></div>`
    });
  }, { perm: 'admin.audit' });
  P.forms['audit-filter'] = form => P.go('/admin/audit?' + new URLSearchParams(P.formData(form)));

  /* -------------------------------------------------------------- settings */
  P.route('/admin/tetapan', async () => {
    const s = await P.api('/admin/settings');
    P.layoutApp({
      title: 'Tetapan Sistem', subtitle: 'Konfigurasi notis pilot dan dasar pelaporan',
      html: `<div class="panel" style="max-width:820px"><form data-form="settings" novalidate>
        <div class="form-check form-switch mb-2"><input class="form-check-input" type="checkbox" role="switch" id="stEn" name="pilot_notice_enabled" ${s.pilot_notice_enabled === 'true' ? 'checked' : ''}><label class="form-check-label" for="stEn">Paparkan notis persekitaran pilot</label></div>
        <label class="form-label" for="stN">Teks notis</label><textarea class="form-control mb-3" id="stN" name="pilot_notice" rows="4">${P.esc(s.pilot_notice)}</textarea>
        <div class="form-check form-switch mb-3"><input class="form-check-input" type="checkbox" role="switch" id="stEv" name="evidence_required_on_submit" ${s.evidence_required_on_submit === 'true' ? 'checked' : ''}><label class="form-check-label" for="stEv">Wajibkan sekurang-kurangnya satu dokumen sokongan sebelum laporan dihantar</label></div>
        <label class="form-label" for="stY">Tahun pelaporan lalai</label><select class="form-select mb-3" id="stY" name="default_reporting_year" style="max-width:160px">${P.yearOptions(+s.default_reporting_year)}</select>
        <button class="btn btn-primary" type="submit">Simpan tetapan</button></form>
        <hr><dl class="kv small"><dt>Persekitaran</dt><dd>${P.esc(s.environment)}</dd><dt>SMTP</dt><dd>${s.smtp_enabled ? 'Dikonfigurasi' : 'Tidak dikonfigurasi (pratonton emel pembangunan)'}</dd><dt>Had saiz fail</dt><dd>${s.max_upload_mb} MB</dd><dt>Tempoh jemputan</dt><dd>${s.invitation_hours} jam</dd></dl>
        <p class="meta mb-0">SMTP, saiz fail dan tempoh jemputan ditetapkan melalui pemboleh ubah persekitaran (.env).</p></div>`
    });
  }, { perm: 'admin.settings' });
  P.forms.settings = async form => {
    const d = P.formData(form);
    await P.api('/admin/settings', { method: 'PUT', body: { ...d, default_reporting_year: +d.default_reporting_year } });
    P.state.config = await P.api('/public/config'); P.toast('Tetapan disimpan.'); P.render();
  };
})();
