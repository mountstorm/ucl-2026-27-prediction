/* UCL 2026-27 odds site. Reads window.UCL (data.js, written by build_site.py). */
(function () {
  "use strict";
  var D = window.UCL, CLUBS = window.CLUBS, DISPLAY = window.DISPLAY;
  var app = document.getElementById("app");
  var tip = document.getElementById("tip");

  var STAGES = [
    { k: "champion", tab: "Winner", ask: "win the Champions League", short: "Win" },
    { k: "final", tab: "Final", ask: "reach the final in Madrid", short: "Final" },
    { k: "sf", tab: "Semis", ask: "reach the semi-finals", short: "SF" },
    { k: "qf", tab: "Quarters", ask: "reach the quarter-finals", short: "QF" },
    { k: "r16", tab: "Last 16", ask: "reach the last 16", short: "Last 16" },
    { k: "top8", tab: "Top 8", ask: "finish top 8 (straight to the last 16)", short: "Top 8" },
    { k: "top24", tab: "Top 24", ask: "finish top 24 (survive the league phase)", short: "Top 24" },
  ];
  var LADDER = ["top24", "top8", "r16", "qf", "sf", "final", "champion"];
  var stageOf = function (k) { return STAGES.filter(function (s) { return s.k === k; })[0]; };

  var byName = {};
  D.teams.forEach(function (t) { byName[t.name] = t; });
  var state = { stage: "champion", team: null, all: false };
  state.team = sorted("champion")[0].name;

  // ---------------------------------------------------------------- helpers
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function nm(n) { return DISPLAY[n] || n; }
  function club(n) { return CLUBS[n] || ["---", "#888888", "#cccccc"]; }
  function lum(hex) {
    var c = hex.replace("#", ""), rgb = [0, 2, 4].map(function (i) {
      var v = parseInt(c.substr(i, 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
  }
  function contrast(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function cssVar(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  // The club color that stays visible on the current card surface (white kits fall back to the trim color).
  function inkFor(n) {
    var c = club(n), surf = cssVar("--card") || "#f4f4f5";
    if (contrast(c[1], surf) >= 2.2) return c[1];
    if (contrast(c[2], surf) >= 2.2) return c[2];
    return cssVar("--text");
  }
  function chip(n, size) {
    var c = club(n), fg = lum(c[1]) > 0.4 ? "#000" : "#fff";
    return '<span class="chip' + (size ? " " + size : "") + '" style="--c1:' + c[1] + ";--c2:" + c[2] + ";color:" + fg + '" aria-hidden="true">' + (size === "sm" ? "" : c[0]) + "</span>";
  }
  function pct(p) {
    if (p <= 0) return "0%";
    if (p < 0.001) return "<0.1%";
    if (p > 0.999 && p < 1) return ">99.9%";
    return (100 * p).toFixed(1) + "%";
  }
  function cents(p) { var c = Math.round(100 * p); return c < 1 && p > 0 ? "<1¢" : (c > 99 && p < 1 ? "99¢" : c + "¢"); }
  function ord(n) { var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function delta(arr, from) {
    var d = 100 * (arr[arr.length - 1] - arr[from == null ? arr.length - 2 : from]);
    if (Math.abs(d) < 0.05) return '<span class="delta flat">–</span>';
    return '<span class="delta ' + (d > 0 ? "up" : "down") + '">' + (d > 0 ? "▲" : "▼") + " " + Math.abs(d).toFixed(1) + "</span>";
  }
  function sorted(stage) {
    return D.teams.slice().sort(function (a, b) { return b.probs[stage] - a.probs[stage] || a.avg_position - b.avg_position; });
  }
  function mdLabel(i) { return i === 0 ? "Start" : "MD" + i; }
  function showTip(html, ev) {
    tip.innerHTML = html; tip.hidden = false;
    var x = ev.clientX + 14, y = ev.clientY + 14, w = tip.offsetWidth, h = tip.offsetHeight;
    if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
    if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.hidden = true; }
  function niceMax(v) {
    var steps = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.4, 0.5, 0.6, 0.8, 1];
    for (var i = 0; i < steps.length; i++) if (v <= steps[i]) return steps[i];
    return 1;
  }

  // ---------------------------------------------------------------- render
  function render() {
    var fav = sorted("champion")[0];
    var fin = D.finals[0];
    var movers = D.teams.slice().sort(function (a, b) {
      return (b.history.top8[D.through_md] - b.history.top8[0]) - (a.history.top8[D.through_md] - a.history.top8[0]);
    });
    var mv = movers[0];
    var played = D.n_played;
    var locks = D.teams.filter(function (t) { return t.probs.top8 >= 0.9; }).sort(function (a, b) { return b.probs.top8 - a.probs.top8; });

    document.getElementById("livePill").textContent = "Live from " + ((D.source && D.source.source) || "results") + " · after matchday " + D.through_md + " · " +
      new Date(D.updated + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

    var h = "";
    h += '<section class="hero"><div>' +
      '<div class="kicker">Who wins the 2026-27 Champions League?</div>' +
      "<h1>" + esc(nm(fav.name)) + '<span class="dim">.</span></h1>' +
      '<p class="lede">The favourite after matchday ' + D.through_md + ", from <b>" + D.n_sims.toLocaleString() +
      " simulated seasons</b>. Every real result so far is locked in, and ratings update after each game.</p></div>" +
      '<div class="hero-fig">' + chip(fav.name, "lg") + '<div><div class="v">' + (100 * fav.probs.champion).toFixed(1) + "<small>%</small></div>" +
      delta(fav.history.champion, 0) + ' <span class="kicker">since the start</span></div></div></section>';

    h += '<section class="tiles">' +
      tile("Near-certain top 8", locks.length + (locks.length === 1 ? " club" : " clubs"), locks.map(function (t) { return club(t.name)[0] + " " + pct(t.probs.top8); }).join(" · ") || "none at 90% yet") +
      tile("Most likely final", club(fin.a)[0] + " v " + club(fin.b)[0], pct(fin.p) + " · Metropolitano, 5 June 2027") +
      tile("Biggest mover, top-8 odds", nm(mv.name), pct(mv.history.top8[0]) + " → " + pct(mv.probs.top8)) +
      tile("Games played", played + " / 144", "league phase · " + (D.teams.length) + " clubs") +
      "</section>";

    h += '<nav class="seg" aria-label="Choose market">' + STAGES.map(function (s) {
      return '<button type="button" data-stage="' + s.k + '" aria-pressed="' + (s.k === state.stage) + '">' + s.tab + "</button>";
    }).join("") + "</nav>";

    h += '<div class="grid2"><section class="card" id="marketCard"></section><section class="card sticky" id="detail"></section></div>';

    h += '<div class="grid3"><section class="card" id="finalsCard"></section><section class="card" id="tableCard"></section></div>';

    h += '<section class="how">' +
      how("Ratings", "Every club starts from a hand-set strength rating for autumn 2026, built from recent European results, league form and squad quality.") +
      how("Goals", "The rating gap and home advantage give each side's expected goals. Scores come from a Poisson model with the Dixon-Coles fix, so 0-0 and 1-1 happen as often as they should.") +
      how("Learning", "Ratings move Elo-style after every match (K = 20, bigger moves for bigger margins). Real results are replayed first, then form carries on inside each simulated season.") +
      how("Format", "36-team league phase, the 9th-24th play-off, a fixed bracket and the final in Madrid, all played " + D.n_sims.toLocaleString() + " times.") +
      "</section>";

    app.innerHTML = h;
    renderMarket(); renderDetail(); renderFinals(); renderTable();
  }

  function tile(l, v, s) { return '<div class="tile"><div class="lbl">' + l + '</div><div class="val">' + esc(v) + '</div><div class="sub">' + esc(s) + "</div></div>"; }
  function how(t, p) { return '<div class="card"><h3>' + t + "</h3><p>" + p + "</p></div>"; }

  function renderMarket() {
    var s = stageOf(state.stage), list = sorted(state.stage), show = state.all ? list : list.slice(0, 12);
    var h = '<div class="card-h"><div><h2>Who will ' + esc(s.ask) + "?</h2><p>Chance now · change since matchday " + (D.through_md - 1) + "</p></div></div>";
    h += '<ul class="market">' + show.map(function (t, i) {
      var p = t.probs[state.stage];
      return '<li><button type="button" class="mrow" data-team="' + esc(t.name) + '" aria-current="' + (t.name === state.team) + '">' +
        '<span class="rk">' + (i + 1) + "</span>" + chip(t.name) +
        '<span style="min-width:0"><div class="nm">' + esc(nm(t.name)) + '</div><div class="meta">' + t.pts + " pts · " + ord(t.table_pos) + " · " + t.w + "-" + t.d + "-" + t.l + "</div></span>" +
        '<span class="pct"><b>' + pct(p) + "</b>" + delta(t.history[state.stage]) + "</span>" +
        '<span class="yn" aria-hidden="true"><span class="y">Yes<b>' + cents(p) + '</b></span><span class="n">No<b>' + cents(1 - p) + "</b></span></span>" +
        "</button></li>";
    }).join("") + "</ul>";
    if (list.length > 12) h += '<button type="button" class="showall" id="showAll">' + (state.all ? "Show top 12" : "Show all " + list.length + " clubs") + "</button>";
    document.getElementById("marketCard").innerHTML = h;
  }

  function renderDetail() {
    var t = byName[state.team], s = stageOf(state.stage), ink = inkFor(t.name), hist = t.history[state.stage];
    var h = '<div class="dhead">' + chip(t.name, "lg") + "<div><h2>" + esc(nm(t.name)) + "</h2><p>" +
      t.country + " · Pot " + t.pot + " · " + ord(t.table_pos) + " on " + t.pts + " pts · rating " + Math.round(t.rating_pre) + " → " + Math.round(t.rating_now) + "</p></div></div>";
    h += '<div class="big-read"><span class="v">' + pct(t.probs[state.stage]) + '</span><span class="d">to ' + esc(s.ask) + "</span> " + delta(hist, 0) + "</div>";
    h += '<div class="sub-h">Chance after each matchday</div><div class="chart" id="lineChart"></div>';
    h += '<div class="sub-h">Road to Madrid</div><div class="ladder">' + LADDER.map(function (k) {
      var p = t.probs[k];
      return '<div class="lrow"><span class="l">' + stageOf(k).short + '</span><span class="t"><span class="f" style="display:block;width:' + (100 * p).toFixed(1) + "%;background:" + ink + '"></span></span><span class="v">' + pct(p) + "</span></div>";
    }).join("") + "</div>";
    h += '<div class="sub-h">Where they finish the league phase</div><div class="chart" id="posChart"></div>' +
      '<div class="zkey"><span><i style="background:var(--zone-a)"></i>1st-8th: last 16</span><span><i style="background:var(--zone-b)"></i>9th-24th: play-off</span><span><i style="background:var(--zone-c)"></i>25th-36th: out</span></div>';
    h += '<div class="sub-h">League phase games</div><ul class="games">' + t.games.map(function (g) { return gameRow(g, ink); }).join("") + "</ul>";
    document.getElementById("detail").innerHTML = h;
    lineChart(document.getElementById("lineChart"), hist, ink);
    posChart(document.getElementById("posChart"), t.pos_hist);
  }

  function gameRow(g, ink) {
    var right;
    if (g.gf != null) {
      var r = g.gf > g.ga ? "W" : g.gf < g.ga ? "L" : "D";
      right = '<span class="res"><i class="' + r + '">' + r + "</i>" + g.gf + "-" + g.ga + "</span>";
    } else {
      right = '<span class="wdl"><span class="seg3"><span style="width:' + (100 * g.pw) + "%;background:" + ink + '"></span><span style="width:' + (100 * g.pd) + '%;background:var(--grid)"></span><span style="width:' + (100 * g.pl) + '%;background:var(--text-3)"></span></span>' +
        "<small>W " + Math.round(100 * g.pw) + " · D " + Math.round(100 * g.pd) + " · L " + Math.round(100 * g.pl) + "</small></span>";
    }
    return '<li class="game"><span class="md">MD' + g.md + "</span>" + chip(g.opp, "sm") + '<span class="op">' + (g.home ? "" : "@ ") + esc(nm(g.opp)) + "<small>" + (g.home ? "home" : "away") + "</small></span>" + right + "</li>";
  }

  // Single-series line: chance after each matchday, with crosshair tooltip.
  function lineChart(el, vals, ink) {
    var W = Math.max(280, el.clientWidth), H = 190, L = 40, R = 52, T = 12, B = 26;
    var max = niceMax(Math.max.apply(null, vals) * 1.12 || 0.01);
    var x = function (i) { return L + (W - L - R) * (vals.length === 1 ? 0.5 : i / (vals.length - 1)); };
    var y = function (v) { return T + (H - T - B) * (1 - v / max); };
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="Chance after each matchday: ' +
      vals.map(function (v, i) { return mdLabel(i) + " " + pct(v); }).join(", ") + '">';
    for (var k = 0; k <= 4; k++) {
      var v = max * k / 4, yy = y(v);
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + yy + '" y2="' + yy + '" stroke="var(--grid)" stroke-width="1"/>';
      s += '<text x="' + (L - 8) + '" y="' + (yy + 4) + '" text-anchor="end">' + Math.round(100 * v) + "%</text>";
    }
    vals.forEach(function (_, i) { s += '<text x="' + x(i) + '" y="' + (H - 6) + '" text-anchor="middle">' + mdLabel(i) + "</text>"; });
    var pts = vals.map(function (v, i) { return x(i) + "," + y(v); });
    s += '<path d="M' + x(0) + "," + y(0) + " L" + pts.join(" L") + " L" + x(vals.length - 1) + "," + y(0) + ' Z" fill="' + ink + '" opacity="0.1"/>';
    s += '<polyline points="' + pts.join(" ") + '" fill="none" stroke="' + ink + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
    var li = vals.length - 1;
    s += '<circle cx="' + x(li) + '" cy="' + y(vals[li]) + '" r="4.5" fill="' + ink + '" stroke="var(--card)" stroke-width="2"/>';
    s += '<text class="lab" x="' + (x(li) + 9) + '" y="' + (y(vals[li]) + 4) + '">' + pct(vals[li]) + "</text>";
    s += '<g class="hov" style="display:none"><line y1="' + T + '" y2="' + (H - B) + '" stroke="var(--text-3)" stroke-width="1"/><circle r="5" fill="' + ink + '" stroke="var(--card)" stroke-width="2"/></g>';
    s += '<rect x="' + L + '" y="0" width="' + (W - L - R + 20) + '" height="' + H + '" fill="transparent"/></svg>';
    el.innerHTML = s;
    var svg = el.firstChild, hov = svg.querySelector(".hov"), line = hov.firstChild, dot = hov.lastChild;
    function at(ev) {
      var r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * (W / r.width);
      var i = Math.max(0, Math.min(li, Math.round((px - L) / ((W - L - R) / Math.max(1, li)))));
      hov.style.display = ""; line.setAttribute("x1", x(i)); line.setAttribute("x2", x(i));
      dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(vals[i]));
      var d = i > 0 ? 100 * (vals[i] - vals[i - 1]) : null;
      showTip("<b>" + (i === 0 ? "Before matchday 1" : "After matchday " + i) + "</b><br>" + pct(vals[i]) +
        (d != null ? " (" + (d >= 0 ? "+" : "−") + Math.abs(d).toFixed(1) + " pts)" : ""), ev);
    }
    svg.addEventListener("mousemove", at);
    svg.addEventListener("mouseleave", function () { hov.style.display = "none"; hideTip(); });
  }

  // 36 columns: share of simulations finishing in each league position.
  function posChart(el, hist) {
    var W = Math.max(280, el.clientWidth), H = 130, L = 4, R = 4, T = 8, B = 22;
    var slot = (W - L - R) / 36, bw = Math.min(24, slot - 2), max = Math.max.apply(null, hist) || 1;
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="League position distribution">';
    s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + (H - B) + '" y2="' + (H - B) + '" stroke="var(--grid)" stroke-width="1"/>';
    hist.forEach(function (p, i) {
      var hgt = (H - T - B) * p / max, x0 = L + slot * i + (slot - bw) / 2, y0 = H - B - hgt;
      var col = i < 8 ? "var(--zone-a)" : i < 24 ? "var(--zone-b)" : "var(--zone-c)";
      if (hgt > 0.5) {
        var r = Math.min(4, hgt, bw / 2);
        s += '<path d="M' + x0 + "," + (H - B) + " V" + (y0 + r) + " Q" + x0 + "," + y0 + " " + (x0 + r) + "," + y0 + " H" + (x0 + bw - r) + " Q" + (x0 + bw) + "," + y0 + " " + (x0 + bw) + "," + (y0 + r) + " V" + (H - B) + ' Z" fill="' + col + '"/>';
      }
      s += '<rect class="hit" data-i="' + i + '" x="' + (L + slot * i) + '" y="' + T + '" width="' + slot + '" height="' + (H - T - B + 4) + '" fill="transparent"/>';
    });
    [1, 8, 24, 36].forEach(function (n) {
      s += '<text x="' + (L + slot * (n - 0.5)) + '" y="' + (H - 6) + '" text-anchor="middle">' + n + "</text>";
    });
    el.innerHTML = s + "</svg>";
    el.querySelectorAll(".hit").forEach(function (r) {
      r.addEventListener("mousemove", function (ev) {
        var i = +r.getAttribute("data-i");
        showTip("<b>Finishes " + ord(i + 1) + "</b><br>" + pct(hist[i]) + " of simulations", ev);
      });
      r.addEventListener("mouseleave", hideTip);
    });
  }

  function renderFinals() {
    var h = '<div class="card-h"><div><h2>Most likely finals</h2><p>Metropolitano, Madrid · 5 June 2027</p></div></div><ul class="finals">';
    h += D.finals.slice(0, 8).map(function (f) {
      return '<li><span class="pair">' + chip(f.a, "sm") + chip(f.b, "sm") + '</span><span class="who">' + esc(nm(f.a)) + " v " + esc(nm(f.b)) + "</span><b>" + pct(f.p) + "</b></li>";
    }).join("") + "</ul>";
    document.getElementById("finalsCard").innerHTML = h;
  }

  function renderTable() {
    var rows = D.teams.slice().sort(function (a, b) { return a.table_pos - b.table_pos; });
    var src = D.source || {}, when = src.fetched_at ? new Date(src.fetched_at.replace("Z", ":00Z")).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : null;
    var srcTxt = src.url ? 'Results from <a href="' + esc(src.url) + '" target="_blank" rel="noopener">' + esc(src.source) + "</a>" + (when ? ", fetched " + when : "") : "Results entered by hand";
    var h = '<div class="card-h"><div><h2>League phase table</h2><p>Real standings after matchday ' + D.through_md + " · " + srcTxt + " · projected points and odds from the model</p></div></div>";
    h += '<div class="tbl-wrap"><table><thead><tr><th>#</th><th class="tm">Club</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th><th>Proj</th><th>Top 8</th><th>Win</th></tr></thead><tbody>';
    h += rows.map(function (t) {
      var gd = t.gf - t.ga, zc = t.table_pos <= 8 ? "var(--zone-a)" : t.table_pos <= 24 ? "var(--zone-b)" : "var(--zone-c)";
      return '<tr data-team="' + esc(t.name) + '"' + (t.table_pos === 8 || t.table_pos === 24 ? ' class="cut"' : "") + ">" +
        '<td><span class="zone" style="background:' + zc + '"></span>' + t.table_pos + '</td><td class="tm">' + chip(t.name, "sm") + esc(nm(t.name)) + "</td>" +
        "<td>" + t.p + "</td><td>" + t.w + "</td><td>" + t.d + "</td><td>" + t.l + "</td><td>" + (gd > 0 ? "+" : "") + gd + '</td><td class="pts">' + t.pts + "</td>" +
        "<td>" + t.avg_points.toFixed(1) + "</td><td>" + pct(t.probs.top8) + "</td><td>" + pct(t.probs.champion) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
    document.getElementById("tableCard").innerHTML = h;
  }

  // ---------------------------------------------------------------- events
  app.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-stage]");
    if (b) {
      state.stage = b.getAttribute("data-stage");
      app.querySelectorAll("[data-stage]").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
      renderMarket(); renderDetail(); return;
    }
    var r = ev.target.closest("[data-team]");
    if (r) {
      state.team = r.getAttribute("data-team");
      renderMarket(); renderDetail();
      if (r.tagName === "TR" || innerWidth <= 940) document.getElementById("detail").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (ev.target.id === "showAll") { state.all = !state.all; renderMarket(); }
  });

  document.getElementById("themeBtn").addEventListener("click", function () {
    var root = document.documentElement, cur = root.getAttribute("data-theme");
    var dark = cur ? cur === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    var next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("ucl.theme", next); } catch (e) {}
    renderMarket(); renderDetail(); renderFinals(); renderTable();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { renderDetail(); });

  var rt;
  addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(renderDetail, 120); });

  render();
})();
