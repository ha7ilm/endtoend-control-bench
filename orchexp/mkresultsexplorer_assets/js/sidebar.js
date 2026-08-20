(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});
  var iterationClickTimer = null;

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "dataset") Object.keys(attrs.dataset).forEach(function (dk) { e.dataset[dk] = attrs.dataset[dk]; });
      else if (k === "style") Object.assign(e.style, attrs.style);
      else if (k === "text") e.textContent = attrs.text;
      else if (k === "html") e.innerHTML = attrs.html;
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function isSingleSelectGroup(state, group) {
    return RE.state.isSingleSelectGroup(state.activeTab, group);
  }

  function isGroupVisible(state, group) {
    return RE.state.isGroupVisible(state.activeTab, group);
  }

  function isOptionButtonGroup(state, group) {
    return false;
  }

  function isSelectionGroup(group) {
    return group === "agent" || group === "plant" || group === "attempt" || group === "iteration";
  }

  function allItems(group, state) {
    if (group === "agent") return (state.catalog.agents || []).slice();
    if (group === "plant") return (state.catalog.plants || []).slice();
    if (group === "attempt") {
      var s = new Set();
      Object.keys(state.catalog.attempts_per_agent || {}).forEach(function (a) {
        (state.catalog.attempts_per_agent[a] || []).forEach(function (n) { s.add(n); });
      });
      return Array.from(s).sort(function (a, b) { return a - b; });
    }
    if (group === "iteration") {
      return RE.state.visibleIterationRecords().map(function (rec) {
        return RE.state.iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index);
      });
    }
    return [];
  }

  function selectAll(group, state) {
    var sel = state.selection[group];
    sel.multiSet = new Set(allItems(group, state));
    if (!sel.multiSet.has(sel.focus)) {
      var iter = sel.multiSet.values().next();
      sel.focus = iter.done ? null : iter.value;
    }
    RE.state.notify();
  }

  function selectNone(group, state) {
    state.selection[group].multiSet = new Set();
    RE.state.notify();
  }

  function resetVisibleIterationsForStepResponse(state) {
    if (state.activeTab !== "D") return;
    var sel = state.selection.iteration;
    var visibleKeys = RE.state.visibleIterationRecords().map(function (rec) {
      return RE.state.iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index);
    });
    sel.multiSet = new Set(visibleKeys);
    if (!sel.multiSet.has(sel.focus)) {
      sel.focus = visibleKeys.length ? visibleKeys[0] : null;
    }
  }

  function render(state) {
    if (!state.catalog) return;
    renderCollapsibles(state);
    renderList("agent", state, state.catalog.agents);
    renderList("plant", state, state.catalog.plants);
    renderAttempts(state);
    renderGraphSettings(state);
    renderIterations(state);
  }

  function renderCollapsibles(state) {
    document.querySelectorAll(".listbox").forEach(function (box) {
      var group = box.dataset.group;
      box.style.display = isGroupVisible(state, group) ? "" : "none";
      if (!isGroupVisible(state, group)) return;
      box.classList.toggle("collapsed", !!state.sidebarCollapsed[group]);

      var header = box.querySelector(".listbox-header");
      if (!header) return;
      var actions = header.querySelector(".listbox-actions");
      if (!actions) {
        actions = document.createElement("span");
        actions.className = "listbox-actions";
        header.appendChild(actions);
      }
      actions.innerHTML = "";
      if (group === "iteration" && state.activeTab !== "D") return;
      if (!isSelectionGroup(group)) return;

      if (!isSingleSelectGroup(state, group)) {
        actions.appendChild(document.createTextNode("select "));
        var aAll = document.createElement("a");
        aAll.href = "#";
        aAll.className = "select-link";
        aAll.textContent = "all";
        aAll.addEventListener("click", function (e) { e.preventDefault(); selectAll(group, state); });
        var aNone = document.createElement("a");
        aNone.href = "#";
        aNone.className = "select-link";
        aNone.textContent = "none";
        aNone.addEventListener("click", function (e) { e.preventDefault(); selectNone(group, state); });
        actions.appendChild(aAll);
        actions.appendChild(document.createTextNode(" · "));
        actions.appendChild(aNone);
      }
    });
    document.querySelectorAll(".collapse-btn").forEach(function (btn) {
      btn.onclick = function () {
        var g = btn.dataset.group;
        state.sidebarCollapsed[g] = !state.sidebarCollapsed[g];
        RE.state.notify();
      };
    });
  }

  function labelForItem(group, item, state) {
    if (group === "plant") {
      var pl = (state.catalog.plant_labels || {})[item];
      if (pl && pl.short_name && pl.short_name !== item) return { primary: pl.short_name, sub: item };
    } else if (group === "agent") {
      var al = (state.catalog.agent_labels || {})[item];
      if (al && al.short_name && al.short_name !== item) return { primary: al.short_name, sub: item };
    }
    return { primary: String(item), sub: null };
  }

  function buildLabelNode(info) {
    var lbl = document.createElement("label");
    if (info.sub) {
      var primary = document.createElement("div");
      primary.className = "row-primary";
      primary.textContent = info.primary;
      var sub = document.createElement("div");
      sub.className = "row-sub";
      sub.textContent = info.sub;
      lbl.appendChild(primary);
      lbl.appendChild(sub);
    } else {
      lbl.textContent = info.primary;
    }
    return lbl;
  }

  function bindRowLabel(row, input, labelNode) {
    if (!row || !input || !labelNode) return;
    var inputId = "sidebar-input-" + Math.random().toString(36).slice(2);
    input.id = inputId;
    labelNode.setAttribute("for", inputId);
    row.addEventListener("click", function (ev) {
      if (ev.target === input || (labelNode.contains && labelNode.contains(ev.target))) return;
      input.click();
    });
  }

  function renderList(group, state, items) {
    var box = document.querySelector('.listbox[data-group="' + group + '"]');
    if (!box) return;
    var body = box.querySelector(".listbox-body");
    body.innerHTML = "";
    body.classList.remove("option-button-list");

    var sel = state.selection[group];
    var single = isSingleSelectGroup(state, group);

    if (isOptionButtonGroup(state, group)) {
      body.classList.add("option-button-list");
      items.forEach(function (item) {
        var info = labelForItem(group, item, state);
        var btn = el("button", {
          class: "option-button" + (sel.focus === item ? " active" : ""),
          type: "button",
          text: info.primary,
        });
        if (info.sub) {
          btn.classList.add("has-tooltip");
          btn.dataset.tooltip = info.sub;
        }
        btn.addEventListener("click", function () {
          sel.focus = item;
          sel.multiSet = new Set([item]);
          RE.state.notify();
        });
        body.appendChild(btn);
      });
      return;
    }

    items.forEach(function (item) {
      var row = el("div", { class: "listbox-row" });
      var input = el("input", {
        type: single ? "radio" : "checkbox",
        name: "sidebar-" + group,
      });
      if (single) input.checked = (sel.focus === item);
      else input.checked = sel.multiSet.has(item);
      input.addEventListener("change", function () {
        if (single) {
          sel.focus = item;
          sel.multiSet = new Set([item]);
        } else {
          if (input.checked) sel.multiSet.add(item);
          else sel.multiSet.delete(item);
          if (sel.multiSet.size && !sel.multiSet.has(sel.focus)) sel.focus = sel.multiSet.values().next().value;
        }
        if (group === "agent" || group === "plant") {
          resetVisibleIterationsForStepResponse(state);
        }
        RE.state.notify();
      });
      var labelNode = buildLabelNode(labelForItem(group, item, state));
      bindRowLabel(row, input, labelNode);
      row.appendChild(input);
      row.appendChild(labelNode);
      body.appendChild(row);
    });
  }

  function renderAttempts(state) {
    var box = document.querySelector('.listbox[data-group="attempt"]');
    if (!box) return;
    var filterDiv = box.querySelector("#attempt-filters");
    var list = box.querySelector(".checklist");
    list.innerHTML = "";
    filterDiv.innerHTML = "";

    var attempts = new Set();
    Object.keys(state.catalog.attempts_per_agent || {}).forEach(function (a) {
      (state.catalog.attempts_per_agent[a] || []).forEach(function (n) { attempts.add(n); });
    });
    var sel = state.selection.attempt;
    var single = isSingleSelectGroup(state, "attempt");
    Array.from(attempts).sort(function (a, b) { return a - b; }).forEach(function (n) {
      var row = el("div", { class: "listbox-row" });
      var input = el("input", {
        type: single ? "radio" : "checkbox",
        name: "sidebar-attempt",
      });
      if (single) input.checked = sel.focus === n;
      else input.checked = sel.multiSet.has(n);
      input.addEventListener("change", function () {
        if (single) {
          sel.focus = n;
          sel.multiSet = new Set([n]);
        }
        else {
          if (input.checked) sel.multiSet.add(n);
          else sel.multiSet.delete(n);
          if (sel.multiSet.size && !sel.multiSet.has(sel.focus)) sel.focus = sel.multiSet.values().next().value;
        }
        resetVisibleIterationsForStepResponse(state);
        RE.state.notify();
      });
      var lbl = document.createElement("label");
      var primary = document.createElement("span");
      primary.className = "attempt-primary";
      primary.textContent = RE.state.attemptLabel(n);
      lbl.appendChild(primary);
      bindRowLabel(row, input, lbl);
      row.appendChild(input);
      row.appendChild(lbl);
      list.appendChild(row);
    });
  }

  function renderGraphSettings(state) {
    var box = document.querySelector('.listbox[data-group="graph-settings"]');
    if (!box) return;
    var filterDiv = box.querySelector("#graph-settings-filters");
    if (!filterDiv) return;
    filterDiv.innerHTML = "";
    if (state.activeTab !== "A") return;

    [
      {
        key: "showActualMarkers",
        label: "Markers for actual obj. value & feasibility",
        tip: "Show actual objective-value markers on top of the cumulative feasible minimum curves: green square for feasible, red cross for infeasible.",
      },
      {
        key: "colorLinesPerAgent",
        label: "Color lines per agent",
        tip: "Color attempt curves by agent identity instead of by attempt. Declared agent colors are used first, with automatic fallbacks for additional agents.",
      },
    ].forEach(function (item) {
      var lbl = document.createElement("label");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!state.filters[item.key];
      cb.addEventListener("change", function () {
        state.filters[item.key] = cb.checked;
        RE.state.notify();
      });
      lbl.appendChild(cb);
      lbl.appendChild(el("span", {
        class: "has-tooltip",
        "data-tooltip": item.tip,
        text: " " + item.label,
      }));
      filterDiv.appendChild(lbl);
    });
  }

  function renderIterations(state) {
    var box = document.querySelector('.listbox[data-group="iteration"]');
    if (!box) return;
    var filterDiv = box.querySelector("#iteration-filters");
    var wrap = box.querySelector(".iteration-table-wrap");
    wrap.innerHTML = "";
    filterDiv.innerHTML = "";

    if (!isGroupVisible(state, "iteration")) return;

    if (state.activeTab === "D") {
      var keepOnlyLine = el("div", { class: "iteration-keep-only-line" });
      keepOnlyLine.appendChild(document.createTextNode("Keep only "));
      [
        {
          key: "showBestOnly",
          icon: "🏆",
          label: "best",
          tip: "Best iteration in the attempt according to best.txt / matched controller selection.",
        },
        {
          key: "showFirstFeasibleOnly",
          icon: "⛳",
          label: "first-feasible",
          tip: "First iteration in the attempt that satisfies all design constraints.",
        },
      ].forEach(function (f, idx) {
        var optionLabel = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = !!state.filters[f.key];
        cb.addEventListener("change", function () {
          state.filters[f.key] = cb.checked;
          RE.state.notify();
        });
        optionLabel.appendChild(cb);
        optionLabel.appendChild(document.createTextNode(" "));
        optionLabel.appendChild(el("span", {
          class: "has-tooltip",
          "data-tooltip": f.tip,
          text: f.icon,
        }));
        optionLabel.appendChild(document.createTextNode(f.label === "first-feasible" ? f.label : " " + f.label));
        keepOnlyLine.appendChild(optionLabel);
        if (idx === 0) keepOnlyLine.appendChild(document.createTextNode(" and "));
      });
      filterDiv.appendChild(keepOnlyLine);

      var rainbowLabel = document.createElement("label");
      var rainbowCb = document.createElement("input");
      rainbowCb.type = "checkbox";
      rainbowCb.checked = !!state.filters.rainbowColors;
      rainbowCb.addEventListener("change", function () {
        state.filters.rainbowColors = rainbowCb.checked;
        RE.state.notify();
      });
      rainbowLabel.appendChild(rainbowCb);
      rainbowLabel.appendChild(document.createTextNode(" 🌈 Colors follow rainbow"));
      filterDiv.appendChild(rainbowLabel);
    }

    var records = RE.state.visibleIterationRecords();
    if (!records.length) {
      wrap.innerHTML = '<div style="padding:6px;color:#64748b;">No iterations for current selection.</div>';
      return;
    }

    var single = isSingleSelectGroup(state, "iteration");
    var showColorColumn = state.activeTab === "D";

    var table = el("table", { class: "iteration-table" });
    var thead = el("thead", {}, [
      el("tr", {}, [
        el("th", { html: "&nbsp;" }),
        el("th", { text: "Iter" }),
        el("th", { text: "File" }),
        el("th", {
          class: "col-obj",
          html: '<span class="has-tooltip" data-tooltip="Objective value computed from the run KPIs. Lower is better.">Obj</span>',
        }),
        el("th", {
          html: '<span class="has-tooltip" data-tooltip="How many design constraints passed for this iteration.">Cstr</span>',
        }),
        showColorColumn ? el("th", { text: "" }) : null,
      ]),
    ]);
    table.appendChild(thead);

    var tbody = el("tbody");
    var selIter = state.selection.iteration;

    records.forEach(function (rec) {
      var order = RE.state.attemptIterationOrder(rec.plant, rec.agent, rec.attempt, rec.it.run_index);
      var color = RE.colors.iterationColor(
        rec.plant, rec.agent, rec.attempt,
        order.index, order.total,
        !!state.filters.rainbowColors
      );
      var key = RE.state.iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index);
      var isSelected = single
        ? selIter.focus === key
        : selIter.multiSet.has(key);

      var trClass = "";
      if (single) {
        if (isSelected) trClass = "row-focus";
      } else {
        if (!isSelected) trClass = "hidden-row";
      }
      var tr = el("tr", {
        class: trClass,
        title: rec.plant + " / " + rec.agent + " / " + RE.state.attemptLabel(rec.attempt) + "\n" +
          (rec.it.why || "") + "\n" + (rec.it.description || ""),
      });
      var markerTd = el("td");
      if (rec.it.is_best) {
        markerTd.appendChild(el("span", {
          class: "has-tooltip badge-best",
          "data-tooltip": "Best iteration in the attempt.",
          text: "🏆",
        }));
      }
      if (rec.it.is_first_feasible) {
        markerTd.appendChild(document.createTextNode(rec.it.is_best ? " " : ""));
        markerTd.appendChild(el("span", {
          class: "has-tooltip badge-first",
          "data-tooltip": "First feasible iteration in the attempt.",
          text: "⛳",
        }));
      }
      tr.appendChild(markerTd);
      tr.appendChild(el("td", { text: String(rec.it.iteration_num) }));

      var fileTd = el("td");
      var basename = rec.it.controller_basename || ("run" + rec.it.run_index);
      if (rec.it.controller_basename) {
        var a = document.createElement("a");
        a.href = "#";
        a.className = "ctrl-link";
        a.textContent = basename;
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          RE.state.crossTabJump(rec.plant, rec.agent, rec.attempt, rec.it.run_index, "C");
        });
        fileTd.appendChild(a);
      } else {
        fileTd.textContent = basename;
      }
      tr.appendChild(fileTd);

      var objText = rec.it.objective === null || rec.it.objective === undefined
        ? "inf" : formatObjective(rec.it.objective);
      tr.appendChild(el("td", { text: objText, class: "col-obj" }));
      var cstrPass = (rec.it.constraints || []).filter(function (c) { return c.passed; }).length;
      var cstrTotal = (rec.it.constraints || []).length;
      var cstrCell = el("td", {
        text: cstrPass + "/" + cstrTotal,
        class: (rec.it.feasible ? "constraint-pass " : "constraint-fail ") + "has-tooltip",
        "data-tooltip": (rec.it.constraints || []).map(function (c) {
          var val = c.value === null || c.value === undefined ? "n/a" : c.value;
          return c.desc + ": " + val + " (limit " + c.limit + ") " + (c.passed ? "PASS" : "FAIL");
        }).join("\n"),
      });
      tr.appendChild(cstrCell);
      if (showColorColumn) {
        var sw = el("td");
        if (isSelected) {
          var swatch = el("span", { class: "color-swatch" });
          swatch.style.background = color;
          sw.appendChild(swatch);
        }
        tr.appendChild(sw);
      }

      tr.addEventListener("click", function () {
        if (single) {
          selIter.focus = key;
          selIter.multiSet = new Set([key]);
          RE.state.notify();
          return;
        }
        if (iterationClickTimer) clearTimeout(iterationClickTimer);
        iterationClickTimer = setTimeout(function () {
          if (selIter.multiSet.has(key)) selIter.multiSet.delete(key);
          else selIter.multiSet.add(key);
          selIter.focus = key;
          iterationClickTimer = null;
          RE.state.notify();
        }, 220);
      });

      tr.addEventListener("dblclick", function () {
        if (single) return;
        if (iterationClickTimer) {
          clearTimeout(iterationClickTimer);
          iterationClickTimer = null;
        }
        if (selIter.multiSet.size === 1 && selIter.multiSet.has(key)) {
          selIter.multiSet = new Set(allItems("iteration", state));
        } else {
          selIter.multiSet = new Set([key]);
        }
        selIter.focus = key;
        RE.state.notify();
      });

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
  }

  function formatObjective(v) {
    if (v === null || v === undefined || !isFinite(v)) return "inf";
    var abs = Math.abs(v);
    var dec = abs < 1 ? 4 : abs < 10 ? 3 : abs < 100 ? 2 : 1;
    var s = v.toFixed(dec);
    if (s.indexOf(".") >= 0) {
      s = s.replace(/0+$/, "");
      if (s.endsWith(".")) s += "0";
    }
    return s;
  }

  RE.sidebar = {
    render: render,
    formatObjective: formatObjective,
  };
})();
