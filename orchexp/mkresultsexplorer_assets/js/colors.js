(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  var TRACE_COLORS = [
    "#636EFA","#EF553B","#00CC96","#AB63FA","#FFA15A","#19D3F3","#FF6692",
    "#B6E880","#FF97FF","#FECB52","#1F77B4","#FF7F0E","#2CA02C","#D62728",
    "#9467BD","#8C564B","#E377C2","#7F7F7F","#BCBD22","#17BECF","#3366CC",
    "#DC3912","#FF9900","#109618","#990099","#0099C6","#DD4477","#66AA00",
    "#B82E2E","#316395","#994499","#22AA99","#AAAA11","#6633CC","#E67300",
    "#8B0707","#329262","#5574A6","#3B3EAC"
  ];

  function hashStr(s) {
    var h = 5381;
    for (var i = 0; i < s.length; i++) {
      h = ((h << 5) + h + s.charCodeAt(i)) | 0;
    }
    return Math.abs(h);
  }

  function attemptColor(plant, agent, attempt) {
    return TRACE_COLORS[hashStr(plant + "|" + agent + "|" + attempt) % TRACE_COLORS.length];
  }

  function agentColor(state, agent) {
    var labels = (state && state.catalog && state.catalog.agent_labels) || {};
    var info = labels[agent] || {};
    var color = String(info.color || "").trim();
    if (color) return color;
    return TRACE_COLORS[hashStr("agent|" + agent) % TRACE_COLORS.length];
  }

  function iterationColor(plant, agent, attempt, runIndex, totalInAttempt, rainbow) {
    if (!rainbow) {
      return TRACE_COLORS[runIndex % TRACE_COLORS.length];
    }
    if (totalInAttempt <= 1) return "#ff0000";
    var t = runIndex / (totalInAttempt - 1);
    // red -> yellow -> blue
    var r, g, b;
    if (t < 0.5) {
      var k = t / 0.5;
      r = 255;
      g = Math.round(255 * k);
      b = 0;
    } else {
      var k2 = (t - 0.5) / 0.5;
      r = Math.round(255 * (1 - k2));
      g = Math.round(255 * (1 - k2));
      b = Math.round(255 * k2);
    }
    return "#" + [r, g, b].map(function (v) {
      var h = v.toString(16);
      return h.length < 2 ? "0" + h : h;
    }).join("");
  }

  RE.colors = {
    TRACE_COLORS: TRACE_COLORS,
    attemptColor: attemptColor,
    agentColor: agentColor,
    iterationColor: iterationColor,
  };
})();
