(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  var runCache = {};

  function loadRun(path) {
    if (runCache[path]) return Promise.resolve(runCache[path]);
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (data) {
      runCache[path] = data;
      return data;
    });
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function plantLabel(state, plant) {
    var labels = (state.catalog && state.catalog.plant_labels) || {};
    var info = labels[plant];
    if (!info) return plant;
    return info.long_name || info.short_name || plant;
  }

  function agentLabel(state, agent) {
    var labels = (state.catalog && state.catalog.agent_labels) || {};
    var info = labels[agent];
    if (!info) return agent;
    return info.long_name || info.short_name || agent;
  }

  function iterationStatus(rec) {
    var parts = [];
    if (rec.it.is_best) parts.push("🏆 best");
    if (rec.it.is_first_feasible) parts.push("⛳ first-feasible");
    if (!parts.length) parts.push(rec.it.feasible ? "feasible" : "infeasible");
    return parts.join(", ");
  }

  function hoverHeader(state, rec, signalKind, channel) {
    var lines = [
      "<b>Setup:</b> " + escapeHTML(plantLabel(state, rec.plant)),
      "<b>Agent:</b> " + escapeHTML(agentLabel(state, rec.agent)),
      "<b>Attempt:</b> " + escapeHTML(RE.state.attemptLabel(rec.attempt)),
      "<b>Iteration:</b> " + escapeHTML(String(rec.it.iteration_num)),
      "<b>Controller:</b> " + escapeHTML(rec.it.controller_basename || ("run" + rec.it.run_index)),
      "<b>Status:</b> " + escapeHTML(iterationStatus(rec)),
      "<b>Objective:</b> " + escapeHTML(rec.it.objective === null ? "inf" : RE.sidebar.formatObjective(rec.it.objective)),
      "<b>Signal:</b> " + escapeHTML(signalKind + (channel && channel !== "__scalar__" ? " [" + channel + "]" : "")),
    ];
    return lines.join("<br>");
  }

  function channelsFromRun(run) {
    if (run.meas && typeof run.meas === "object" && !Array.isArray(run.meas)) {
      return Object.keys(run.meas).sort();
    }
    return ["__scalar__"];
  }

  function getChannelTrace(signal, channel) {
    if (signal === null) return null;
    if (Array.isArray(signal)) {
      return channel === "__scalar__" ? signal : null;
    }
    return signal[channel] || null;
  }

  function visibleSelected(state) {
    var sel = state.selection.iteration;
    var records = RE.state.visibleIterationRecords();
    return records.filter(function (rec) {
      var key = RE.state.iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index);
      return sel.multiSet.has(key);
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

  function render(state) {
    var plotDiv = document.getElementById("tab-d-plot");
    if (!plotDiv) return;

    var selected = visibleSelected(state);
    if (!selected.length) {
      showMessage(plotDiv, '<div style="padding:30px;color:#64748b;">No iterations selected. Click rows in the iteration table to enable.</div>');
      return;
    }

    // Group by attempt for rainbow ordering
    var groupOrder = {};
    selected.forEach(function (rec) {
      var ak = rec.plant + "||" + rec.agent + "||" + rec.attempt;
      (groupOrder[ak] = groupOrder[ak] || []).push(rec);
    });
    Object.keys(groupOrder).forEach(function (ak) {
      groupOrder[ak].sort(function (a, b) { return a.it.run_index - b.it.run_index; });
    });

    // Only show "Loading…" when there is no existing Plotly figure to keep
    // visible — clobbering the div with innerHTML would corrupt Plotly's
    // internal state and the subsequent Plotly.react() call would silently
    // fail to render.
    if (!plotDiv._fullLayout) {
      plotDiv.innerHTML = '<div style="padding:20px;color:#64748b;">Loading…</div>';
    }

    var promises = selected.map(function (rec) {
      return loadRun(rec.it.run_file).then(function (run) {
        return { rec: rec, run: run };
      });
    });
    Promise.all(promises).then(function (loaded) {
      buildFigure(plotDiv, loaded, groupOrder, state);
    }).catch(function (err) {
      showMessage(plotDiv, '<div style="padding:20px;color:#b00020;">Failed to load runs: ' + escapeHTML(err.message) + '</div>');
    });
  }

  function buildFigure(plotDiv, loaded, groupOrder, state) {
    // Collect all channels across loaded runs
    var allChannels = {};
    loaded.forEach(function (entry) {
      channelsFromRun(entry.run).forEach(function (c) { allChannels[c] = true; });
    });
    var channels = Object.keys(allChannels);
    if (channels.indexOf("__scalar__") < 0 && channels.length > 1) {
      // multichannel ordering
      channels.sort();
    }
    // Subplot layout: top is response (with 1+ y-axes), bottom is control
    var traces = [];
    var layout = {
      template: "plotly_white",
      xaxis: { domain: [0, 1], anchor: "y2", title: "time (s)" },
      yaxis: { domain: [0.36, 1.0], anchor: "x", title: "Step response" },
      yaxis2: { domain: [0, 0.28], anchor: "x", title: "Control" },
      hovermode: "closest",
      margin: { l: 60, r: 60, t: 30, b: 50 },
      showlegend: false,
    };

    // Multi-y-axis support for multichannel plants
    var channelAxis = {};
    channels.forEach(function (ch, idx) {
      if (idx === 0) {
        channelAxis[ch] = "y";
        layout.yaxis.title = "Step response" + (ch === "__scalar__" ? "" : " [" + ch + "]");
      } else {
        var num = idx + 2; // y3, y4, ...
        channelAxis[ch] = "y" + num;
        layout["yaxis" + num] = {
          title: "Step response [" + ch + "]",
          overlaying: "y",
          side: idx % 2 === 0 ? "left" : "right",
          domain: [0.36, 1.0],
        };
      }
    });

    loaded.forEach(function (entry) {
      var rec = entry.rec, run = entry.run;
      var order = RE.state.attemptIterationOrder(rec.plant, rec.agent, rec.attempt, rec.it.run_index);
      var color = RE.colors.iterationColor(
        rec.plant, rec.agent, rec.attempt,
        order.index,
        order.total,
        !!state.filters.rainbowColors
      );
      var legendName = rec.plant + "/att" + rec.attempt + "/it" + rec.it.iteration_num;
      var groupId = "iter-" + rec.it.run_index + "-" + rec.attempt + "-" + rec.agent + "-" + rec.plant;
      var time = run.time_sec;

      var runChannels = channelsFromRun(run);
      runChannels.forEach(function (ch, ci) {
        var meas = getChannelTrace(run.meas, ch);
        var ref = getChannelTrace(run.ref, ch);
        if (!meas) return;
        var axis = channelAxis[ch] || "y";
        var measHover = hoverHeader(state, rec, "Measurement", ch);
        traces.push({
          type: "scatter",
          mode: "lines",
          name: legendName + (ch !== "__scalar__" ? " [" + ch + "]" : ""),
          legendgroup: groupId,
          showlegend: ci === 0,
          x: time,
          y: meas,
          line: { color: color, width: 2 },
          yaxis: axis,
          xaxis: "x",
          hovertemplate:
            measHover + "<br><b>Time:</b> %{x:.4f} s<br><b>Value:</b> %{y:.4f}<extra></extra>",
        });
        if (ref) {
          var refHover = hoverHeader(state, rec, "Reference", ch);
          traces.push({
            type: "scatter",
            mode: "lines",
            name: legendName + " ref",
            legendgroup: groupId,
            showlegend: false,
            x: time,
            y: ref,
            line: { color: color, width: 1, dash: "dash" },
            yaxis: axis,
            xaxis: "x",
            hovertemplate: refHover + "<br><b>Time:</b> %{x:.4f} s<br><b>Value:</b> %{y:.4f}<extra></extra>",
          });
        }
      });

      if (run.control) {
        var controlHover = hoverHeader(state, rec, "Control", null);
        traces.push({
          type: "scatter",
          mode: "lines",
          name: legendName + " u",
          legendgroup: groupId,
          showlegend: false,
          x: time,
          y: run.control,
          line: { color: color, width: 1.5 },
          yaxis: "y2",
          xaxis: "x",
          hovertemplate: controlHover + "<br><b>Time:</b> %{x:.4f} s<br><b>Value:</b> %{y:.4f}<extra></extra>",
        });
      }
    });

    if (plotDiv._fullLayout) {
      Plotly.react(plotDiv, traces, layout, { responsive: true, displaylogo: false });
    } else {
      Plotly.newPlot(plotDiv, traces, layout, { responsive: true, displaylogo: false });
    }
  }

  RE.tabs = RE.tabs || {};
  RE.tabs.D = { render: render };
})();
