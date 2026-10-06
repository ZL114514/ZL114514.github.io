/* TG 风格 emoji reaction（计数走 X99 的 /reactions/api，按浏览器去重） */
(function () {
  "use strict";
  var API = "https://www.maimaidx-net.top/reactions/api";
  var EMOJI = ["👍", "❤", "😁", "🔥", "🥰", "😢"];
  var STORE = "zl-tg-rx";

  function votedMap() {
    try { return JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { return {}; }
  }
  function setVoted(id, emoji, on) {
    var m = votedMap();
    m[id] = m[id] || {};
    if (on) { m[id][emoji] = 1; } else { delete m[id][emoji]; }
    try { localStorage.setItem(STORE, JSON.stringify(m)); } catch (e) { /* 隐私模式 */ }
  }

  function render(el, totals, voted) {
    var id = el.getAttribute("data-post");
    var mine = voted[id] || {};
    el.textContent = "";
    EMOJI.forEach(function (em) {
      var n = (totals[id] && totals[id][em]) || 0;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tg-rx-btn" + (mine[em] ? " on" : "");
      b.title = "点一下表态（同一浏览器只计一次，可取消）";
      var e1 = document.createElement("span");
      e1.className = "tg-rx-e";
      e1.textContent = em;
      var e2 = document.createElement("span");
      e2.className = "tg-rx-n";
      e2.textContent = n;
      b.appendChild(e1);
      b.appendChild(e2);
      b.addEventListener("click", function () { vote(id, em, b); });
      el.appendChild(b);
    });
    el.setAttribute("data-ready", "1");
  }

  function vote(id, em, btn) {
    var on = btn.classList.contains("on");
    btn.disabled = true;
    fetch(API + "/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id, emoji: em, delta: on ? -1 : 1 })
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || !j.ok) { throw new Error((j && j.error) || "fail"); }
      btn.querySelector(".tg-rx-n").textContent = j.count;
      btn.classList.toggle("on", !on);
      setVoted(id, em, !on);
    }).catch(function () {
      btn.title = "投票失败：服务不可达";
    }).then(function () { btn.disabled = false; });
  }

  function init() {
    var els = document.querySelectorAll(".tg-rx[data-post]");
    if (!els.length) { return; }
    fetch(API + "/totals").then(function (r) { return r.json(); }).then(function (j) {
      var totals = (j && j.totals) || {}, voted = votedMap();
      els.forEach(function (el) { render(el, totals, voted); });
    }).catch(function () {
      var voted = votedMap();
      els.forEach(function (el) { render(el, {}, voted); });
      var tip = document.createElement("p");
      tip.className = "tg-rx-tip";
      tip.textContent = "reaction 计数服务暂时不可达，按钮只显示本地状态。";
      els[0].parentNode.insertBefore(tip, els[0].nextSibling);
    });
  }

  // Material 的 instant loading 不会重发 DOMContentLoaded，要挂 document$
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
