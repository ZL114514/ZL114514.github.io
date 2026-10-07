/* TG 风格 emoji reaction（计数走 X99 的 /reactions/api，按浏览器去重）
   只显示有计数的表情；想投别的点 ＋ 打开选择面板。表情一律用本地 Noto Emoji 图
   （/assets/emoji/<codepoint>.png，图缺失时自动退回字体字形）。 */
(function () {
  "use strict";
  var API = "https://www.maimaidx-net.top/reactions/api";
  var ALL = ["👍", "❤", "😁", "🔥", "🥰", "😢", "🍌", "🤯", "😭", "🌚", "🤪", "👎", "😨",
             "🙊", "🤓", "😱", "🤔", "😈", "🤬", "👾", "👏", "🤩", "😇", "🌭", "👀"];
  var STORE = "zl-tg-rx";
  var TOTALS = {};

  function votedMap() {
    try { return JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { return {}; }
  }
  function setVoted(id, emoji, on) {
    var m = votedMap();
    m[id] = m[id] || {};
    if (on) { m[id][emoji] = 1; } else { delete m[id][emoji]; }
    try { localStorage.setItem(STORE, JSON.stringify(m)); } catch (e) { /* 隐私模式 */ }
  }

  function fileOf(em) {                     // 👍 -> /assets/emoji/1f44d.png
    var cps = [];
    for (var i = 0; i < em.length; i++) {
      var cu = em.codePointAt(i);
      if (cu > 0xffff) { i++; }             // 跳过代理对的低位
      if (cu === 0xfe0f) { continue; }      // 变体选择符不进文件名
      cps.push(cu.toString(16));
    }
    return "/assets/emoji/" + cps.join("-") + ".png";
  }

  function icon(em) {
    var img = document.createElement("img");
    img.className = "tg-rx-img";
    img.alt = em;
    img.loading = "lazy";
    img.addEventListener("error", function () {
      var s = document.createElement("span");
      s.className = "tg-rx-e";
      s.textContent = em;
      if (img.parentNode) { img.parentNode.replaceChild(s, img); }
    });
    img.src = fileOf(em);
    return img;
  }

  function makeBtn(el, id, em, on) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "tg-rx-btn" + (on ? " on" : "");
    b.title = "点一下表态（同一浏览器只计一次，可取消）";
    b.appendChild(icon(em));
    var n = (TOTALS[id] || {})[em] || 0;
    if (n > 0) {
      var s = document.createElement("span");
      s.className = "tg-rx-n";
      s.textContent = n;
      b.appendChild(s);
    }
    b.addEventListener("click", function () { vote(el, id, em, on); });
    return b;
  }

  function plusEl(el, id, shown) {
    var wrap = document.createElement("span");
    wrap.className = "tg-rx-add";
    var b = document.createElement("button");
    b.type = "button";
    b.className = "tg-rx-btn tg-rx-plus";
    b.title = "添加表情";
    b.textContent = "＋";
    var panel = document.createElement("span");
    panel.className = "tg-rx-panel";
    panel.hidden = true;
    ALL.forEach(function (em) {
      if (shown.indexOf(em) >= 0) { return; }      // 已经显示的不重复给
      var pb = document.createElement("button");
      pb.type = "button";
      pb.className = "tg-rx-btn";
      pb.title = em;
      pb.appendChild(icon(em));
      pb.addEventListener("click", function (ev) {
        ev.stopPropagation();
        panel.hidden = true;
        vote(el, id, em, false);
      });
      panel.appendChild(pb);
    });
    b.addEventListener("click", function (ev) {
      ev.stopPropagation();
      panel.hidden = !panel.hidden;
      wrap.classList.toggle("open", !panel.hidden);   // 面板开着时 hover 样式别把它藏了
    });
    wrap.appendChild(b);
    wrap.appendChild(panel);
    return wrap;
  }

  function render(el) {
    var id = el.getAttribute("data-post");
    var mine = votedMap()[id] || {};
    var have = TOTALS[id] || {};
    var shown = ALL.filter(function (em) { return (have[em] || 0) > 0 || mine[em]; });
    Object.keys(have).forEach(function (em) {      // 服务端存的冷门表情也照显
      if (have[em] > 0 && shown.indexOf(em) < 0) { shown.push(em); }
    });
    el.textContent = "";
    shown.forEach(function (em) { el.appendChild(makeBtn(el, id, em, !!mine[em])); });
    el.appendChild(plusEl(el, id, shown));
    el.setAttribute("data-ready", "1");
  }

  function vote(el, id, em, on) {
    fetch(API + "/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id, emoji: em, delta: on ? -1 : 1 })
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || !j.ok) { throw new Error((j && j.error) || "fail"); }
      TOTALS[id] = TOTALS[id] || {};
      if (j.count > 0) { TOTALS[id][em] = j.count; } else { delete TOTALS[id][em]; }
      setVoted(id, em, !on);
      render(el);                                  // 归 0 的按钮自动消失、新加的自动出现
    }).catch(function () {
      if (el.parentNode && !el.parentNode.querySelector(".tg-rx-tip")) {
        var tip = document.createElement("p");
        tip.className = "tg-rx-tip";
        tip.textContent = "投票失败：计数服务不可达（网络或服务问题）。";
        el.parentNode.insertBefore(tip, el.nextSibling);
      }
    });
  }

  function init() {
    var els = document.querySelectorAll(".tg-rx[data-post]");
    if (!els.length) { return; }
    fetch(API + "/totals").then(function (r) { return r.json(); }).then(function (j) {
      TOTALS = (j && j.totals) || {};
      Array.prototype.forEach.call(els, render);
    }).catch(function () {
      TOTALS = {};
      Array.prototype.forEach.call(els, render);
      var first = els[0];
      if (first.parentNode && !first.parentNode.querySelector(".tg-rx-tip")) {
        var tip = document.createElement("p");
        tip.className = "tg-rx-tip";
        tip.textContent = "reaction 计数服务暂时不可达，按钮只显示本地状态。";
        first.parentNode.insertBefore(tip, first.nextSibling);
      }
    });
  }

  // 点空白处收起表情面板（全站只注册一次）
  document.addEventListener("click", function (ev) {
    var panels = document.querySelectorAll(".tg-rx-panel");
    for (var i = 0; i < panels.length; i++) {
      var p = panels[i];
      if (!p.hidden && p.parentNode && !p.parentNode.contains(ev.target)) {
        p.hidden = true;
        if (p.parentNode.classList) { p.parentNode.classList.remove("open"); }
      }
    }
  });

  // /notes/ 的连贯加载追加出来的条目要重新渲染一遍
  document.addEventListener("zl:tl-appended", init);

  // Material 的 instant loading 不会重发 DOMContentLoaded，要挂 document$
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
