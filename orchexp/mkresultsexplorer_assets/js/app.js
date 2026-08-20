(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  function setActiveTabUI(tab) {
    document.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.tab === tab);
    });
    document.querySelectorAll(".tab-panel").forEach(function (panel) {
      panel.classList.toggle("active", panel.dataset.tab === tab);
    });
  }

  function normalizeTooltipHTML(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/\n/g, "<br>");
  }

  function initTooltips() {
    if (!window.bootstrap || !window.bootstrap.Tooltip) return;
    document.querySelectorAll(".tooltip.show").forEach(function (tip) {
      tip.remove();
    });
    document.querySelectorAll("[data-tooltip]").forEach(function (el) {
      var text = el.getAttribute("data-tooltip");
      if (!text) return;
      el.setAttribute("data-bs-toggle", "tooltip");
      el.setAttribute("data-bs-placement", "top");
      el.setAttribute("data-bs-html", "true");
      el.setAttribute("data-bs-title", normalizeTooltipHTML(text));
      window.bootstrap.Tooltip.getOrCreateInstance(el, {
        container: "body",
        html: true,
        trigger: "hover focus",
      });
    });
  }

  function rerender() {
    var state = RE.state.get();
    setActiveTabUI(state.activeTab);
    RE.sidebar.render(state);
    if (state.activeTab === "A") RE.tabs.A.render(state);
    if (state.activeTab === "P") RE.tabs.P.render(state);
    if (state.activeTab === "B") RE.tabs.B.render(state);
    if (state.activeTab === "C") RE.tabs.C.render(state);
    if (state.activeTab === "D") RE.tabs.D.render(state);
    initTooltips();
  }

  function bindTabButtons() {
    document.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        RE.state.setActiveTab(btn.dataset.tab);
      });
    });
  }

  function bindSidebarToggle() {
    var btn = document.getElementById("sidebar-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      document.getElementById("app-shell").classList.toggle("sidebar-hidden");
    });
  }

  function showError(msg) {
    var content = document.getElementById("content");
    if (content) {
      content.innerHTML = '<div style="padding:24px;color:#b00020;">' + msg + "</div>";
    }
    console.error(msg);
  }

  function boot() {
    bindTabButtons();
    bindSidebarToggle();
    setActiveTabUI("A");

    fetch("data/catalog.json")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status + " fetching catalog.json");
        return r.json();
      })
      .then(function (catalog) {
        RE.state.setCatalog(catalog);
        RE.state.validateAgainstCatalog();
        RE.state.subscribe(rerender);
        rerender();
      })
      .catch(function (err) {
        showError("Failed to load catalog.json: " + err.message);
      });
  }

  RE.boot = boot;
})();
