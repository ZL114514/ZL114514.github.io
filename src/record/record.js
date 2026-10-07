// Arcaea 成绩库 —— 纯前端,读同目录 records.json
(function () {
  const root = document.getElementById('arc');
  if (!root) return;

  const esc = (s) =>
    String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const GRADE_ORDER = ['PURE MEMORY', 'EX+', 'EX', 'AA', 'A', 'B', 'C', 'D'];
  const fmt = (n) => (n == null ? '—' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "'"));

  let all = [];      // deduped, one entry per song
  let view = 'song'; // song | log
  let q = '', set = '', grade = '', sort = 'score';

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
      '<button id="arc-view" type="button" aria-pressed="false">去重视图</button>' +
      '</div>' +
      '<div class="arc-list" id="arc-list"></div>';

    root.querySelector('#arc-q').addEventListener('input', (e) => { q = e.target.value.trim().toLowerCase(); paint(rows, songs); });
    root.querySelector('#arc-set').addEventListener('change', (e) => { set = e.target.value; paint(rows, songs); });
    root.querySelector('#arc-grade').addEventListener('change', (e) => { grade = e.target.value; paint(rows, songs); });
    root.querySelector('#arc-sort').addEventListener('change', (e) => { sort = e.target.value; paint(rows, songs); });
    root.querySelector('#arc-view').addEventListener('click', (e) => {
      view = view === 'song' ? 'log' : 'song';
      e.target.setAttribute('aria-pressed', view === 'song' ? 'false' : 'true');
      e.target.textContent = view === 'song' ? '去重视图' : '全部记录';
      paint(rows, songs);
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

    out.sort((a, b) => {
      if (sort === 'title') return String(a.title).localeCompare(String(b.title));
      if (sort === 'grade') return GRADE_ORDER.indexOf(a.grade) - GRADE_ORDER.indexOf(b.grade) || b.score - a.score;
      return b.score - a.score;
    });

    const list = root.querySelector('#arc-list');
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
      '<div class="arc-grade" data-g="' + esc(r.grade) + '">' + esc(r.grade) + '</div>' +
      '</div>' +
      '</div>'
    );
  }

  load();
})();
