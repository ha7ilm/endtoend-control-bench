(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  var clickBound = false;

  function cumulativeMin(iterations) {
    var best = Infinity;
    return iterations.map(function (it) {
      var obj = it.objective;
      if (it.feasible && obj !== null && obj !== undefined && isFinite(obj)) {
        if (obj < best) best = obj;
      }
      return isFinite(best) ? best : null;
    });
  }

  function groupRecordsByAttempt(records) {
    var map = {};
    records.forEach(function (rec) {
      var key = rec.plant + "||" + rec.agent + "||" + rec.attempt;
      if (!map[key]) map[key] = { plant: rec.plant, agent: rec.agent, attempt: rec.attempt, items: [] };
      map[key].items.push(rec.it);
    });
    Object.keys(map).forEach(function (k) {
      map[k].items.sort(function (a, b) { return a.run_index - b.run_index; });
    });
    return Object.keys(map).sort().map(function (k) { return map[k]; });
  }

  function plantLabel(state, plant) {
    var labels = (state.catalog && state.catalog.plant_labels) || {};
    var info = labels[plant];
    return info && info.short_name ? info.short_name : plant;
  }

  function agentLabel(state, agent) {
    var labels = (state.catalog && state.catalog.agent_labels) || {};
    var info = labels[agent];
    return info && info.short_name ? info.short_name : agent;
  }

  function attemptLabel(attempt) {
    return RE.state.attemptLabel(attempt);
  }

  function groupHeader(state, g) {
    return plantLabel(state, g.plant) + " · " + agentLabel(state, g.agent) + " · " + attemptLabel(g.attempt);
  }

  function legendLabel(state, g) {
    return agentLabel(state, g.agent) + " · " + attemptLabel(g.attempt);
  }

  function hoverText(state, g, it, cumValue) {
    var lines = [
      "<b>" + escapeHTML(groupHeader(state, g)) + "</b>",
      "(🖱️ click to view step response)",
      "Iteration: " + it.iteration_num,
      "Objective: " + (it.objective === null ? "inf" : it.objective.toFixed(4)),
      "Cumulative min: " + (cumValue === null ? "n/a" : cumValue.toFixed(4)),
      "Feasible: " + it.feasible,
    ];
    if (it.why) lines.push("why: " + escapeHTML(it.why));
    if (it.description) lines.push("desc: " + escapeHTML(it.description));
    return lines.join("<br>");
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function purgeIfPlot(div) {
    if (div && div._fullLayout && window.Plotly) {
      try { Plotly.purge(div); } catch (e) { /* ignore */ }
    }
  }

  function showMessage(div, html) {
    purgeIfPlot(div);
    div.innerHTML = html;
  }

  function formatConstraintNum(v) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    var abs = Math.abs(v);
    if (abs >= 100) return v.toFixed(0);
    if (abs >= 10) return v.toFixed(1);
    if (abs >= 1) return v.toFixed(2);
    if (abs >= 0.01) return v.toFixed(3);
    return v.toPrecision(2);
  }

  function constraintCellHTML(it) {
    var cs = it.constraints || [];
    if (!cs.length) return it.feasible ? '<span class="constraint-pass">yes</span>' : '<span class="constraint-fail">no</span>';
    return cs.map(function (c) {
      var val = formatConstraintNum(c.value);
      var marker = c.passed ? "✓" : "✗";
      var cls = c.passed ? "constraint-pass" : "constraint-fail";
      return '<div class="' + cls + '">' + escapeHTML(c.desc) + ' ' + val + ' ' + marker + '</div>';
    }).join("");
  }

  function feasibilityTooltip(it) {
    var lines = [it.feasible ? "feasible" : "infeasible"];
    (it.constraints || []).forEach(function (c) {
      var val = formatConstraintNum(c.value);
      lines.push(c.desc + ": " + val + " (limit " + c.limit + ") " + (c.passed ? "PASS" : "FAIL"));
    });
    return escapeHTML(lines.join("\n"));
  }

  function render(state) {
    var plotDiv = document.getElementById("tab-a-plot");
    var tableDiv = document.getElementById("tab-a-table");
    if (!plotDiv || !tableDiv) return;

    var records = RE.state.visibleIterationRecords();
    var groups = groupRecordsByAttempt(records);
    if (!groups.length) {
      showMessage(plotDiv, '<div style="padding:30px;color:#64748b;">No attempts selected.</div>');
      tableDiv.innerHTML = "";
      return;
    }

    var traces = [];
    var showActual = !!state.filters.showActualMarkers;
    groups.forEach(function (g) {
      var color = state.filters.colorLinesPerAgent
        ? RE.colors.agentColor(state, g.agent)
        : RE.colors.attemptColor(g.plant, g.agent, g.attempt);
      var legendName = legendLabel(state, g);
      var groupId = "att-" + g.plant + "-" + g.agent + "-" + g.attempt;
      var x = g.items.map(function (it) { return it.iteration_num; });
      var cums = cumulativeMin(g.items);
      var hover = g.items.map(function (it, idx) { return hoverText(state, g, it, cums[idx]); });
      var customdata = g.items.map(function (it) {
        return [g.plant, g.agent, g.attempt, it.run_index];
      });

      traces.push({
        type: "scatter",
        mode: "lines",
        name: legendName,
        legendgroup: groupId,
        x: x,
        y: cums,
        line: { color: color, width: 2 },
        hovertext: hover,
        hovertemplate: "%{hovertext}<extra></extra>",
        customdata: customdata,
        connectgaps: false,
      });

      if (showActual) {
        var feasX = [], feasY = [], feasHover = [], feasCD = [];
        var infX = [], infY = [], infHover = [], infCD = [];
        g.items.forEach(function (it, idx) {
          var obj = it.objective;
          if (obj === null || obj === undefined || !isFinite(obj)) return;
          var bucket = it.feasible
            ? { x: feasX, y: feasY, h: feasHover, c: feasCD }
            : { x: infX, y: infY, h: infHover, c: infCD };
          bucket.x.push(it.iteration_num);
          bucket.y.push(obj);
          bucket.h.push(hoverText(state, g, it, cums[idx]));
          bucket.c.push([g.plant, g.agent, g.attempt, it.run_index]);
        });
        if (feasX.length) {
          traces.push({
            type: "scatter",
            mode: "markers",
            name: legendName + " feasible",
            legendgroup: groupId,
            showlegend: false,
            x: feasX,
            y: feasY,
            marker: { color: color, symbol: "square", size: 7 },
            hovertext: feasHover,
            hovertemplate: "%{hovertext}<extra></extra>",
            customdata: feasCD,
          });
        }
        if (infX.length) {
          traces.push({
            type: "scatter",
            mode: "markers",
            name: legendName + " infeasible",
            legendgroup: groupId,
            showlegend: false,
            x: infX,
            y: infY,
            marker: { color: color, symbol: "x", size: 8 },
            hovertext: infHover,
            hovertemplate: "%{hovertext}<extra></extra>",
            customdata: infCD,
          });
        }
      }
    });

    var layout = {
      template: "plotly_white",
      margin: { l: 60, r: 20, t: 30, b: 50 },
      xaxis: { title: "Iteration" },
      yaxis: { title: "Objective (line: cumulative feasible minimum)", type: "log" },
      hovermode: "closest",
      legend: { orientation: "v" },
    };
    if (plotDiv._fullLayout) {
      Plotly.react(plotDiv, traces, layout, { responsive: true, displaylogo: false });
    } else {
      Plotly.newPlot(plotDiv, traces, layout, { responsive: true, displaylogo: false });
    }
    if (!clickBound) {
      plotDiv.on("plotly_click", function (ev) {
        var pts = ev.points || [];
        if (!pts.length) return;
        var cd = pts[0].customdata;
        if (!cd) return;
        RE.state.crossTabJump(cd[0], cd[1], cd[2], cd[3]);
      });
      clickBound = true;
    }

    renderTable(state, tableDiv, groups);
  }

  function renderTable(state, tableDiv, groups) {
    var tips = {
      markers: "🏆 marks the controller the agent selected in best.txt. ⛳ marks the first iteration that satisfied all design constraints.",
      setup: "The plant/setup used in the benchmark. The paper evaluates nine simulated control-design setups.",
      agent: "The coding agent used for this attempt, namely GPT-5.3 Codex or Claude Opus 4.6 in the paper.",
      attempt: "One of the independent design attempts given to an agent on the same setup.",
      iter: "The controller iteration number within the attempt. Agents were prompted to create a new controller_N.py for every evaluated controller.",
      file: "The controller script evaluated at this iteration.",
      obj: "The tuning objective value computed from the KPIs. Lower is better, and the plot shows the running best objective among only feasible controllers.",
      why: "The per-iteration reason written by the LLM. During design it starts with 'Design to meet specifications:', and during tuning it starts with 'Tuning:'.",
      description: "The per-iteration description written by the LLM, summarizing the controller idea or technique it claims to be using.",
    };
    var html = '<table class="progress-table"><thead><tr>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.markers) + '">&nbsp;</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.setup) + '">Setup</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.agent) + '">Agent</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.attempt) + '">Att</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.iter) + '">Iter</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.file) + '">File</span></th>' +
      '<th class="col-obj"><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.obj) + '">Obj</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.why) + '">Why</span></th>' +
      '<th><span class="has-tooltip" data-tooltip="' + escapeHTML(tips.description) + '">Description</span></th>' +
      '</tr></thead><tbody>';
    groups.forEach(function (g) {
      var plantTxt = plantLabel(state, g.plant);
      var agentTxt = agentLabel(state, g.agent);
      var attTxt = String(g.attempt + 1);
      g.items.forEach(function (it) {
        var marker = "";
        if (it.is_best) marker += '<span class="has-tooltip badge-best" data-tooltip="Best iteration in the attempt.">🏆</span>';
        if (it.is_first_feasible) marker += (marker ? " " : "") +
          '<span class="has-tooltip badge-first" data-tooltip="First feasible iteration in the attempt.">⛳</span>';
        var fileCell = "";
        if (it.controller_basename) {
          fileCell = '<a href="#" class="ctrl-link" data-plant="' + escapeHTML(g.plant) +
            '" data-agent="' + escapeHTML(g.agent) +
            '" data-attempt="' + g.attempt +
            '" data-run="' + it.run_index + '">' +
            escapeHTML(it.controller_basename) + '</a>';
        }
        html += "<tr>" +
          "<td>" + marker + "</td>" +
          "<td>" + escapeHTML(plantTxt) + "</td>" +
          "<td>" + escapeHTML(agentTxt) + "</td>" +
          "<td>" + escapeHTML(attTxt) + "</td>" +
          "<td>" + it.iteration_num + "</td>" +
          "<td>" + fileCell + "</td>" +
          '<td class="col-obj"><span class="has-tooltip ' + (it.feasible ? 'constraint-pass' : 'constraint-fail') +
          '" data-tooltip="' + feasibilityTooltip(it) + '">' +
          (it.objective === null ? "inf" : RE.sidebar.formatObjective(it.objective)) + "</span></td>" +
          "<td>" + escapeHTML(it.why || "") + "</td>" +
          "<td>" + escapeHTML(it.description || "") + "</td>" +
          "</tr>";
      });
    });
    html += "</tbody></table>";
    tableDiv.innerHTML = html;

    tableDiv.querySelectorAll("a.ctrl-link").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        RE.state.crossTabJump(
          a.dataset.plant,
          a.dataset.agent,
          parseInt(a.dataset.attempt, 10),
          parseInt(a.dataset.run, 10),
          "C"
        );
      });
    });
  }

  RE.tabs = RE.tabs || {};
  RE.tabs.A = { render: render };
})();
