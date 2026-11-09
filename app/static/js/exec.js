/* Executive dashboard (Pengurusan Tertinggi) and national performance — verified data only. */
'use strict';
(() => {
  const qs = o => Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

  P.route('/eksekutif', async (_, q) => {
    const y = +(q.tahun || P.state.year);
    const f = { teras: q.teras || '', kpi: q.kpi || '', ipt: q.ipt || '', kategori: q.kategori || '' };
    const canInst = P.can('dashboard.executive') || P.can('monitoring.view');
    const [nat, kpis, insts] = await Promise.all([
      P.api('/analytics/national?' + qs({ year: y, institution_id: f.ipt, category: f.kategori })),
      P.state.kpis ? Promise.resolve(P.state.kpis) : P.api('/kpis'),
      P.can('monitoring.view') ? P.api('/kpt/institutions') : Promise.resolve([]),
    ]);
    P.state.kpis = kpis;
    const all = nat.kpis;
    const rows = all.filter(r => (!f.teras || r.teras === +f.teras) && (!f.kpi || r.kpi_id === +f.kpi));
    const selKpi = kpis.find(k => k.id === +f.kpi) || kpis.find(k => !f.teras || k.teras === +f.teras) || kpis[0];
    const [trend, comp] = await Promise.all([
      P.api('/analytics/trend?' + qs({ kpi_id: selKpi.id, institution_id: f.ipt, category: f.kategori })),
      canInst ? P.api('/analytics/institutions?' + qs({ kpi_id: selKpi.id, year: y, category: f.kategori })) : Promise.resolve(null),
    ]);
    const S = nat.summary;
    const hasData = all.some(r => r.value !== null);
    const stat = (l, v, cls = '', h = '') => `<div class="stat ${cls}"><div class="label">${l}</div><div class="value">${v}</div>${h ? `<div class="hint">${h}</div>` : ''}</div>`;
    const scopeTxt = nat.scope === 'national' ? 'Agregat nasional (IPT melapor)' : nat.scope === 'category' ? 'Kategori: ' + P.esc(P.CATS()[f.kategori] || f.kategori) : 'Institusi terpilih';
    P.layoutApp({
      title: P.can('monitoring.view') ? 'Prestasi Nasional' : 'Dashboard Eksekutif', subtitle: 'Prestasi strategik PSKG 2026–2030 berdasarkan rekod yang DISAHKAN sahaja',
      html: P.heading('Dashboard Eksekutif', `${scopeTxt} · Tahun ${y}`, `
        <form class="filters" data-form="exec-filter">
          <select class="form-select" name="tahun" aria-label="Tahun">${P.yearOptions(y)}</select>
          <select class="form-select" name="teras" aria-label="Teras"><option value="">Semua 5 Teras</option>${Object.entries(P.terasNames).map(([k, v]) => `<option value="${k}" ${+f.teras === +k ? 'selected' : ''}>Teras ${k}</option>`).join('')}</select>
          <select class="form-select" name="kpi" aria-label="KPI"><option value="">Semua KPI</option>${kpis.map(k => `<option value="${k.id}" ${+f.kpi === k.id ? 'selected' : ''}>${P.esc(k.code)}</option>`).join('')}</select>
          ${insts.length ? `<select class="form-select" name="ipt" aria-label="Institusi"><option value="">Semua institusi</option>${insts.filter(i => i.status === 'ACTIVE').map(i => `<option value="${i.id}" ${+f.ipt === i.id ? 'selected' : ''}>${P.esc(i.code)}</option>`).join('')}</select>` : ''}
          <select class="form-select" name="kategori" aria-label="Kategori institusi"><option value="">Semua kategori</option>${Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}" ${f.kategori === k ? 'selected' : ''}>${P.esc(v)}</option>`).join('')}</select>
          <button class="btn btn-primary">Tapis</button></form>`) + `
      <div class="stats">
        ${stat('Jumlah institusi', S.institutions, 'blue', 'Institusi aktif dalam skop')}
        ${stat('Institusi telah melapor', S.institutions_reported, 'teal', 'Dihantar atau disahkan')}
        ${stat('Institusi belum melapor', S.institutions_not_reported, 'red')}
        ${stat('Laporan disahkan', S.verified_reports, 'teal')}
        ${stat('KPI capai sasaran', S.kpis_met, 'teal', 'Berdasarkan data disahkan')}
        ${stat('KPI di bawah sasaran', S.kpis_below, 'amber')}
        ${stat('KPI tanpa data disahkan', S.kpis_no_data, '', 'Tidak dianggap sifar')}
        ${stat('Liputan pelaporan', S.coverage_pct === null ? '—' : P.fmt(S.coverage_pct, 1) + '%', 'blue', 'IPT dengan ≥1 laporan disahkan')}
      </div>
      <div class="callout info small">${P.esc(nat.note)}</div>
      <div class="cards5">${nat.teras.map(t => `<a class="tera ${+f.teras === t.teras ? 'active' : ''}" href="#/eksekutif?${qs({ ...f, tahun: y, teras: +f.teras === t.teras ? '' : t.teras, kpi: '' })}"><small>TERAS ${t.teras}</small><b>${P.esc(t.name)}</b>
        <span class="count">${t.kpis}</span><span class="meta"> KPI</span><div class="meta mt-1"><span class="text-success fw-bold">${t.met} capai</span> · <span class="text-warning fw-bold">${t.below} bawah</span> · ${t.no_data} tiada data</div></a>`).join('')}</div>
      ${!hasData ? `<div class="panel">${P.emptyState('Belum ada data disahkan bagi tahun dan tapisan ini. Dashboard rasmi tidak memaparkan nilai simulasi.', '◔')}</div>` : `
      <div class="grid2">
        <div class="panel"><div class="paneltitle"><h3>Sasaran vs pencapaian (dinormalkan)</h3><span class="meta">Pencapaian ÷ sasaran × 100 — garis 100% = sasaran</span></div><div class="chartbox lg"><canvas id="cTvA" aria-label="Carta sasaran berbanding pencapaian"></canvas></div>
          <div class="meta mt-1">Penormalan digunakan supaya KPI peratus dan bilangan boleh dipaparkan bersama tanpa dipuratakan. Milestone indeks dikecualikan.</div></div>
        <div class="panel"><div class="paneltitle"><h3>Jurang kepada sasaran</h3><span class="meta">(% sasaran dicapai − 100)</span></div><div class="chartbox lg"><canvas id="cGap"></canvas></div></div>
      </div>`}
      <div class="grid2">
        <div class="panel"><div class="paneltitle"><h3>Trend 2026–2030: ${P.esc(selKpi.code)}</h3><span class="meta">${P.esc(selKpi.title)}</span></div><div class="chartbox"><canvas id="cTrend"></canvas></div></div>
        <div class="panel"><div class="paneltitle"><h3>Liputan pelaporan disahkan mengikut KPI</h3><span class="meta">% IPT berkenaan dengan rekod disahkan</span></div><div class="chartbox"><canvas id="cCov"></canvas></div></div>
      </div>
      <div class="grid2">
        ${comp ? `<div class="panel"><div class="paneltitle"><h3>Perbandingan institusi: ${P.esc(comp.kpi.code)} (${y})</h3><span class="meta">${comp.rows.length} disahkan · ${comp.not_reported.length} tiada data</span></div>
          ${comp.rows.length ? '<div class="chartbox"><canvas id="cInst"></canvas></div>' : P.emptyState('Tiada rekod disahkan bagi KPI ini.')}
          ${comp.not_reported.length ? `<div class="meta mt-2">Tiada data disahkan (tidak dikira sifar): ${comp.not_reported.map(i => P.esc(i.code)).join(', ')}</div>` : ''}</div>` : ''}
        <div class="panel"><div class="paneltitle"><h3>Prestasi mengikut Teras</h3><span class="meta">Bilangan KPI capai / bawah / tiada data</span></div><div class="chartbox"><canvas id="cTeras"></canvas></div></div>
      </div>
      <div class="panel"><div class="paneltitle"><h3>Jadual terperinci KPI ${f.teras ? '— Teras ' + f.teras : ''}</h3><a class="btn btn-sm btn-soft" href="#/laporan">Eksport laporan</a></div>
      <div class="tablewrap"><table class="datatable"><thead><tr><th>Kod</th><th>KPI</th><th>Kaedah agregat</th><th class="num">Σ Pembilang</th><th class="num">Σ Penyebut</th><th class="num">Pencapaian</th><th class="num">Sasaran ${y}</th><th class="num">Jurang</th><th>Status</th><th class="num">Liputan</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td><b>${P.esc(r.code)}</b></td><td>${P.esc(r.title)}</td><td class="meta">${P.esc(r.method_label)}${r.duplicates_excluded ? `<br>${r.duplicates_excluded} pendua dikecualikan` : ''}</td>
        <td class="num">${P.fmt(r.numerator_sum, 0)}</td><td class="num">${P.fmt(r.denominator_sum, 0)}</td>
        <td class="num"><b>${r.method === 'milestone' ? (r.value === null ? '—' : P.fmt(r.value) + '% siap') : P.val(r.value, r.unit === 'index' ? 'percent' : r.unit)}</b></td>
        <td class="num">${P.targetText({ value: r.target, kind: r.target_kind, label: r.target_label }, r.unit)}</td>
        <td class="num">${r.gap === null ? '—' : (r.gap >= 0 ? '+' : '') + P.fmt(r.gap, 2)}</td>
        <td>${r.achieved === true ? P.badge('VERIFIED', 'Capai') : r.achieved === false ? P.badge('SUBMITTED', 'Di bawah sasaran') : P.badge('NOT_STARTED', 'Tiada data disahkan')}</td>
        <td class="num">${r.method === 'milestone' ? '<span class="meta">KPT</span>' : `${r.reporting}/${r.applicable}`}</td></tr>`).join('')}
      </tbody></table></div></div>`
    });

    const norm = all.filter(r => r.pct_of_target !== null && r.method !== 'milestone' && (!f.teras || r.teras === +f.teras));
    if (hasData) {
      P.chart('#cTvA', {
        type: 'bar', data: { labels: norm.map(r => r.code), datasets: [{ label: '% sasaran dicapai', data: norm.map(r => r.pct_of_target), backgroundColor: norm.map(r => r.achieved ? P.COL.teal : P.COL.amber) }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => { const r = norm[c.dataIndex]; return [`${P.fmt(c.raw, 1)}% daripada sasaran`, `Pencapaian ${P.val(r.value, r.unit === 'index' ? 'percent' : r.unit)} vs sasaran ${P.fmt(r.target)}`]; } } } },
          scales: { x: { beginAtZero: true, title: { display: true, text: '% sasaran dicapai (100 = sasaran)' } } } }
      });
      P.chart('#cGap', {
        type: 'bar', data: { labels: norm.map(r => r.code), datasets: [{ label: 'Jurang (%)', data: norm.map(r => +(r.pct_of_target - 100).toFixed(2)), backgroundColor: norm.map(r => r.pct_of_target >= 100 ? P.COL.green : P.COL.red) }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: 'Lebihan (+) / kekurangan (−) berbanding sasaran, %' } } } }
      });
    }
    const pts = trend.points;
    const unit = selKpi.unit;
    P.chart('#cTrend', {
      type: 'line', data: { labels: pts.map(p => p.year), datasets: [
        { label: 'Sasaran', data: pts.map(p => p.target), borderColor: P.COL.teal, backgroundColor: P.COL.teal, tension: .2 },
        { label: 'Pencapaian disahkan', data: pts.map(p => p.value), borderColor: P.COL.amber, backgroundColor: P.COL.amber, borderDash: [6, 4], tension: .2, spanGaps: false, pointRadius: 6, pointHoverRadius: 8 }] },
      options: { plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.raw === null ? 'tiada data disahkan' : P.fmt(c.raw) + (unit === 'count' ? '' : '%')}${pts[c.dataIndex].target_kind === 'milestone' ? ' (milestone indeks)' : ''}` } } },
        scales: { y: { beginAtZero: true, title: { display: true, text: unit === 'count' ? 'Bilangan' : '%' } } } }
    });
    const cov = all.filter(r => r.method !== 'milestone' && (!f.teras || r.teras === +f.teras));
    P.chart('#cCov', {
      type: 'bar', data: { labels: cov.map(r => r.code), datasets: [{ label: 'Liputan disahkan (%)', data: cov.map(r => r.coverage_pct ?? 0), backgroundColor: P.COL.blue }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${P.fmt(c.raw, 1)}% (${cov[c.dataIndex].reporting}/${cov[c.dataIndex].applicable} IPT)` } } }, scales: { y: { beginAtZero: true, max: 100 } } }
    });
    if (comp && comp.rows.length) {
      const isIdx = comp.kpi.unit === 'index';
      P.chart('#cInst', {
        type: 'bar', data: { labels: comp.rows.map(r => r.code), datasets: [
          { label: isIdx ? 'Skor indeks' : comp.kpi.unit === 'count' ? 'Bilangan' : 'Pencapaian (%)', data: comp.rows.map(r => r.value), backgroundColor: comp.rows.map(r => r.achieved === false ? P.COL.amber : P.COL.teal) },
          ...(comp.kpi.unit === 'percent' && comp.target.value !== null ? [{ type: 'line', label: 'Sasaran nasional', data: comp.rows.map(() => comp.target.value), borderColor: P.COL.navy, pointRadius: 0, borderDash: [4, 4] }] : [])] },
        options: { plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }
      });
    }
    P.chart('#cTeras', {
      type: 'bar', data: { labels: nat.teras.map(t => 'Teras ' + t.teras), datasets: [
        { label: 'Capai', data: nat.teras.map(t => t.met), backgroundColor: P.COL.teal }, { label: 'Di bawah sasaran', data: nat.teras.map(t => t.below), backgroundColor: P.COL.amber },
        { label: 'Tiada data disahkan', data: nat.teras.map(t => t.no_data), backgroundColor: P.COL.light }] },
      options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }
    });
  }, { perm: 'dashboard.executive' });
  P.forms['exec-filter'] = form => P.go('/eksekutif?' + qs(P.formData(form)));

  /* -------------------------------------------------------------- reports & export */
  P.route('/laporan', async () => {
    const cat = await P.api('/reports');
    const y = P.state.year;
    const insts = P.can('monitoring.view') ? await P.api('/kpt/institutions') : [];
    const DESC = {
      ipt_performance: 'Rekod setiap KPI bagi institusi: pembilang, penyebut, pencapaian, sasaran, jurang dan status pengesahan.',
      national_kpi: 'Agregat nasional 20 KPI daripada rekod disahkan, dengan kaedah agregat dan liputan.',
      by_teras: 'Pencapaian KPI dikumpulkan mengikut lima Teras dengan ringkasan capai/bawah/tiada data.',
      target_vs_actual: 'Sasaran tahunan berbanding pencapaian, jurang dan % sasaran dicapai.',
      reporting_status: 'Matriks status pelaporan setiap institusi bagi setiap KPI.',
      verification: 'Log keputusan pengesahan KPT (disahkan/dipulangkan/dibuka semula).',
      annual_trend: 'Pencapaian dan sasaran 2026–2030 bagi setiap KPI.',
    };
    P.layoutApp({
      title: 'Laporan & Eksport', subtitle: 'Laporan rasmi daripada pangkalan data pusat (CSV, XLSX, PDF)',
      html: `<div class="panel"><form class="row g-2 align-items-end" id="repFilters">
        <div class="col-sm-3"><label class="form-label" for="rYear">Tahun</label><select class="form-select" id="rYear">${P.yearOptions(y)}</select></div>
        <div class="col-sm-3"><label class="form-label" for="rTeras">Teras</label><select class="form-select" id="rTeras"><option value="">Semua</option>${Object.entries(P.terasNames).map(([k, v]) => `<option value="${k}">Teras ${k}: ${P.esc(v)}</option>`).join('')}</select></div>
        ${P.state.me.role !== 'ipt' ? `<div class="col-sm-3"><label class="form-label" for="rCat">Kategori</label><select class="form-select" id="rCat"><option value="">Semua</option>${Object.entries(P.CATS()).map(([k, v]) => `<option value="${k}">${P.esc(v)}</option>`).join('')}</select></div>` : ''}
        ${insts.length ? `<div class="col-sm-3"><label class="form-label" for="rInst">Institusi</label><select class="form-select" id="rInst"><option value="">Semua</option>${insts.map(i => `<option value="${i.id}">${P.esc(i.code)}</option>`).join('')}</select></div>` : ''}
      </form></div>
      <div class="row g-3">${cat.map(r => `<div class="col-md-6 col-xl-4"><div class="panel h-100 d-flex flex-column"><h3 class="h6 fw-bold">${P.esc(r.title)}</h3><p class="small text-muted flex-grow-1">${P.esc(DESC[r.key] || '')}</p>
        <div class="d-flex gap-2 flex-wrap">${['csv', 'xlsx', 'pdf'].map(fm => `<button class="btn btn-sm ${fm === 'xlsx' ? 'btn-primary' : 'btn-soft'}" data-act="download-report" data-key="${r.key}" data-fmt="${fm}">⇩ ${fm.toUpperCase()}</button>`).join('')}</div></div></div>`).join('')}</div>
      <p class="meta mt-2">Setiap laporan mengandungi tahun pelaporan, kod KPI, pencapaian, sasaran, jurang, status pengesahan, skop pelaporan dan cap masa penjanaan.</p>`
    });
  });
  P.actions['download-report'] = el => {
    const o = { year: P.$('#rYear').value, teras: P.$('#rTeras').value, category: P.$('#rCat')?.value || '', institution_id: P.$('#rInst')?.value || '', format: el.dataset.fmt };
    const a = document.createElement('a'); a.href = `/api/reports/${el.dataset.key}?${qs(o)}`; a.rel = 'noopener'; document.body.appendChild(a); a.click(); a.remove();
    P.toast('Laporan sedang dimuat turun…', 'info');
  };

  /* -------------------------------------------------------------- notifications */
  P.route('/notifikasi', async () => {
    const d = await P.api('/notifications');
    P.layoutApp({
      title: 'Notifikasi', subtitle: 'Notifikasi dalam aplikasi',
      html: `<div class="panel"><div class="paneltitle"><h3>${d.unread} belum dibaca</h3>${d.unread ? '<button class="btn btn-sm btn-soft" data-act="mark-read">Tanda semua dibaca</button>' : ''}</div>
      ${d.items.length ? d.items.map(n => `<div class="notif-item ${n.read ? '' : 'unread'}"><div class="d-flex justify-content-between gap-2"><b>${P.esc(n.title)}</b><span class="meta text-nowrap">${P.date(n.created_at)}</span></div>
        ${n.body ? `<div class="small">${P.esc(n.body)}</div>` : ''}${n.link ? `<a class="small" href="${P.esc(n.link)}">Buka →</a>` : ''}</div>`).join('') : P.emptyState('Tiada notifikasi.', '🔔')}</div>`
    });
  });
  P.actions['mark-read'] = async () => { await P.api('/notifications/read', { method: 'POST' }); P.state.unread = 0; P.render(); };
})();
