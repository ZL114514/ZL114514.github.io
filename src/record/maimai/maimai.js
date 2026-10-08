// 舞萌DX 成绩库 —— 纯前端,读同目录 records.json + growth.json
(function () {
  const root = document.getElementById('mai');
  if (!root) return;

  const esc = (s) =>
    String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // DX Rating 档位（Gen 3）：数字定档,牌子颜色只是互相校验
  const TIER = {
    white:    ['白', '#e9edf2'],
    blue:     ['蓝', '#4a90e2'],
    green:    ['绿', '#3fb54b'],
    yellow:   ['黄', '#e0b422'],
    red:      ['赤', '#e0483b'],
    purple:   ['紫', '#9a5fd0'],
    bronze:   ['铜', '#b0763f'],
    silver:   ['银', '#b9c2cc'],
    gold:     ['金', '#dfa41c'],
    platinum: ['白金', '#6fd0c8'],
    rainbow:  ['虹', 'linear-gradient(90deg,#e0483b,#e0b422,#3fb54b,#4a90e2,#9a5fd0)'],
  };
  const DIFF_ORDER = ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'Re:MASTER'];
  const RANK_ORDER = ['D', 'C', 'B', 'BB', 'BBB', 'A', 'AA', 'AAA', 'S', 'S+', 'SS', 'SS+', 'SSS', 'SSS+'];

  const fmt = (n, d) => (n == null ? '—' : Number(n).toFixed(d == null ? 0 : d));
  const ach = (r) => (r.achievement == null ? null : r.achievement);

  const tierBadge = (t) => {
    const [name, color] = TIER[t] || ['?', '#888'];
    const bg = color.startsWith('linear') ? color : color;
    return '<span class="mai-tier" title="' +
      esc(t + (TIER[t] ? '' : ' (未知档位)')) + '" style="background:' + esc(bg) +
      (t === 'white' || t === 'silver' || t === 'platinum' ? ';color:#222' : '') + '">' + esc(name) + '</span>';
  };

  const rankClass = (g) => 'mai-rank' + (g ? ' mai-r-' + g.replace(/[+:]/g, '') : '');

  let all = [];
  let mask = { diff: '', rank: '' };

  // ---------- Rating 成长曲线 ----------
  function series(rows) {
    const pts = rows
      .filter((r) => r.player_rating != null && r.captured_at)
      .map((r) => ({ t: r.captured_at, v: r.player_rating, tier: r.tier, title: r.title }))
      .sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
    const out = [];
    for (const p of pts) if (!out.length || out[out.length - 1].v !== p.v) out.push(p);
    return out;
  }

  function chart(pts) {
    if (pts.length < 2) {
      return '<p class="mai-note">Rating 曲线要至少两次结算才有得画' +
        (pts.length === 1 ? '，目前只有 ' + pts[0].v + '（' + esc(pts[0].t.slice(0, 16)) + '）' : '') + '。</p>';
    }
    const W = 760, H = 200, PX = 34, PY = 22;
    const vs = pts.map((p) => p.v);
    let lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs);
    if (hi === lo) { hi = lo + 1; }
    const pad = Math.max(20, (hi - lo) * 0.12);
    lo -= pad; hi += pad;
    const x = (i) => PX + (i * (W - PX * 2)) / (pts.length - 1);
    const y = (v) => H - PY - ((v - lo) * (H - PY * 2)) / (hi - lo);

    let d = '', dots = '';
    pts.forEach((p, i) => {
      const px = x(i).toFixed(1), py = y(p.v).toFixed(1);
      d += (i ? ' L' : 'M') + px + ' ' + py;
      dots += '<circle cx="' + px + '" cy="' + py + '" r="' + (i === pts.length - 1 ? 4.5 : 3) + '"' +
        ' class="mai-dot' + (i === pts.length - 1 ? ' mai-dot-last' : '') + '">' +
        '<title>' + esc(p.t.slice(0, 16) + '  ' + p.title + '  ' + p.v) + '</title></circle>';
    });
    const gridY = [hi, (hi + lo) / 2, lo]
      .map((v) => '<line x1="' + PX + '" x2="' + (W - PX) + '" y1="' + y(v).toFixed(1) +
        '" y2="' + y(v).toFixed(1) + '" class="mai-grid"/><text x="6" y="' +
        (y(v) + 4).toFixed(1) + '" class="mai-axis">' + Math.round(v) + '</text>').join('');
    return '<figure class="mai-chart"><svg viewBox="0 0 ' + W + ' ' + H + '" role="img" ' +
      'aria-label="DX Rating 成长曲线">' + gridY +
      '<path d="' + d + '" class="mai-line"/>' + dots + '</svg>' +
      '<figcaption>' + esc(pts[0].t.slice(0, 10)) + ' → ' + esc(pts[pts.length - 1].t.slice(0, 10)) +
      '，共 ' + pts.length + ' 个采样点，' + esc(String(pts[0].v)) + ' → ' + esc(String(pts[pts.length - 1].v)) +
      '（' + (pts[pts.length - 1].v - pts[0].v >= 0 ? '+' : '') + (pts[pts.length - 1].v - pts[0].v) + '）</figcaption></figure>';
  }

  // ---------- 统计 ----------
  function stats(rows) {
    const songs = new Set(rows.map((r) => r.title + '|' + r.difficulty));
    const bestAch = rows.reduce((m, r) => (ach(r) != null && (m == null || ach(r) > m) ? ach(r) : m), null);
    const latest = series(rows).slice(-1)[0];
    const cells = [];
    if (rows.length) cells.push(['游玩记录', rows.length + ' 次']);
    if (songs.size) cells.push(['谱面', songs.size + ' 个']);
    if (bestAch != null) cells.push(['最高达成率', bestAch.toFixed(4) + '%']);
    if (latest) cells.push(['当前 Rating', latest.v + ' ']);
    const byDiff = {};
    rows.forEach((r) => { if (r.difficulty) byDiff[r.difficulty] = (byDiff[r.difficulty] || 0) + 1; });
    return '<div class="mai-stats">' + cells.map(([k, v]) =>
      '<div class="mai-stat"><span>' + esc(k) + '</span><b>' + esc(v) +
      (k === '当前 Rating' && latest ? tierBadge(latest.tier) : '') + '</b></div>').join('') +
      '</div><div class="mai-filters">' +
      '<span class="mai-filt-label">难度</span>' +
      ['', ...DIFF_ORDER.filter((d) => byDiff[d])].map((d) =>
        '<button data-diff="' + esc(d) + '"' + (mask.diff === d ? ' class="on"' : '') + '>' +
        esc(d || '全部') + (d ? ' ' + byDiff[d] : '') + '</button>').join('') +
      '<span class="mai-filt-label">评级</span>' +
      ['', ...RANK_ORDER.filter((g) => rows.some((r) => r.rank === g)).reverse()].map((g) =>
        '<button data-rank="' + esc(g) + '"' + (mask.rank === g ? ' class="on"' : '') + '>' +
        esc(g || '全部') + '</button>').join('') + '</div>';
  }

  // ---------- 列表（每曲最佳） ----------
  function bests(rows) {
    const seen = {};
    for (const r of rows) {
      const k = r.title + '|' + r.difficulty;
      if (!seen[k] || (ach(r) || 0) > (ach(seen[k]) || 0)) seen[k] = r;
    }
    return Object.keys(seen).map((k) => seen[k])
      .sort((a, b) => (b.single_rating || 0) - (a.single_rating || 0));
  }

  function row(r) {
    const img = r.src
      ? '<a class="mai-shot" href="' + esc(r.src) + '" target="_blank" rel="noopener" title="看原图">' +
        '<img loading="lazy" src="' + esc(r.src) + '" alt=""></a>'
      : '<div class="mai-shot mai-ph"></div>';
    const icon = r.icon
      ? '<img class="mai-icon" loading="lazy" src="icons/' + esc(r.icon) + '" alt="Rating 档位" title="结算时的 DX Rating ' +
        esc(r.player_rating == null ? '?' : r.player_rating) + '">'
      : '';
    const j = r.judgements || {};
    const jtxt = Object.keys(j).length
      ? '<span class="mai-j">' + Object.keys(j).map((k) => esc(k) + ' ' + esc(j[k])).join(' · ') + '</span>' : '';
    return '<div class="mai-card">' + img +
      '<div class="mai-meta">' +
      '<div class="mai-title">' + esc(r.title) + '</div>' +
      '<div class="mai-sub">' + esc([r.difficulty, r.level || '', r.ds != null ? '定数 ' + r.ds : '']
        .filter(Boolean).join(' · ')) + '</div>' +
      '<div class="mai-tags">' +
      '<span class="' + rankClass(r.rank) + '">' + esc(r.rank || '?') + '</span>' +
      '<span class="mai-ach">' + (ach(r) == null ? '—' : ach(r).toFixed(4) + '%') + '</span>' +
      (r.dx_score != null ? '<span class="mai-dx">DX ' + esc(r.dx_score) + '</span>' : '') +
      (r.single_rating != null ? '<span class="mai-sr">单曲 R ' + esc(r.single_rating) + '</span>' : '') +
      icon + '</div>' +
      '<div class="mai-sub mai-when">' + esc((r.captured_at || '').slice(0, 16)) + jtxt + '</div>' +
      '</div></div>';
  }

  function render() {
    const rows = all.filter((r) =>
      (!mask.diff || r.difficulty === mask.diff) && (!mask.rank || r.rank === mask.rank));
    const head = chart(series(all));
    if (!rows.length) {
      root.innerHTML = head + '<p class="mai-note">这些筛选下没有成绩。</p>';
      bind();
      return;
    }
    root.innerHTML = head + stats(all) +
      '<div class="mai-cards">' + bests(rows).map(row).join('') + '</div>';
    bind();
  }

  function bind() {
    root.querySelectorAll('.mai-filters button').forEach((b) => {
      b.onclick = () => {
        if (b.dataset.diff !== undefined) mask.diff = b.dataset.diff;
        if (b.dataset.rank !== undefined) mask.rank = b.dataset.rank;
        render();
      };
    });
  }

  fetch('records.json', { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error('no records.json'))))
    .then((d) => {
      all = Array.isArray(d) ? d : (d.records || []);
      if (!all.length) {
        root.innerHTML = '<p class="mai-note">还没有识别到成绩。手机连上 ADB 跑一次 mai-sync，' +
          '或者把成绩图丢进 X99 的 ~/maimai-ocr/incoming/。</p>';
        return;
      }
      render();
    })
    .catch(() => {
      root.innerHTML = '<p class="mai-note">读不到 records.json —— 在 X99 上跑 ' +
        '<code>python maimai.py all</code> 再 <code>python scripts/sitegen.py --pull</code>。</p>';
    });
})();
