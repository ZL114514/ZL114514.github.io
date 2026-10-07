// Arcaea 成绩库 —— 纯前端,读同目录 records.json
(function () {
  const root = document.getElementById('arc');
  if (!root) return;

  const esc = (s) =>
    String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const GRADE_ORDER = ['PURE MEMORY', 'EX+', 'EX', 'AA', 'A', 'B', 'C', 'D'];
  const fmt = (n) => (n == null ? '—' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "'"));

  const WEEK_JP = ['日', '月', '火', '水', '木', '金', '土'];

  // 评级图标用 APK 拆包出来的原图（PURE MEMORY 是 P 灯，不是字母评级）
  const GRADE_IMG = { 'PURE MEMORY': 'pure', 'EX+': 'explus', 'EX': 'ex',
                      'AA': 'aa', 'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd' };
  const gradeHTML = (g) => (GRADE_IMG[g]
    ? '<img class="arc-grade" data-g="' + esc(g) + '" src="/assets/grade/' + GRADE_IMG[g] +
      '.png" alt="' + esc(g) + '" loading="lazy">'
    : '');

  let all = [];      // deduped, one entry per song
  let view = 'time'; // time（时间线，默认）| song（按曲目去重）| log（全部记录）
  let q = '', set = '', grade = '', sort = 'score';

  // 成绩库的时间线：碎碎念里识别出来的带日期；早期批量识别的没日期，另起一组
  function dayLabel(d) {
    const w = WEEK_JP[new Date(d + 'T00:00:00').getDay()] || '';
    return { day: d.slice(8, 10), label: d.slice(0, 7) + ' · ' + w };
  }

  function timeRow(r) {
    const img = r.jacket
      ? '<img class="arc-tl-jk" loading="lazy" src="jackets/' + esc(r.jacket) + '" alt="">'
      : '<div class="arc-ph arc-tl-jk"></div>';
    const src = r.from_url
      ? '<a class="arc-tag" href="' + esc(r.from_url) + '">' + esc(r.from || '碎碎念') + '</a>'
      : (r.from ? '<span class="arc-tag">' + esc(r.from) + '</span>' : '');
    return (
      '<div class="arc-tl-item">' + img +
      '<div class="arc-meta">' +
      '<div class="arc-title">' + esc(r.title) + '</div>' +
      '<div class="arc-sub">' + esc(r.artist) + '</div>' +
      '<div class="arc-tags">' + src +
      (r.set ? '<span class="arc-tag">' + esc(r.set) + '</span>' : '') + '</div>' +
      '</div>' +
      '<div class="arc-score">' +
      '<div class="arc-num">' + esc(fmt(r.score)) + '</div>' +
      gradeHTML(r.grade) +
      '</div></div>'
    );
  }

  function paintTime(rows) {
    const dated = rows.filter((r) => r.date).sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const undated = rows.filter((r) => !r.date).sort((a, b) => b.score - a.score);
    const days = [];
    dated.forEach((r) => {
      const d = String(r.date).slice(0, 10);
      const last = days[days.length - 1];
      if (!last || last.d !== d) { days.push({ d: d, items: [r] }); } else { last.items.push(r); }
    });
    if (!days.length && !undated.length) { return '<p class="arc-empty">没有匹配的记录</p>'; }
    let out = '<div class="arc-tl">';
    days.forEach((g) => {
      const lb = dayLabel(g.d);
      out += '<div class="arc-tl-day"><div class="arc-tl-date"><b>' + esc(lb.day) + '</b><span>' +
             esc(lb.label) + '</span></div><div class="arc-tl-items">' +
             g.items.map(timeRow).join('') + '</div></div>';
    });
    if (undated.length) {
      out += '<div class="arc-tl-day"><div class="arc-tl-date"><b>—</b><span>无日期</span></div>' +
             '<div class="arc-tl-items"><p class="arc-sub">曲库存档（早期批量识别，没记日期）</p>' +
             undated.map(timeRow).join('') + '</div></div>';
    }
    return out + '</div>';
  }

  // 两张数据源：records.json（早期批量识别）+ records-notes.json（碎碎念里识别出来的）
  const SOURCES = ['records.json', 'records-notes.json'];
  const pick = (f) =>
    fetch(f, { cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : []))
      .catch(() => []);

  function load() {
    root.innerHTML = '<p class="arc-empty">正在加载成绩数据…</p>';
    Promise.all(SOURCES.map(pick))
      .then((parts) => {
        const raw = parts.reduce((a, b) => a.concat(b), []);
        const ok = raw.filter((x) => x.song_ok && x.score_ok);
        all = dedupe(ok);
        buildControls(ok, all);
        render(ok, all);
      })
      .catch((e) => {
        root.innerHTML = '<p class="arc-empty">数据加载失败:' + esc(e.message) + '</p>';
      });
  }

  // one row per song: best score wins, plays counted
  function dedupe(rows) {
    const by = new Map();
    for (const r of rows) {
      const cur = by.get(r.song_id);
      if (!cur) {
        by.set(r.song_id, Object.assign({}, r, { plays: 1 }));
      } else {
        cur.plays += 1;
        if (r.score > cur.score) Object.assign(cur, r, { plays: cur.plays });
      }
    }
    return [...by.values()];
  }

  function buildControls(rows, songs) {
    const sets = [...new Set(rows.map((r) => r.set).filter(Boolean))].sort();
    const grades = GRADE_ORDER.filter((g) => rows.some((r) => r.grade === g));
    const scores = rows.map((r) => r.score);
    const stats = [
      ['记录', rows.length],
      ['曲目', songs.length],
      ['最高分', Math.max(...scores)],
      ['曲包', sets.length],
    ];
    const dist = grades
      .map((g) => g + ' ' + rows.filter((r) => r.grade === g).length)
      .join(' · ');

    root.innerHTML =
      '<div class="arc-panel">' +
      stats
        .map(
          ([k, v]) =>
            '<div class="arc-stat"><b>' + esc(fmt(v)) + '</b><span>' + esc(k) + '</span></div>'
        )
        .join('') +
      '</div>' +
      '<p class="arc-sub" style="margin:-.5rem 0 1rem">评级分布:' + esc(dist) + '</p>' +
      '<div class="arc-ctl">' +
      '<input id="arc-q" type="search" placeholder="搜索曲名 / 曲师 / 曲包" autocomplete="off">' +
      '<select id="arc-set"><option value="">全部曲包</option>' +
      sets.map((s) => '<option value="' + esc(s) + '">' + esc(s) + '</option>').join('') +
      '</select>' +
      '<select id="arc-grade"><option value="">全部评级</option>' +
      grades.map((g) => '<option value="' + esc(g) + '">' + esc(g) + '</option>').join('') +
      '</select>' +
      '<select id="arc-sort">' +
      '<option value="score">按分数</option>' +
      '<option value="title">按曲名</option>' +
      '<option value="grade">按评级</option>' +
      '</select>' +
      '<span class="arc-views">' +
      '<button type="button" data-view="time">时间线</button>' +
      '<button type="button" data-view="song">按曲目</button>' +
      '<button type="button" data-view="log">全部记录</button>' +
      '</span>' +
      '<a class="arc-official" href="https://arcaea.lowiro.com/zh/profile/" target="_blank" rel="noopener">官方档案 ↗</a>' +
      '</div>' +
      '<div class="arc-list" id="arc-list"></div>';

    root.querySelector('#arc-q').addEventListener('input', (e) => { q = e.target.value.trim().toLowerCase(); paint(rows, songs); });
    root.querySelector('#arc-set').addEventListener('change', (e) => { set = e.target.value; paint(rows, songs); });
    root.querySelector('#arc-grade').addEventListener('change', (e) => { grade = e.target.value; paint(rows, songs); });
    root.querySelector('#arc-sort').addEventListener('change', (e) => { sort = e.target.value; paint(rows, songs); });
    root.querySelector('.arc-views').addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-view]');
      if (!btn) { return; }
      view = btn.getAttribute('data-view');
      [].forEach.call(root.querySelectorAll('.arc-views button'), (b) => {
        b.classList.toggle('on', b === btn);
      });
      paint(rows, songs);
    });
    [].forEach.call(root.querySelectorAll('.arc-views button'), (b) => {
      b.classList.toggle('on', b.getAttribute('data-view') === view);
    });
  }

  function render(rows, songs) {
    paint(rows, songs);
  }

  function paint(rows, songs) {
    const source = view === 'song' ? songs : rows;
    let out = source.filter((r) => {
      if (set && r.set !== set) return false;
      if (grade && r.grade !== grade) return false;
      if (q) {
        const hay = [r.title, r.artist, r.set, r.song_id].join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    const list = root.querySelector('#arc-list');
    if (view === 'time') {
      list.innerHTML = paintTime(out);      // 时间线按日期分组，不再走下面的排序
      return;
    }
    out.sort((a, b) => {
      if (sort === 'title') return String(a.title).localeCompare(String(b.title));
      if (sort === 'grade') return GRADE_ORDER.indexOf(a.grade) - GRADE_ORDER.indexOf(b.grade) || b.score - a.score;
      return b.score - a.score;
    });
    if (!out.length) {
      list.innerHTML = '<p class="arc-empty">没有匹配的记录</p>';
      return;
    }
    list.innerHTML = out.map(card).join('');
  }

  function card(r) {
    const img = r.jacket
      ? '<img loading="lazy" src="jackets/' + esc(r.jacket) + '" alt="">'
      : '<div class="arc-ph"></div>';
    const tags = [
      r.set && '<span class="arc-tag">' + esc(r.set) + '</span>',
      r.plays > 1 && '<span class="arc-tag">' + r.plays + ' 次</span>',
      r.layout && '<span class="arc-tag">' + esc(r.layout) + '</span>',
    ].filter(Boolean).join('');
    return (
      '<div class="arc-row">' +
      img +
      '<div class="arc-meta">' +
      '<div class="arc-title">' + esc(r.title) + '</div>' +
      '<div class="arc-sub">' + esc(r.artist) + '</div>' +
      '<div class="arc-tags">' + tags + '</div>' +
      '</div>' +
      '<div class="arc-score">' +
      '<div class="arc-num">' + esc(fmt(r.score)) + '</div>' +
      gradeHTML(r.grade) +
      '</div>' +
      '</div>'
    );
  }

  load();
})();
