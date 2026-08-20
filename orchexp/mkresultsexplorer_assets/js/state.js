(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  function iterKey(plant, agent, attempt, runIndex) {
    return plant + "__" + agent + "__attempt" + attempt + "__run" + runIndex;
  }

  function attemptKey(plant, agent, attempt) {
    return plant + "__" + agent + "__attempt" + attempt;
  }

  function attemptLabel(attempt) {
    return "Attempt " + (attempt + 1);
  }

  function isSingleSelectGroup(tab, group) {
    if (tab === "P") return group === "agent" || group === "plant" || group === "attempt";
    if (tab === "B") return group === "agent" || group === "plant" || group === "attempt";
    if (tab === "C") return group === "agent" || group === "plant" || group === "attempt" || group === "iteration";
    if ((tab === "A" || tab === "D") && group === "plant") return true;
    return false;
  }

  function isGroupVisible(tab, group) {
    if (group === "graph-settings") return tab === "A";
    if (group === "iteration") return tab === "C" || tab === "D";
    return true;
  }

  var state = {
    catalog: null,
    selection: {
      agent: { multiSet: new Set(), focus: null },
      plant: { multiSet: new Set(), focus: null },
      attempt: { multiSet: new Set(), focus: null },
      iteration: { multiSet: new Set(), focus: null },
    },
    activeTab: "A",
    filters: {
      showBestOnly: false,
      showFirstFeasibleOnly: false,
      rainbowColors: false,
      showActualMarkers: false,
      colorLinesPerAgent: true,
    },
    sidebarCollapsed: {
      agent: false,
      plant: false,
      attempt: false,
      "graph-settings": false,
      iteration: false,
    },
    subscribers: [],
  };

  function compareValues(a, b) {
    if (typeof a === "number" && typeof b === "number") return a - b;
    return String(a).localeCompare(String(b));
  }

  function sortedValues(group, setLike) {
    return Array.from(setLike || []).sort(compareValues);
  }

  function firstFromSet(group, setLike) {
    var vals = sortedValues(group, setLike);
    return vals.length ? vals[0] : null;
  }

  function chosenValue(group) {
    var sel = state.selection[group];
    if (sel.focus !== null && sel.focus !== undefined) return sel.focus;
    return firstFromSet(group, sel.multiSet);
  }

  function setCatalog(catalog) {
    state.catalog = catalog;
    var sel = state.selection;
    sel.plant.multiSet = new Set(catalog.plants);
    sel.plant.focus = catalog.plants[0] || null;
    sel.agent.multiSet = new Set(catalog.agents);
    sel.agent.focus = catalog.agents[0] || null;
    var allAttempts = new Set();
    Object.keys(catalog.attempts_per_agent || {}).forEach(function (a) {
      (catalog.attempts_per_agent[a] || []).forEach(function (n) { allAttempts.add(n); });
    });
    sel.attempt.multiSet = allAttempts;
    sel.attempt.focus = firstFromSet("attempt", allAttempts);
    sel.iteration.multiSet = new Set();
    sel.iteration.focus = null;
    applyTabSelectionModes();
  }

  function subscribe(fn) {
    state.subscribers.push(fn);
    return function () {
      state.subscribers = state.subscribers.filter(function (f) { return f !== fn; });
    };
  }

  function notify() {
    validateAgainstCatalog();
    applyTabSelectionModes();
    state.subscribers.forEach(function (fn) {
      try { fn(state); } catch (e) { console.error(e); }
    });
  }

  function setActiveTab(tab) {
    state.activeTab = tab;
    notify();
  }

  function firstIterationKey() {
    if (!state.catalog) return null;
    var its = state.catalog.iterations || {};
    var keys = Object.keys(its).sort();
    for (var i = 0; i < keys.length; i++) {
      var arr = its[keys[i]];
      if (arr && arr.length) {
        var parts = keys[i].split("__attempt");
        var rest = parts[0];
        var attempt = parseInt(parts[1], 10);
        var rsplit = rest.split("__");
        var plant = rsplit[0];
        var agent = rsplit.slice(1).join("__");
        return iterKey(plant, agent, attempt, arr[0].run_index);
      }
    }
    return null;
  }

  function iterationExistsInCatalog(key) {
    if (!state.catalog) return false;
    var parts = parseIterKey(key);
    if (!parts) return false;
    var arr = (state.catalog.iterations || {})[attemptKey(parts.plant, parts.agent, parts.attempt)];
    if (!arr) return false;
    return arr.some(function (it) { return it.run_index === parts.runIndex; });
  }

  function parseIterKey(key) {
    var idx = key.lastIndexOf("__run");
    if (idx < 0) return null;
    var runIndex = parseInt(key.slice(idx + 5), 10);
    if (isNaN(runIndex)) return null;
    var rest = key.slice(0, idx);
    var idx2 = rest.lastIndexOf("__attempt");
    if (idx2 < 0) return null;
    var attempt = parseInt(rest.slice(idx2 + 9), 10);
    if (isNaN(attempt)) return null;
    var rest2 = rest.slice(0, idx2);
    var parts = rest2.split("__");
    if (parts.length < 2) return null;
    return {
      plant: parts[0],
      agent: parts.slice(1).join("__"),
      attempt: attempt,
      runIndex: runIndex,
    };
  }

  function validateAgainstCatalog() {
    if (!state.catalog) return;
    var c = state.catalog;
    var sel = state.selection;
    sel.plant.multiSet = new Set(Array.from(sel.plant.multiSet).filter(function (p) { return c.plants.indexOf(p) >= 0; }));
    sel.agent.multiSet = new Set(Array.from(sel.agent.multiSet).filter(function (a) { return c.agents.indexOf(a) >= 0; }));
    var allAttempts = new Set();
    Object.keys(c.attempts_per_agent || {}).forEach(function (a) {
      (c.attempts_per_agent[a] || []).forEach(function (n) { allAttempts.add(n); });
    });
    sel.attempt.multiSet = new Set(Array.from(sel.attempt.multiSet).filter(function (n) { return allAttempts.has(n); }));
    sel.iteration.multiSet = new Set(Array.from(sel.iteration.multiSet).filter(iterationExistsInCatalog));
    if (sel.plant.focus && c.plants.indexOf(sel.plant.focus) < 0) sel.plant.focus = c.plants[0] || null;
    if (sel.agent.focus && c.agents.indexOf(sel.agent.focus) < 0) sel.agent.focus = c.agents[0] || null;
    if (sel.attempt.focus !== null && !allAttempts.has(sel.attempt.focus)) {
      sel.attempt.focus = firstFromSet("attempt", allAttempts);
    }
    if (sel.iteration.focus && !iterationExistsInCatalog(sel.iteration.focus)) sel.iteration.focus = null;
  }

  function applySingleSelection(group) {
    var sel = state.selection[group];
    var focus = chosenValue(group);
    if (focus === null || focus === undefined) {
      sel.multiSet = new Set();
      sel.focus = null;
      return;
    }
    sel.focus = focus;
    sel.multiSet = new Set([focus]);
  }

  function applyMultiSelection(group) {
    var sel = state.selection[group];
    if (!sel.multiSet.size && sel.focus !== null && sel.focus !== undefined) {
      sel.multiSet = new Set([sel.focus]);
    }
    if ((!sel.focus && sel.focus !== 0) || !sel.multiSet.has(sel.focus)) {
      sel.focus = firstFromSet(group, sel.multiSet);
    }
  }

  function applyTabSelectionModes() {
    ["agent", "plant", "attempt"].forEach(function (group) {
      if (isSingleSelectGroup(state.activeTab, group)) applySingleSelection(group);
      else applyMultiSelection(group);
    });

    var visible = visibleIterationRecords();
    var selIter = state.selection.iteration;
    if (isSingleSelectGroup(state.activeTab, "iteration")) {
      var focusRec = null;
      if (selIter.focus) {
        focusRec = visible.find(function (rec) {
          return iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index) === selIter.focus;
        }) || null;
      }
      if (!focusRec && visible.length) {
        focusRec = visible[0];
      }
      if (focusRec) {
        selIter.focus = iterKey(focusRec.plant, focusRec.agent, focusRec.attempt, focusRec.it.run_index);
        selIter.multiSet = new Set([selIter.focus]);
      } else if (!selIter.focus) {
        var fk = firstIterationKey();
        if (fk) {
          selIter.focus = fk;
          selIter.multiSet = new Set([fk]);
        } else {
          selIter.multiSet = new Set();
        }
      }
    } else {
      selIter.multiSet = new Set(Array.from(selIter.multiSet).filter(function (key) {
        return visible.some(function (rec) {
          return iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index) === key;
        });
      }));
      if (selIter.focus && !iterationExistsInCatalog(selIter.focus)) selIter.focus = null;
    }
  }

  function visibleIterationRecords() {
    if (!state.catalog) return [];
    var out = [];
    var plants = sortedValues("plant", state.selection.plant.multiSet);
    var agents = sortedValues("agent", state.selection.agent.multiSet);
    var attempts = sortedValues("attempt", state.selection.attempt.multiSet);
    var applyPlotFilters = state.activeTab === "D";
    plants.forEach(function (plant) {
      agents.forEach(function (agent) {
        attempts.forEach(function (attempt) {
          var list = (state.catalog.iterations || {})[attemptKey(plant, agent, attempt)];
          if (!list) return;
          list.forEach(function (it) {
            if (applyPlotFilters) {
              var bestOnly = !!state.filters.showBestOnly;
              var firstOnly = !!state.filters.showFirstFeasibleOnly;
              if (bestOnly || firstOnly) {
                var keep = (bestOnly && it.is_best) || (firstOnly && it.is_first_feasible);
                if (!keep) return;
              }
            }
            out.push({ plant: plant, agent: agent, attempt: attempt, it: it });
          });
        });
      });
    });
    return out;
  }

  function focusedAttemptContext() {
    if (!state.catalog) return null;
    var plant = chosenValue("plant");
    var agent = chosenValue("agent");
    var attempt = chosenValue("attempt");
    if (plant !== null && agent !== null && attempt !== null) {
      var key = attemptKey(plant, agent, attempt);
      var items = (state.catalog.iterations || {})[key];
      if (items && items.length) return { plant: plant, agent: agent, attempt: attempt, items: items };
    }
    var visible = visibleIterationRecords();
    if (!visible.length) return null;
    var first = visible[0];
    return {
      plant: first.plant,
      agent: first.agent,
      attempt: first.attempt,
      items: ((state.catalog.iterations || {})[attemptKey(first.plant, first.agent, first.attempt)] || []),
    };
  }

  function singleIterationRecord() {
    var focus = state.selection.iteration.focus;
    var visible = visibleIterationRecords();
    if (focus) {
      var hit = visible.find(function (rec) {
        return iterKey(rec.plant, rec.agent, rec.attempt, rec.it.run_index) === focus;
      });
      if (hit) return hit;
    }
    return visible.length ? visible[0] : null;
  }

  function attemptIterationOrder(plant, agent, attempt, runIndex) {
    var list = ((state.catalog || {}).iterations || {})[attemptKey(plant, agent, attempt)] || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].run_index === runIndex) return { index: i, total: list.length };
    }
    return { index: 0, total: Math.max(list.length, 1) };
  }

  function crossTabJump(plant, agent, attempt, runIndex, targetTab) {
    var nextTab = targetTab || "D";
    var sel = state.selection;
    sel.plant.focus = plant;
    sel.plant.multiSet = new Set([plant]);
    sel.agent.focus = agent;
    sel.agent.multiSet = new Set([agent]);
    sel.attempt.focus = attempt;
    sel.attempt.multiSet = new Set([attempt]);
    var ik = iterKey(plant, agent, attempt, runIndex);
    sel.iteration.focus = ik;
    sel.iteration.multiSet = new Set([ik]);
    if (nextTab === "D") {
      state.filters.showBestOnly = false;
      state.filters.showFirstFeasibleOnly = false;
    }
    state.activeTab = nextTab;
    notify();
  }

  RE.state = {
    get: function () { return state; },
    setCatalog: setCatalog,
    setActiveTab: setActiveTab,
    notify: notify,
    subscribe: subscribe,
    iterKey: iterKey,
    attemptKey: attemptKey,
    parseIterKey: parseIterKey,
    validateAgainstCatalog: validateAgainstCatalog,
    visibleIterationRecords: visibleIterationRecords,
    focusedAttemptContext: focusedAttemptContext,
    singleIterationRecord: singleIterationRecord,
    attemptIterationOrder: attemptIterationOrder,
    isSingleSelectGroup: isSingleSelectGroup,
    isGroupVisible: isGroupVisible,
    attemptLabel: attemptLabel,
    crossTabJump: crossTabJump,
  };
})();
