/* 碎碎念页面上的「后台状态即时覆盖」。
   静态产物是按构建时的状态生成的；后台一改（隐藏 / 分享成博文 / 识别成绩），
   镜像上没必要等下次重建 —— 这里从 /content/api/state 读实时状态补一遍。
   GitHub Pages 那侧没有这个接口，fetch 失败就静默退出，页面照旧。 */
(function () {
  "use strict";
  var API = "https://www.maimaidx-net.top/content/api/state";

  function badge(el, cls, text) {
    var b = el.querySelector(".badge." + cls);
    if (b) { return b; }
    b = document.createElement("span");
    b.className = "badge " + cls;
    b.textContent = text;
    var head = el.querySelector(".tl-head");
    (head || el).insertBefore(b, (head || el).firstChild.nextSibling || null);
    return b;
  }

  function cards(records) {
    if (!records || !records.length) { return null; }
    var wrap = document.createElement("div");
    wrap.className = "arc-cards";
    var h = document.createElement("p");
    h.className = "arc-cards-head";
    h.textContent = "识别到的音游成绩";
    wrap.appendChild(h);
    records.forEach(function (r) {
      var a = document.createElement("a");
      a.className = "arc-card";
      a.target = "_blank";
      a.rel = "noopener";
      a.href = r.src || ("/record/jackets/" + (r.jacket || ""));
      if (r.jacket) {
        var img = document.createElement("img");
        img.loading = "lazy";
        img.alt = "";
        img.src = "/record/jackets/" + r.jacket;
        a.appendChild(img);
      }
      var meta = document.createElement("span");
      meta.className = "arc-cmeta";
      var b = document.createElement("b");
      b.textContent = r.title || r.song_id || "";
      var small = document.createElement("small");
      small.textContent = [r.artist, r.set].filter(Boolean).join(" · ");
      meta.appendChild(b);
      meta.appendChild(small);
      a.appendChild(meta);
      var num = document.createElement("span");
      num.className = "arc-cnum";
      num.textContent = r.score == null ? "—"
        : String(r.score).replace(/\B(?=(\d{3})+(?!\d))/g, "'");
      a.appendChild(num);
      if (r.grade) {
        var g = document.createElement("span");
        g.className = "arc-grade";
        g.textContent = r.grade;
        a.appendChild(g);
      }
      wrap.appendChild(a);
    });
    return wrap;
  }

  function mount(el, node) {
    var rx = el.querySelector(".tg-rx");
    if (rx && rx.parentNode === el) { el.insertBefore(node, rx); return; }
    el.appendChild(node);
  }

  function apply(state) {
    var posts = (state && state.posts) || {};
    var ids = Object.keys(posts);
    if (!ids.length) { return; }
    var seen = 0;

    // 时间线上的每一条
    document.querySelectorAll(".tl-item[data-post]").forEach(function (el) {
      var s = posts[el.getAttribute("data-post")];
      if (!s) { return; }
      seen++;
      if (s.hidden) { el.classList.add("is-hidden"); return; }
      if (s.type === "score") { badge(el, "b-score", "音游成绩"); }
      if (s.type === "post") { badge(el, "b-post", "已分享到博客"); }
      if (s.records && s.records.length && !el.querySelector(".arc-cards")) {
        var c = cards(s.records);
        if (c) { mount(el, c); }
      }
    });

    // 碎碎念单页（页面里只有一篇）
    var rx = document.querySelector(".tg-rx[data-post]");
    if (rx && !rx.closest(".tl-item")) {
      var id = rx.getAttribute("data-post");
      var s = posts[id];
      if (s) {
        seen++;
        if (s.records && s.records.length && !document.querySelector(".arc-cards")) {
          var c2 = cards(s.records);
          if (c2) { mount(rx.parentNode || document.body, c2); }
        }
      }
    }
    if (!seen) { return; }
  }

  var STATE = null;

  function init() {
    if (!document.querySelector('[data-post]')) { return; }
    fetch(API, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && j.ok) { STATE = j; apply(j); }
      })
      .catch(function () { /* 没有后端（GitHub Pages）或离线：静态产物已经是构建时的状态 */ });
  }

  // 连贯加载追加出来的条目的状态覆盖
  document.addEventListener("zl:tl-appended", function () { if (STATE) { apply(STATE); } });

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(init);        // Material 的 instant loading 不会重发 DOMContentLoaded
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();


/* /notes/ 的连贯加载：滚到「加载更早的碎碎念」就把上一个月的页面拿过来，
   抽出它 .tl 里的日期分组接到当前时间线末尾（重复的帖子按 data-post 去重）。
   月份/前后月的线索写在 .tl 的 data-* 上，所以不用第二份数据文件。
   静态站（GitHub Pages）上一样有效；禁 JS 时下面的「按月翻」列表兜底。 */
(function () {
  "use strict";
  var box = document.querySelector(".tl-next");
  if (!box) { return; }
  var seen = {};
  var loaded = 0;

  function look() {
    seen = {};
    var list = document.querySelectorAll(".tl-item[data-post]");
    for (var i = 0; i < list.length; i++) { seen[list[i].getAttribute("data-post")] = 1; }
  }

  function append(doc) {
    var src = doc.querySelector(".tl");
    var dst = document.querySelector(".tl");
    if (!src || !dst || src === dst) { return null; }
    var days = src.children, added = 0;
    for (var i = 0; i < days.length; i++) {
      var day = days[i];
      if (day.className.indexOf("tl-day") < 0) { continue; }
      var items = day.querySelectorAll(".tl-item[data-post]");
      var fresh = 0;
      for (var j = 0; j < items.length; j++) {
        var id = items[j].getAttribute("data-post");
        if (seen[id]) { items[j].parentNode.removeChild(items[j]); } else { seen[id] = 1; fresh++; }
      }
      if (fresh) { dst.appendChild(day); added += fresh; }
    }
    return { added: added, prev: src.getAttribute("data-prev") };
  }

  function fire() {
    document.dispatchEvent(new CustomEvent("zl:tl-appended"));
  }

  function label(txt) {
    var s = box.querySelector("span");
    if (s) { s.textContent = txt; }
  }

  function load() {
    if (box.getAttribute("data-busy")) { return; }
    var ym = box.getAttribute("data-next");
    if (!ym) { box.remove(); return; }
    box.setAttribute("data-busy", "1");
    box.classList.add("loading");
    fetch("/notes/" + ym + "/", { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) { throw new Error(String(r.status)); } return r.text(); })
      .then(function (html) {
        var res = append(new DOMParser().parseFromString(html, "text/html"));
        if (!res) { throw new Error("no tl"); }
        // added=0 是正常的：哨兵那个月的内容多半已经在上面的首屏里了，继续往更早走
        if (res.added) { loaded += res.added; fire(); }
        box.removeAttribute("data-busy");
        box.classList.remove("loading");
        if (res.prev) {
          box.setAttribute("data-next", res.prev);
          label("加载更早的碎碎念…");
          if (visible()) { load(); }            // 还没铺满一屏就继续接
        } else {
          box.remove();
        }
      })
      .catch(function () {
        box.removeAttribute("data-busy");
        box.classList.remove("loading");
        label("这里接不上（网络或没这个月）—— 用下面的「按月翻」");
      });
  }

  function visible() {
    var r = box.getBoundingClientRect();
    return r.top < (window.innerHeight || 800) + 300;
  }

  look();
  if (window.IntersectionObserver) {
    new IntersectionObserver(function (es) {
      for (var i = 0; i < es.length; i++) { if (es[i].isIntersecting) { load(); } }
    }, { rootMargin: "300px 0px" }).observe(box);
  } else {
    window.addEventListener("scroll", function () { if (visible()) { load(); } }, { passive: true });
  }
  box.addEventListener("click", load);
})();
