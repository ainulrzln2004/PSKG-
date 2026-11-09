/* Portal Pelaporan IPT: dashboard, Teras listing, dynamic KPI forms, evidence, verified records. */
'use strict';
(() => {
  const yearSel = (y, on = 'ipt-year') => `<label class="visually-hidden" for="yearSel">Tahun pelaporan</label><select id="yearSel" class="form-select" data-on="change:${on}">${P.yearOptions(y)}</select>`;
  P.inputs['ipt-year'] = el => { P.state.year = +el.value; P.render(); };

  /* -------------------------------------------------------------- dashboard */
  P.route('/ipt', async () => {
    const y = P.state.year;
    const d = await P.api('/ipt/overview?year=' + y);
    const c = d.counts;
    const card = (label, value, cls = '', hint = '') => `<div class="stat ${cls}"><div class="label">${label}</div><div class="value">${value}</div>${hint ? `<div class="hint">${hint}</div>` : ''}</div>`;
    const returned = d.teras.flatMap(t => t.kpis).filter(k => k.status === 'RETURNED');
    P.layoutApp({
      title: 'Dashboard IPT', subtitle: `${P.esc(d.institution.code)} — ${P.esc(d.institution.name)}`,
      html: P.heading(P.esc(d.institution.name), `Tahun pelaporan ${y} · ${d.period_open ? 'Tempoh pelaporan <b>DIBUKA</b>' : 'Tempoh pelaporan <b>tidak dibuka</b> (paparan sahaja)'}`, yearSel(y)) + `
      <div class="stats">
        ${card('Jumlah KPI', d.total_kpis, 'blue', `${d.applicable} berkenaan bagi institusi ini`)}
        ${card('KPI belum diisi', c.NOT_STARTED)}
        ${card('KPI dalam draf', c.DRAFT)}
        ${card('Menunggu semakan', c.SUBMITTED, 'amber')}
        ${card('Perlu pembetulan', c.RETURNED, 'red')}
        ${card('KPI disahkan', c.VERIFIED, 'teal')}
        ${card('Kelengkapan pelaporan', d.completion_pct === null ? '—' : P.fmt(d.completion_pct, 1) + '%', 'teal', 'Dihantar + disahkan ÷ KPI berkenaan')}
      </div>
      ${returned.length ? `<div class="callout danger"><b>${returned.length} laporan dipulangkan untuk pembetulan:</b> ${returned.map(k => `<a href="#/ipt/kpi/${k.id}">${P.esc(k.code)}</a>`).join(', ')}</div>` : ''}
      <div class="cards5">${d.teras.map(t => {
        const pct = t.applicable ? Math.round(100 * t.sent / t.applicable) : 0;
        return `<a class="tera" href="#/ipt/teras/${t.teras}"><small>TERAS ${t.teras}</small><b>${P.esc(t.name)}</b>
          <span class="count">${t.kpis.length}</span><span class="meta"> KPI</span>
          <div class="track mt-2" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="Kemajuan Teras ${t.teras}"><i style="width:${pct}%"></i></div>
          <div class="meta mt-1">${t.sent}/${t.applicable} dihantar · ${t.verified} disahkan${t.returned ? ` · <span class="text-danger">${t.returned} dipulangkan</span>` : ''}</div></a>`;
      }).join('')}</div>
      <div class="panel"><div class="paneltitle"><h3>Status 20 KPI — ${y}</h3><span class="meta">Klik KPI untuk membuka borang pelaporan</span></div>
      <div class="tablewrap"><table class="datatable"><thead><tr><th>Kod</th><th>KPI</th><th>Teras</th><th class="num">Sasaran ${y}</th><th class="num">Pencapaian</th><th>Status</th><th></th></tr></thead><tbody>
      ${d.teras.flatMap(t => t.kpis.map(k => `<tr><td><b>${P.esc(k.code)}</b></td><td>${P.esc(k.title)}${k.na_reason ? `<div class="meta">${P.esc(k.na_reason)}</div>` : ''}</td><td>T${t.teras}</td>
        <td class="num">${P.targetText(k.target, k.unit)}${k.unit === 'count' ? '<div class="meta">nasional</div>' : ''}</td><td class="num">${P.val(k.value, k.unit)}</td><td>${P.badge(k.status, k.status_label)}</td>
        <td><a class="btn btn-sm btn-soft" href="#/ipt/kpi/${k.id}">${k.status === 'RETURNED' ? 'Kemaskini' : k.status === 'NOT_APPLICABLE' ? 'Butiran' : 'Buka'} →</a></td></tr>`)).join('')}
      </tbody></table></div></div>`
    });
  }, { perm: 'ipt.report' });

  /* -------------------------------------------------------------- teras listing */
  P.route('/ipt/teras/:n', async ({ n }) => {
    const y = P.state.year; const t = +n;
    const d = await P.api('/ipt/overview?year=' + y);
    const card = d.teras.find(x => x.teras === t) || d.teras[0];
    P.layoutApp({
      title: 'Borang Pelaporan KPI', subtitle: `${P.esc(d.institution.name)} · Tahun ${y}`,
      html: P.heading(`Teras ${card.teras}: ${P.esc(card.name)}`, `${card.kpis.length} KPI · pilih KPI untuk mengisi borang`, yearSel(y)) + `
      <div class="cards5">${d.teras.map(x => `<a class="tera ${x.teras === card.teras ? 'active' : ''}" href="#/ipt/teras/${x.teras}"><small>TERAS ${x.teras}</small><b>${P.esc(x.name)}</b><span class="count">${x.kpis.length}</span><span class="meta"> KPI · ${x.sent}/${x.applicable} dihantar</span></a>`).join('')}</div>
      <div class="row g-3">${card.kpis.map(k => `<div class="col-md-6 col-xl-4"><div class="panel h-100 d-flex flex-column">
        <div class="d-flex justify-content-between align-items-start gap-2"><span class="smallcaps">${P.esc(k.code)}</span>${P.badge(k.status, k.status_label)}</div>
        <h3 class="h6 fw-bold mt-2 mb-1">${P.esc(k.title)}</h3><div class="meta mb-2">${P.UNIT[k.unit]} · Sasaran ${y}: <b>${P.targetText(k.target, k.unit)}</b>${k.unit === 'count' ? ' (nasional)' : ''}</div>
        ${k.na_reason ? `<div class="callout warn small">${P.esc(k.na_reason)}</div>` : `<div class="mb-2">Pencapaian: <b>${P.val(k.value, k.unit)}</b></div>`}
        <a class="btn btn-sm ${k.status === 'RETURNED' ? 'btn-danger' : 'btn-primary'} mt-auto" href="#/ipt/kpi/${k.id}">${k.status === 'RETURNED' ? 'Kemaskini / Hantar Semula' : k.status === 'NOT_STARTED' ? 'Isi borang' : 'Buka borang'}</a></div></div>`).join('')}</div>`
    });
  }, { perm: 'ipt.report' });

  /* -------------------------------------------------------------- dynamic KPI form */
  let F = null; // current form context
  P.route('/ipt/kpi/:id', async ({ id }, q) => {
    if (q.tahun) P.state.year = +q.tahun;
    const y = P.state.year;
    F = await P.api(`/ipt/form/${id}?year=${y}`);
    renderForm();
  }, { perm: 'ipt.report' });

  function inputsHtml(k, s, editable) {
    const dis = editable ? '' : 'disabled';
    if (k.unit === 'percent') {
      return `<div class="row g-3">
        <div class="col-md-6"><label class="form-label" for="numerator">Pembilang (A)</label><input class="form-control" id="numerator" name="numerator" type="number" min="0" step="1" inputmode="numeric" value="${s?.numerator ?? ''}" ${dis} data-on="input:calc"><div class="form-text">${P.esc(k.numerator_label)}</div></div>
        <div class="col-md-6"><label class="form-label" for="denominator">Penyebut (B)</label><input class="form-control" id="denominator" name="denominator" type="number" min="1" step="1" inputmode="numeric" value="${s?.denominator ?? ''}" ${dis} data-on="input:calc"><div class="form-text">${P.esc(k.denominator_label)}</div></div></div>
        <div class="detail mt-3 d-flex flex-wrap justify-content-between align-items-center gap-2"><div><div class="smallcaps">Pencapaian (%) = (A ÷ B) × 100</div><div class="calc" id="calcOut">${P.val(s?.value, 'percent')}</div></div><div id="gapOut" class="text-end"></div></div>`;
    }
    if (k.unit === 'count' && k.itemised) {
      const schema = k.items_schema || []; const items = (s?.items?.length ? s.items : []);
      return `<label class="form-label">Senarai item (setiap item dengan rujukan unik)</label>
        <div class="form-text mb-2">Bilangan sebenar dikira automatik daripada senarai. Rujukan unik membolehkan pendua antara IPT dikecualikan dalam agregat nasional. Isi 0 jika tiada.</div>
        <div class="tablewrap"><table class="datatable" id="itemsTbl"><thead><tr>${schema.map(f => `<th>${P.esc(f.label)}${f.required ? ' *' : ''}</th>`).join('')}<th></th></tr></thead>
        <tbody>${items.map(it => itemRow(schema, it, dis)).join('')}</tbody></table></div>
        ${editable ? '<button class="btn btn-sm btn-soft mt-2" type="button" data-act="add-item">+ Tambah item</button>' : ''}
        <div class="row g-3 mt-1"><div class="col-md-6"><label class="form-label" for="numerator">Bilangan sebenar</label><input class="form-control" id="numerator" name="numerator" type="number" min="0" step="1" value="${s?.numerator ?? ''}" ${dis} data-on="input:calc"><div class="form-text">Diisi automatik apabila item disenaraikan; isi 0 jika tiada pencapaian.</div></div>
        <div class="col-md-6"><div class="detail h-100"><div class="smallcaps">Bilangan dilaporkan</div><div class="calc" id="calcOut">${P.val(s?.value, 'count')}</div></div></div></div>`;
    }
    if (k.unit === 'count') {
      return `<div class="row g-3"><div class="col-md-6"><label class="form-label" for="numerator">Bilangan sebenar</label><input class="form-control" id="numerator" name="numerator" type="number" min="0" step="1" inputmode="numeric" value="${s?.numerator ?? ''}" ${dis} data-on="input:calc"><div class="form-text">${P.esc(k.numerator_label)}. Nombor bulat ≥ 0.</div></div>
        <div class="col-md-6"><div class="detail h-100"><div class="smallcaps">Bilangan dilaporkan</div><div class="calc" id="calcOut">${P.val(s?.value, 'count')}</div><div id="gapOut"></div></div></div></div>`;
    }
    // index (KPI 17)
    const sc = k.index_scale || [1, 5];
    return `<div class="callout info">Ukuran khas: <b>${P.esc(k.indicator)}</b>. IPT melaporkan skor Indeks Kepuasan Majikan institusi (skala ${sc[0]}–${sc[1]}).
      ${k.excellence_threshold !== null && k.excellence_threshold !== undefined ? `Skor ≥ ${k.excellence_threshold} dikira <b>cemerlang</b> (slaid 33: skor 4–5) — ambang menunggu pengesahan KPT.` : ''}
      Agregat nasional = % IPTA yang mencapai skor cemerlang.</div>
      <div class="row g-3"><div class="col-md-6"><label class="form-label" for="index_score">Skor indeks institusi</label><input class="form-control" id="index_score" name="index_score" type="number" min="${sc[0]}" max="${sc[1]}" step="0.01" value="${s?.index_score ?? ''}" ${dis} data-on="input:calc"></div>
      <div class="col-md-6"><div class="detail h-100"><div class="smallcaps">Kategori skor</div><div class="calc" id="calcOut">${s?.index_excellent === true ? 'Cemerlang' : s?.index_excellent === false ? 'Belum cemerlang' : '—'}</div></div></div></div>`;
  }
  function itemRow(schema, it = {}, dis = '') {
    return `<tr>${schema.map(f => `<td><input class="form-control form-control-sm" data-item="${f.key}" value="${P.esc(it[f.key] || '')}" maxlength="300" ${dis} aria-label="${P.esc(f.label)}" ${f.key === 'date' ? 'type="date"' : ''}></td>`).join('')}
      <td>${dis ? '' : '<button class="btn btn-sm btn-outline-danger" type="button" data-act="del-item" aria-label="Buang item">✕</button>'}</td></tr>`;
  }
  P.actions['add-item'] = () => { P.$('#itemsTbl tbody').insertAdjacentHTML('beforeend', itemRow(F.kpi.items_schema)); P.inputs.calc(); };
  P.actions['del-item'] = el => { el.closest('tr').remove(); P.inputs.calc(); };
  P.inputs.calc = () => {
    const k = F.kpi; const out = P.$('#calcOut'); if (!out) return;
    const t = k.targets[String(F.year)];
    if (k.unit === 'percent') {
      const a = P.$('#numerator').value, b = P.$('#denominator').value;
      const ok = a !== '' && b !== '' && +b > 0;
      out.textContent = ok ? P.fmt(100 * a / b, 2) + '%' : '—';
      const g = P.$('#gapOut');
      if (g) g.innerHTML = ok && t.value !== null && t.kind !== 'milestone' ? `<div class="smallcaps">Jurang vs sasaran ${P.fmt(t.value)}%</div><b class="${100 * a / b >= t.value ? 'text-success' : 'text-danger'}">${(100 * a / b - t.value >= 0 ? '+' : '') + P.fmt(100 * a / b - t.value, 2)} mata %</b><div class="meta">Pratonton; nilai rasmi dikira pelayan.</div>` : '';
      if (ok && +a > +b && k.subset_ratio) out.innerHTML += ' <span class="badge text-bg-danger">A > B</span>';
    } else if (k.unit === 'count') {
      const rows = P.$$('#itemsTbl tbody tr').filter(tr => P.$$('input', tr).some(i => i.value.trim()));
      if (k.itemised && rows.length) P.$('#numerator').value = rows.length;
      const v = P.$('#numerator').value; out.textContent = v === '' ? '—' : P.fmt(v, 0);
    } else {
      const v = P.$('#index_score').value; const thr = k.excellence_threshold;
      out.textContent = v === '' ? '—' : (thr !== null && thr !== undefined ? (+v >= thr ? 'Cemerlang' : 'Belum cemerlang') : P.fmt(v));
    }
  };

  function collect() {
    const k = F.kpi; const body = { kpi_id: k.id, year: F.year, note: P.$('#note')?.value || '' };
    if (k.unit === 'percent') { body.numerator = P.$('#numerator').value; body.denominator = P.$('#denominator').value; }
    else if (k.unit === 'count') {
      body.numerator = P.$('#numerator').value;
      if (k.itemised) body.items = P.$$('#itemsTbl tbody tr').map(tr => Object.fromEntries(P.$$('input', tr).map(i => [i.dataset.item, i.value])));
    } else body.index_score = P.$('#index_score').value;
    body.attestations = P.$$('[data-attest]').map(c => c.checked);
    Object.keys(body).forEach(key => { if (body[key] === '' && key !== 'note') body[key] = null; });
    return body;
  }

  function renderForm() {
    const { kpi: k, submission: s, institution: inst, year: y, editable } = F;
    const t = k.targets[String(y)];
    const status = s ? s.status : (F.applicable ? 'NOT_STARTED' : 'NOT_APPLICABLE');
    const ev = (s?.evidence || []);
    const activeEv = ev.filter(e => !e.withdrawn);
    const returned = s?.status === 'RETURNED';
    P.layoutApp({
      title: `${k.code} — ${k.title}`, subtitle: `${P.esc(inst.code)} — ${P.esc(inst.name)} · Tahun pelaporan ${y}`,
      html: `<nav aria-label="breadcrumb" class="mb-2"><ol class="breadcrumb small mb-0"><li class="breadcrumb-item"><a href="#/ipt">Dashboard IPT</a></li><li class="breadcrumb-item"><a href="#/ipt/teras/${k.teras}">Teras ${k.teras}</a></li><li class="breadcrumb-item active" aria-current="page">${P.esc(k.code)}</li></ol></nav>
      ${returned ? `<div class="callout danger"><b>Dipulangkan untuk pembetulan oleh KPT${s.reviewed_by ? ' (' + P.esc(s.reviewed_by) + ')' : ''}:</b><br>${P.esc(s.review_note)}</div>` : ''}
      ${!F.applicable ? `<div class="callout warn"><b>Tidak berkenaan:</b> ${P.esc(F.na_reason)}</div>` : ''}
      ${F.applicable && !F.period_open ? `<div class="callout warn">Tempoh pelaporan ${y} tidak dibuka. Borang dipaparkan dalam mod baca sahaja.</div>` : ''}
      ${s?.status === 'SUBMITTED' ? `<div class="callout info">Laporan telah dihantar (revisi ${s.revision}) dan dilindungi daripada pengubahsuaian sehingga disemak oleh KPT.</div>` : ''}
      ${s?.status === 'VERIFIED' ? `<div class="callout ok">Laporan telah <b>disahkan</b> oleh KPT${s.reviewed_by ? ' (' + P.esc(s.reviewed_by) + ', ' + P.date(s.reviewed_at) + ')' : ''}. Rekod dikunci.</div>` : ''}
      <div class="grid-form">
        <div>
          <div class="panel">
            <div class="paneltitle"><h3>Borang Pelaporan KPI</h3>${P.badge(status)}</div>
            <dl class="kv mb-3"><dt>Nama IPT</dt><dd>${P.esc(inst.name)}</dd><dt>Kod IPT</dt><dd>${P.esc(inst.code)}</dd><dt>Tahun pelaporan</dt><dd>${y}</dd>
              <dt>Teras</dt><dd>Teras ${k.teras}: ${P.esc(k.teras_name)}</dd><dt>Objektif strategik</dt><dd>${P.esc(k.os_code)} — ${P.esc(k.os_name)}</dd>
              <dt>Kod KPI</dt><dd><b>${P.esc(k.code)}</b></dd><dt>Nama KPI</dt><dd>${P.esc(k.title)}</dd>
              <dt>Sasaran semasa (${y})</dt><dd><b>${P.targetText(t, k.unit)}</b> ${k.unit === 'count' ? `<span class="meta">— sasaran nasional, bukan kuota IPT${F.institution_target !== null && F.institution_target !== undefined ? `; sasaran institusi ditetapkan KPT: <b>${P.fmt(F.institution_target, 0)}</b>` : ''}</span>` : k.unit === 'percent' ? '<span class="meta">— kadar nasional sebagai rujukan</span>' : ''}</dd>
              ${s?.comparison?.gap !== null && s?.comparison?.gap !== undefined ? `<dt>Jurang sasaran</dt><dd class="${s.comparison.achieved ? 'text-success' : 'text-danger'} fw-bold">${(s.comparison.gap >= 0 ? '+' : '') + P.fmt(s.comparison.gap, 2)}${k.unit === 'percent' ? ' mata %' : ''}</dd>` : ''}
              <dt>Status pelaporan</dt><dd>${P.badge(status)} ${s ? `<span class="meta">revisi ${s.revision}</span>` : ''}</dd></dl>
            <form id="kpiForm" data-form="kpi-save" novalidate>
              ${F.applicable ? inputsHtml(k, s, editable) : ''}
              ${F.applicable && k.attestations.length ? `<div class="mt-3 chk-list"><div class="form-label">Syarat kelayakan</div>${k.attestations.map((a, i) => `<div class="form-check"><input class="form-check-input" type="checkbox" id="att${i}" data-attest ${s?.attestations?.[i] ? 'checked' : ''} ${editable ? '' : 'disabled'}><label class="form-check-label" for="att${i}">${P.esc(a)}</label></div>`).join('')}</div>` : ''}
              ${F.applicable ? `<div class="mt-3"><label class="form-label" for="note">Catatan / justifikasi</label><textarea class="form-control" id="note" rows="3" maxlength="4000" ${editable ? '' : 'disabled'} placeholder="Sumber data, tarikh potong, skop populasi, sebab perbezaan dan sebagainya">${P.esc(s?.note || '')}</textarea></div>` : ''}
              <div id="formMsg" class="mt-3"></div>
              <div class="d-flex flex-wrap gap-2 mt-2">
                ${editable ? `<button class="btn btn-soft" type="submit">Simpan Draf</button>
                <button class="btn ${returned ? 'btn-danger' : 'btn-primary'}" type="button" data-act="kpi-submit">${returned ? 'Kemaskini / Hantar Semula' : 'Hantar untuk Semakan KPT'} →</button>` : ''}
                <button class="btn btn-outline-primary" type="button" data-act="scroll-evidence">Lihat Dokumen Sokongan (${activeEv.length})</button>
                <button class="btn btn-outline-primary" type="button" data-act="kpi-history" ${s ? '' : 'disabled'}>Lihat Sejarah</button>
              </div>
            </form>
          </div>
          <div class="panel" id="evidencePanel">
            <div class="paneltitle"><h3>Dokumen sokongan</h3><span class="meta">PDF, XLSX, CSV, DOCX, PNG, JPG · maks. ${P.state.config?.max_upload_mb || 10} MB setiap fail${F.evidence_required ? ' · <b>wajib sekurang-kurangnya satu sebelum dihantar</b>' : ''}</span></div>
            ${ev.length ? ev.map(e => evidenceRow(e, editable)).join('') : P.emptyState('Belum ada dokumen sokongan.', '📄')}
            ${editable ? `<div class="mt-3"><label class="form-label" for="evFile">Muat naik dokumen</label><div class="input-group"><input class="form-control" type="file" id="evFile" multiple accept=".pdf,.xlsx,.csv,.docx,.png,.jpg,.jpeg"><button class="btn btn-teal" type="button" data-act="upload-evidence">Muat naik</button></div>
              <div class="form-text">Jangan muat naik data peribadi graduan. Dokumen yang dihantar bersama laporan dikekalkan sebagai rekod sejarah.</div></div>` : ''}
          </div>
        </div>
        <div>
          <div class="panel"><div class="paneltitle"><h3>Takrif & mekanisme pengukuran</h3><span class="badge text-bg-warning">Formula ${P.esc(k.formula_status === 'confirmed' ? 'diperakukan' : 'DRAF')}</span></div>
            <div class="detail"><span class="meta">${P.esc(k.code)} · TERAS ${k.teras} · ${P.esc(k.source_ref || '')}</span><strong class="d-block mt-1">${P.esc(k.indicator)}</strong>
              <p class="mt-2 mb-2"><b>Takrif KPI:</b> ${P.esc(k.definition)}</p>
              <p class="mb-2"><b>Sasaran keberhasilan 2030:</b> ${P.esc(k.outcome_2030)}</p>
              <b>Mekanisme pengukuran:</b><span class="formula">${P.esc(k.measurement)}</span>
              ${k.denominator_label ? `<p class="mb-1"><b>Pembilang:</b> ${P.esc(k.numerator_label)}<br><b>Penyebut:</b> ${P.esc(k.denominator_label)}</p>` : ''}
              <p class="mb-0"><b>Tanggungjawab / pemilik data:</b> ${P.esc(k.data_owner)}</p></div>
            <h4 class="h6 fw-bold mt-3">Sasaran tahunan</h4>
            <div class="timeline">${Object.entries(k.targets).map(([yr, tt]) => `<div class="yr ${+yr === y ? 'sel' : ''}"><small>${yr}</small><strong>${tt.kind === 'milestone' ? P.fmt(tt.value) + '%*' : P.targetText(tt, k.unit)}</strong></div>`).join('')}</div>
            ${Object.values(k.targets).some(tt => tt.kind === 'milestone') ? '<div class="meta mt-1">* Milestone pembangunan indeks (bukan skor kepuasan majikan).</div>' : ''}
            ${k.cumulative_target ? `<div class="meta mt-1">Sasaran kumulatif menjelang 2030: <b>${P.fmt(k.cumulative_target, 0)}</b> (disimpan sebagai sasaran tahunan, bukan kumulatif).</div>` : ''}
            ${k.confirmation_notes.length ? `<div class="callout warn mt-3 mb-0"><b>Perlu pengesahan KPT:</b><ul class="mb-0 ps-3">${k.confirmation_notes.map(n => `<li>${P.esc(n)}</li>`).join('')}</ul></div>` : ''}
          </div>
          ${s?.verification_history?.length ? `<div class="panel"><div class="paneltitle"><h3>Sejarah pengesahan KPT</h3></div>${s.verification_history.map(v => `<div class="hist"><div>${P.badge(v.decision)} oleh <b>${P.esc(v.reviewer)}</b> · revisi ${v.revision}</div>${v.comment ? `<div>${P.esc(v.comment)}</div>` : ''}<div class="when">${P.date(v.at)}</div></div>`).join('')}</div>` : ''}
        </div>
      </div>`
    });
    P.inputs.calc();
  }

  function evidenceRow(e, editable) {
    return `<div class="evid ${e.withdrawn ? 'withdrawn' : ''}"><span aria-hidden="true">📄</span><div class="nm"><b>${P.esc(e.name)}</b><div class="meta">${e.size < 1024 ? e.size + ' B' : P.fmt(e.size / 1024, 1) + ' KB'} · revisi ${e.revision} · ${P.esc(e.uploaded_by)} · ${P.date(e.uploaded_at)}${e.locked ? ' · 🔒 dihantar' : ''}${e.withdrawn ? ' · ditarik balik' : ''}</div></div>
      ${e.previewable && !e.withdrawn ? `<button class="btn btn-sm btn-soft" type="button" data-act="preview-evidence" data-id="${e.id}" data-name="${P.esc(e.name)}">Pratonton</button>` : ''}
      <a class="btn btn-sm btn-outline-primary" href="/api/evidence/${e.id}/download">Muat turun</a>
      ${editable && !e.locked && !e.withdrawn ? `<button class="btn btn-sm btn-outline-danger" type="button" data-act="withdraw-evidence" data-id="${e.id}">Tarik balik</button>` : ''}</div>`;
  }

  async function saveDraft(silent = false) {
    const r = await P.api('/ipt/submissions', { method: 'PUT', body: collect() });
    F.submission = r.submission;
    if (!silent) {
      P.toast(r.message);
      if (r.warnings?.length) P.toast(r.warnings.join(' '), 'warning');
    }
    return r;
  }
  P.forms['kpi-save'] = async () => { await saveDraft(); renderForm(); };
  P.actions['kpi-submit'] = async () => {
    const box = P.$('#formMsg'); box.innerHTML = '';
    try { await saveDraft(true); }
    catch (e) { box.innerHTML = `<div class="callout danger">${P.esc(e.message)}</div>`; return; }
    const s = F.submission;
    const ok = await P.confirm({
      title: 'Hantar untuk semakan KPT?', ok: 'Hantar', body: `<p>Laporan <b>${P.esc(F.kpi.code)}</b> bagi tahun ${F.year} akan dihantar kepada Penyelaras KPT. Selepas dihantar, rekod tidak boleh diubah sehingga dipulangkan.</p>
      <div class="detail">Pencapaian: <b>${F.kpi.unit === 'index' ? P.fmt(s.index_score) + (s.index_excellent ? ' (Cemerlang)' : '') : P.val(s.value, F.kpi.unit)}</b>${s.denominator ? ` (${P.fmt(s.numerator, 0)} ÷ ${P.fmt(s.denominator, 0)})` : ''}<br>Dokumen sokongan: ${(s.evidence || []).filter(e => !e.withdrawn).length}</div>`
    });
    if (!ok) { renderForm(); return; }
    try {
      const r = await P.api(`/ipt/submissions/${s.id}/submit`, { method: 'POST' });
      F.submission = r.submission; F.editable = false; P.toast(r.message); renderForm();
    } catch (e) { renderForm(); P.$('#formMsg').innerHTML = `<div class="callout danger" role="alert">${P.esc(e.message)}</div>`; }
  };
  P.actions['scroll-evidence'] = () => P.$('#evidencePanel').scrollIntoView({ behavior: 'smooth' });
  P.actions['upload-evidence'] = async () => {
    const input = P.$('#evFile');
    if (!input.files.length) { P.toast('Pilih fail terlebih dahulu.', 'warning'); return; }
    if (!F.submission) await saveDraft(true);
    let n = 0;
    for (const f of input.files) {
      const fd = new FormData(); fd.append('file', f);
      try { await P.api(`/ipt/submissions/${F.submission.id}/evidence`, { method: 'POST', form: fd }); n++; }
      catch (e) { P.toast(`${f.name}: ${e.message}`, 'danger'); }
    }
    if (n) P.toast(`${n} dokumen dimuat naik.`);
    F = await P.api(`/ipt/form/${F.kpi.id}?year=${F.year}`); renderForm();
  };
  P.actions['withdraw-evidence'] = async el => {
    if (!await P.confirm({ title: 'Tarik balik dokumen?', body: 'Dokumen akan ditanda sebagai ditarik balik (tidak dipadam daripada rekod audit).', ok: 'Tarik balik', okClass: 'btn-danger' })) return;
    await P.api(`/evidence/${el.dataset.id}/withdraw`, { method: 'POST' });
    F = await P.api(`/ipt/form/${F.kpi.id}?year=${F.year}`); renderForm();
  };
  P.actions['preview-evidence'] = el => {
    const url = `/api/evidence/${el.dataset.id}/download?inline=true`;
    if (/\.pdf$/i.test(el.dataset.name)) { window.open(url, '_blank', 'noopener'); return; }
    P.modal({
      title: 'Pratonton: ' + P.esc(el.dataset.name), size: 'modal-xl',
      body: `<img src="${url}" alt="Pratonton ${P.esc(el.dataset.name)}" class="img-fluid border rounded">`,
      footer: `<a class="btn btn-primary" href="/api/evidence/${el.dataset.id}/download">Muat turun</a>`
    });
  };
  P.actions['kpi-history'] = async () => {
    const s = F.submission; if (!s) return;
    P.showHistory(s, F.kpi.unit);
  };
  P.showHistory = (s, unit) => {
    const ACTION = { SAVE_DRAFT: 'Draf disimpan', SUBMIT: 'Dihantar', RESUBMIT: 'Dihantar semula', VERIFY: 'Disahkan', RETURN: 'Dipulangkan', REOPEN: 'Dibuka semula' };
    P.modal({
      title: 'Sejarah rekod ' + P.esc(s.kpi.code), size: 'modal-lg',
      body: (s.revisions || []).slice().reverse().map(r => `<div class="hist"><div><b>${P.esc(ACTION[r.action] || r.action)}</b> → ${P.badge(r.status)} · revisi ${r.revision} · ${P.esc(r.actor || '')}</div>
        <div class="meta">Nilai: ${unit === 'index' ? P.fmt(r.snapshot.index_score) : P.val(r.snapshot.value, unit)}${r.snapshot.denominator ? ` (${P.fmt(r.snapshot.numerator, 0)} ÷ ${P.fmt(r.snapshot.denominator, 0)})` : ''} · dokumen: ${(r.snapshot.evidence_ids || []).length}</div>
        ${r.comment ? `<div>${P.esc(r.comment)}</div>` : ''}<div class="when">${P.date(r.at)}</div></div>`).join('') || P.emptyState('Tiada sejarah.')
    });
  };

  /* -------------------------------------------------------------- verified institutional records */
  P.route('/ipt/prestasi', async () => {
    const y = P.state.year;
    const [nat, subs] = await Promise.all([P.api('/analytics/national?year=' + y), P.api('/submissions?year=' + y + '&status=VERIFIED')]);
    const rows = nat.kpis;
    const withData = rows.filter(r => r.value !== null && r.target !== null && r.target_kind !== 'milestone');
    P.layoutApp({
      title: 'Rekod Disahkan Institusi', subtitle: 'Hanya rekod yang telah disahkan oleh KPT',
      html: P.heading('Prestasi institusi (disahkan)', `Tahun ${y} · ${subs.length} rekod disahkan`, yearSel(y)) + `
      <div class="panel"><div class="paneltitle"><h3>Pencapaian sebagai % sasaran (dinormalkan)</h3><span class="meta">Pencapaian ÷ sasaran × 100. KPI bilangan dibandingkan dengan sasaran nasional hanya sebagai rujukan.</span></div>
        ${withData.length ? '<div class="chartbox"><canvas id="iptChart" aria-label="Carta pencapaian institusi"></canvas></div>' : P.emptyState('Belum ada rekod disahkan bagi tahun ini.')}</div>
      <div class="panel"><div class="paneltitle"><h3>Rekod disahkan</h3><a class="btn btn-sm btn-soft" href="#/laporan">Muat turun laporan institusi</a></div>
      <div class="tablewrap"><table class="datatable"><thead><tr><th>Kod</th><th>KPI</th><th class="num">Pembilang</th><th class="num">Penyebut</th><th class="num">Pencapaian</th><th class="num">Sasaran</th><th class="num">Jurang</th><th>Disahkan</th></tr></thead><tbody>
      ${subs.length ? subs.map(s => `<tr><td><b>${P.esc(s.kpi.code)}</b></td><td>${P.esc(s.kpi.title)}</td><td class="num">${P.fmt(s.numerator, 0)}</td><td class="num">${P.fmt(s.denominator, 0)}</td>
        <td class="num"><b>${s.kpi.unit === 'index' ? P.fmt(s.index_score) : P.val(s.value, s.kpi.unit)}</b></td><td class="num">${P.targetText(s.target, s.kpi.unit)}</td>
        <td class="num">${s.comparison.gap === null ? '—' : (s.comparison.gap >= 0 ? '+' : '') + P.fmt(s.comparison.gap, 2)}</td><td>${P.esc(s.reviewed_by || '')}<div class="meta">${P.date(s.reviewed_at)}</div></td></tr>`).join('')
        : `<tr><td colspan="8">${P.emptyState('Tiada rekod disahkan.')}</td></tr>`}</tbody></table></div></div>`
    });
    if (withData.length) P.chart('#iptChart', {
      type: 'bar', data: { labels: withData.map(r => r.code), datasets: [{ label: '% sasaran dicapai', data: withData.map(r => r.pct_of_target), backgroundColor: withData.map(r => r.achieved ? P.COL.teal : P.COL.amber) }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${P.fmt(c.raw, 1)}% daripada sasaran` } } }, scales: { y: { beginAtZero: true, title: { display: true, text: '% sasaran' } } } }
    });
  }, { perm: 'ipt.report' });
})();
