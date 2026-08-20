(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  var sourceCache = {};
  var renderNonce = 0;

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function loadSource(path) {
    if (sourceCache[path]) return Promise.resolve(sourceCache[path]);
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    }).then(function (text) {
      sourceCache[path] = text;
      return text;
    });
  }

  function resetHighlight(codeEl) {
    codeEl.removeAttribute("data-highlighted");
    codeEl.classList.remove("hljs");
    codeEl.innerHTML = "";
  }

  function renderHeading(rec) {
    var div = document.getElementById("tab-c-heading");
    if (!div) return;
    var title = (rec.it.why || rec.it.controller_basename || "Controller").trim();
    var subtitle = (rec.it.description || "").trim();
    var html = '<div class="code-title">' + escapeHTML(title) + "</div>";
    if (subtitle) {
      html += '<div class="code-subtitle">' + escapeHTML(subtitle) + "</div>";
    }
    html += '<div class="code-caption">(as described by the LLM in the "why" and "description" arguments)</div>';
    div.innerHTML = html;
  }

  function renderMeta(state, rec) {
    var div = document.getElementById("tab-c-meta");
    if (!div) return;
    var it = rec.it;
    var pLabels = (state.catalog && state.catalog.plant_labels) || {};
    var aLabels = (state.catalog && state.catalog.agent_labels) || {};
    var plantTxt = (pLabels[rec.plant] && pLabels[rec.plant].short_name) || rec.plant;
    var agentTxt = (aLabels[rec.agent] && aLabels[rec.agent].short_name) || rec.agent;
    var rows = [
      ["Plant", plantTxt + " (" + rec.plant + ")"],
      ["Agent", agentTxt + " (" + rec.agent + ")"],
      ["Attempt", RE.state.attemptLabel(rec.attempt)],
      ["Iteration", String(it.iteration_num)],
      ["Controller", it.controller_basename || "n/a"],
      ["Objective", it.objective === null ? "inf" : RE.sidebar.formatObjective(it.objective)],
      ["Feasible", it.feasible ? "yes" : "no"],
      ["🏆 best", it.is_best ? "yes" : "no"],
      ["⛳ first feasible", it.is_first_feasible ? "yes" : "no"],
    ];
    var html = '<h3>Iteration metadata</h3><table class="meta-table"><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      html += "<tr><td><b>" + escapeHTML(r[0]) + "</b></td><td>" + escapeHTML(r[1]) + "</td></tr>";
    });
    html += '</tbody></table><h3 style="margin-top:10px;">Constraints</h3><table class="meta-table"><thead><tr><th>Constraint</th><th>Value</th><th>Status</th></tr></thead><tbody>';
    (it.constraints || []).forEach(function (c) {
      var cls = c.passed ? "constraint-pass" : "constraint-fail";
      var val = c.value === null || c.value === undefined ? "n/a" : (typeof c.value === "number" ? c.value.toPrecision(6) : c.value);
      html += '<tr><td>' + escapeHTML(c.desc) + '</td><td>' + escapeHTML(String(val)) +
        '</td><td class="' + cls + '">' + (c.passed ? "PASS" : "FAIL") + '</td></tr>';
    });
    html += "</tbody></table>";
    div.innerHTML = html;
  }

  function render(state) {
    var codeEl = document.getElementById("tab-c-code");
    if (!codeEl) return;
    var rec = RE.state.singleIterationRecord();
    if (!rec) {
      var heading = document.getElementById("tab-c-heading");
      if (heading) heading.innerHTML = "";
      resetHighlight(codeEl);
      codeEl.textContent = "No iteration selected.";
      var meta = document.getElementById("tab-c-meta");
      if (meta) meta.innerHTML = "";
      return;
    }
    renderHeading(rec);
    renderMeta(state, rec);
    var path = rec.it.controller_file;
    if (!path) {
      resetHighlight(codeEl);
      codeEl.textContent = "No controller source available for this iteration.";
      return;
    }
    var nonce = ++renderNonce;
    resetHighlight(codeEl);
    codeEl.textContent = "Loading…";
    loadSource(path).then(function (text) {
      if (nonce !== renderNonce) return;
      resetHighlight(codeEl);
      codeEl.textContent = text;
      if (window.hljs) {
        try { window.hljs.highlightElement(codeEl); } catch (e) {}
      }
    }).catch(function (err) {
      if (nonce !== renderNonce) return;
      resetHighlight(codeEl);
      codeEl.textContent = "Failed to load source: " + err.message;
    });
  }

  RE.tabs = RE.tabs || {};
  RE.tabs.C = { render: render };
})();
