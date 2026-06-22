/* Shared Brand Spectrometer "spectrum strip" renderer.
 * Used by spectrometer.html (the tool) AND how-to-read.html (the teaching page) so the
 * two never drift. Pure: given a host element + atlas slice + detail level, it writes the
 * SVG and (optionally) a caption. No app state, no globals beyond what is passed in.
 *
 * Detail levels (additive supersets):
 *  -1 Origin   one number — the mean across every dimension & audience (how-to-read prelude only)
 *   0 Headline one consensus line per dimension (mean across audiences)
 *   1 Compare  + per-audience lines + the spread band
 *   2 Sentiment+ the valence dot on each line (−1 left … +1 right)        [needs valence]
 *             (at level 4 the dot becomes a horizontal distribution "cloud",
 *              widest by valence_spread, densest at the valence point)
 *   3 Resolve  + a 95% CI halo per line                                    [needs ci_95]
 *   4 Cloud    + emission strength as line weight                          [needs emission]
 *
 * Graceful degradation: a channel renders only if its field is present in the data.
 */
(function (root) {
  "use strict";
  var SAFEHEX = /^#[0-9a-fA-F]{3,8}$/;
  function safeColor(c) { return (typeof c === "string" && SAFEHEX.test(c)) ? c : "#8b93a7"; }
  function escHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m];
    });
  }
  function median(a) {
    var s = a.slice().sort(function (x, y) { return x - y; }), m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function mean(a) { return a.reduce(function (x, y) { return x + y; }, 0) / Math.max(1, a.length); }

  /* opts = {host, captionEl?, dims, cohorts, level, hover?, captionText?, onTip?} */
  function render(opts) {
    var host = opts.host, dims = opts.dims || [], cohorts = opts.cohorts || [];
    var level = opts.level, hover = opts.hover || null;
    var W = 820, H = 420, top = 18, padB = 72;
    var n = dims.length, laneGap = 8, laneW = (W - (n - 1) * laneGap) / n;
    var plotTop = top, plotH = H - top - padB;
    var y = function (v) { return plotTop + (1 - v / 10) * plotH; };
    var xL = function (lx) { return lx + laneW * 0.16; };
    var xR = function (lx) { return lx + laneW * 0.84; };
    var vx = function (lx, val) { var c = (xL(lx) + xR(lx)) / 2, h = (xR(lx) - xL(lx)) / 2; return c + h * Math.max(-1, Math.min(1, val)); };
    var hasVal = cohorts.some(function (c) { return Array.isArray(c.valence) && c.valence.length === n; });
    var hasCI = cohorts.some(function (c) { return Array.isArray(c.ci_95) && c.ci_95.length === n; });
    var hasEmis = cohorts.some(function (c) { return Array.isArray(c.emission) && c.emission.length === n; });
    var hasVspread = cohorts.some(function (c) { return Array.isArray(c.valence_spread) && c.valence_spread.length === n; });

    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Brand spectrum strip">';
    var g;
    for (g = 0; g <= 10; g += 2) {
      s += '<line x1="0" y1="' + y(g) + '" x2="' + W + '" y2="' + y(g) + '" stroke="#1f2430" stroke-width="1"/>'
        + '<text x="2" y="' + (y(g) - 3) + '" font-size="9" fill="#5a6273">' + g + '</text>';
    }

    if (level <= -1) {
      // ORIGIN: one monolithic background, one line at the grand mean — the single-number world.
      var consensus = dims.map(function (d, di) { return mean(cohorts.map(function (c) { return c.vector[di]; })); });
      var gm = mean(consensus);
      s += '<rect x="0" y="' + plotTop + '" width="' + W + '" height="' + plotH + '" fill="#8b93a7" opacity="0.06" rx="6"/>';
      s += '<line class="cohline" x1="' + (W * 0.04) + '" y1="' + y(gm) + '" x2="' + (W * 0.96) + '" y2="' + y(gm)
        + '" stroke="#cfd4e2" stroke-width="3" opacity="0.9" data-tip="One number: ' + gm.toFixed(1) + ' (mean across all dimensions and audiences)"/>';
      s += '<text x="' + (W / 2) + '" y="' + (y(gm) - 9) + '" font-size="11" fill="#cfd4e2" text-anchor="middle" font-weight="600">one number — ' + gm.toFixed(1) + '</text>';
      s += '<text x="' + (W / 2) + '" y="' + (H - padB + 22) + '" font-size="10.5" fill="#5a6273" text-anchor="middle">a single brand-health score — every dimension and audience averaged into one</text>';
      s += "</svg>";
      finish(host, s, opts);
      caption(opts, level, opts.captionText || "one number — the average across every dimension and audience; it hides everything below. Turn the dial up...");
      return;
    }

    dims.forEach(function (d, di) {
      var lx = di * (laneW + laneGap), cx = lx + laneW / 2, col = safeColor(d.color);
      s += '<rect x="' + lx + '" y="' + plotTop + '" width="' + laneW + '" height="' + plotH + '" fill="' + col + '" opacity="0.07" rx="6"/>';
      var vals = cohorts.map(function (c) { return c.vector[di]; }); if (!vals.length) vals.push(0);
      var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), cen = mean(vals);
      if (level >= 1 && cohorts.length >= 2) {
        s += '<rect class="band" x="' + (lx + laneW * 0.30).toFixed(1) + '" y="' + y(mx).toFixed(1) + '" width="' + (laneW * 0.40).toFixed(1) + '" height="' + (y(mn) - y(mx)).toFixed(1) + '" fill="' + col + '" opacity="0.26" rx="4"/>';
      }
      var rows = level >= 1 ? cohorts.map(function (c) {
        return { c: c, score: c.vector[di], val: (hasVal && c.valence) ? c.valence[di] : null,
                 vsp: (hasVspread && c.valence_spread) ? c.valence_spread[di] : null,
                 emis: (hasEmis && c.emission) ? c.emission[di] : null, ci: (hasCI && c.ci_95) ? c.ci_95[di] : null,
                 reflections: (Array.isArray(c.reflections) && c.reflections[di]) ? c.reflections[di] : null, cons: false };
      }) : [{ c: { label: "consensus", color: "#cfd4e2" }, score: cen, val: null, vsp: null, emis: null, ci: null, reflections: null, cons: true }];
      rows.forEach(function (r) {
        var cy = y(r.score), cc = safeColor(r.c.color);
        var dimmed = (hover && !r.cons && hover !== r.c.id) ? 0.2 : 1;
        if (level >= 3 && r.ci) {
          var lo = y(Math.min(10, r.ci[1])), hi = y(Math.max(0, r.ci[0]));
          s += '<rect class="cihalo" x="' + xL(lx).toFixed(1) + '" y="' + Math.min(lo, hi).toFixed(1) + '" width="' + (xR(lx) - xL(lx)).toFixed(1) + '" height="' + Math.abs(lo - hi).toFixed(1) + '" fill="' + cc + '" opacity="' + (0.12 * dimmed) + '" rx="2"/>';
        }
        if (level >= 4 && r.reflections && r.reflections.length) {
          var na = r.reflections.length;
          r.reflections.forEach(function (av, ai) {
            var gx = xL(lx) + (xR(lx) - xL(lx)) * (na > 1 ? ai / (na - 1) : 0.5);
            s += '<circle class="ghost" cx="' + gx.toFixed(1) + '" cy="' + y(av).toFixed(1) + '" r="1.6" fill="' + cc + '" opacity="' + (0.5 * dimmed) + '"/>';
          });
        }
        var w = (level >= 4 && r.emis != null) ? (1.2 + 2.6 * r.emis) : 2.4;
        var op = ((level >= 4 && r.emis != null) ? (0.35 + 0.5 * r.emis) : 0.55) * dimmed;
        s += '<line class="cohline" x1="' + xL(lx).toFixed(1) + '" y1="' + cy.toFixed(1) + '" x2="' + xR(lx).toFixed(1) + '" y2="' + cy.toFixed(1)
          + '" stroke="' + cc + '" stroke-width="' + w.toFixed(1) + '" opacity="' + op.toFixed(2) + '" data-tip="' + escHtml(r.c.label) + ' · ' + escHtml(d.label) + ': ' + r.score.toFixed(1) + '"/>';
        if (level >= 2 && r.val != null) {
          var vxp = vx(lx, r.val);
          var vtip = escHtml(r.c.label) + ' · ' + escHtml(d.label) + ' valence: ' + (r.val > 0 ? "+" : "") + r.val.toFixed(2);
          if (level >= 4) {
            // valence shown as a horizontal distribution "cloud", densest at the valence
            // point and stretched along the line by its spread (overlap across cohorts is fine)
            var sp = (r.vsp != null) ? Math.max(0, Math.min(1, r.vsp)) : 0.4;
            var rxB = Math.min((xR(lx) - xL(lx)) / 2 * (0.18 + 0.82 * sp), vxp - xL(lx), xR(lx) - vxp);
            rxB = Math.max(rxB, 2.5);
            [[1.0, 0.11], [0.6, 0.17], [0.32, 0.28]].forEach(function (L) {
              s += '<ellipse class="vcloud" cx="' + vxp.toFixed(1) + '" cy="' + cy.toFixed(1) + '" rx="' + (rxB * L[0]).toFixed(1) + '" ry="4" fill="' + cc + '" opacity="' + (L[1] * dimmed).toFixed(2) + '" data-tip="' + vtip + ' (distribution)"/>';
            });
            s += '<circle class="vcore" cx="' + vxp.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="2" fill="' + cc + '" opacity="' + (0.6 * dimmed).toFixed(2) + '" data-tip="' + vtip + ' (peak)"/>';
          } else {
            s += '<circle class="vdot" cx="' + vxp.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="3.2" fill="' + cc + '" opacity="' + dimmed + '" data-tip="' + vtip + '"/>';
          }
        }
      });
      if (level >= 2 && hasVal) {
        s += '<g class="vaxis"><line x1="' + cx + '" y1="' + plotTop + '" x2="' + cx + '" y2="' + (plotTop + plotH) + '" stroke="#ffffff" stroke-width="1" opacity="0.08" stroke-dasharray="2 4"/>'
          + '<text x="' + xL(lx).toFixed(1) + '" y="' + (H - padB + 34) + '" font-size="8" fill="#5a6273" text-anchor="middle">−1</text>'
          + '<text x="' + cx + '" y="' + (H - padB + 34) + '" font-size="8" fill="#5a6273" text-anchor="middle">0</text>'
          + '<text x="' + xR(lx).toFixed(1) + '" y="' + (H - padB + 34) + '" font-size="8" fill="#5a6273" text-anchor="middle">+1</text></g>';
      }
      s += '<text x="' + cx + '" y="' + (H - padB + 18) + '" font-size="10.5" fill="#cdd3e0" text-anchor="middle" font-weight="600">' + escHtml(String(d.label).slice(0, 4)) + '</text>';
    });
    s += "</svg>";
    finish(host, s, opts);
    caption(opts, level, opts.captionText);
  }

  function finish(host, s, opts) {
    host.innerHTML = s;
    var svg = host.querySelector("svg");
    if (svg && opts.onTip) {
      svg.addEventListener("mousemove", function (ev) {
        var t = ev.target.getAttribute && ev.target.getAttribute("data-tip");
        if (t) opts.onTip(ev, t); else opts.onTip(null);
      });
      svg.addEventListener("mouseleave", function () { opts.onTip(null); });
    }
  }
  function caption(opts, level, text) {
    if (!(opts.captionEl && text)) return;
    var t = "This view: " + text;
    if (!/[.!?…]$/.test(t)) t += ".";
    opts.captionEl.textContent = t;
  }

  root.renderSpectrumStrip = render;
  root.spectrumHelpers = { safeColor: safeColor, escHtml: escHtml, median: median, mean: mean };
})(typeof window !== "undefined" ? window : this);
