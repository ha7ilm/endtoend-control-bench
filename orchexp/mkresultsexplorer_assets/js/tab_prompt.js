(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function renderSubtitleWithFilename(text) {
    return escapeHTML(String(text || "")).replace(
      /(prompt\.md|[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*\/[A-Za-z0-9_.-]+\.md)/g,
      "<tt>$1</tt>"
    );
  }

  function docAnchorId(doc, idx) {
    var base = String((doc && (doc.filename || doc.title)) || ("doc-" + idx))
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    return "prompt-doc-" + (base || String(idx + 1));
  }

  function render(state) {
    var container = document.getElementById("tab-p-content");
    if (!container) return;
    var ctx = RE.state.focusedAttemptContext();
    if (!ctx) {
      container.dataset.key = "";
      container.innerHTML = '<div style="padding:20px;color:#64748b;">No attempt selected.</div>';
      return;
    }

    var docs = ctx.items.length ? (ctx.items[0].prompt_inputs || []) : [];
    var viewKey = [ctx.plant, ctx.agent, ctx.attempt].join("::");
    container.dataset.key = viewKey;
    container.innerHTML = '<div style="padding:20px;color:#64748b;">Loading prompt inputs…</div>';

    Promise.all(docs.map(function (doc) {
      return RE.docCommon.loadText(doc.file).then(function (text) {
        return { doc: doc, text: text, error: null };
      }).catch(function (err) {
        return { doc: doc, text: "", error: err };
      });
    })).then(function (loaded) {
      if (container.dataset.key !== viewKey) return;
      container.innerHTML = "";

      var labels = (state.catalog && state.catalog.plant_labels) || {};
      var aLabels = (state.catalog && state.catalog.agent_labels) || {};
      var plantTxt = (labels[ctx.plant] && labels[ctx.plant].short_name) || ctx.plant;
      var agentTxt = (aLabels[ctx.agent] && aLabels[ctx.agent].short_name) || ctx.agent;

      var intro = document.createElement("section");
      intro.className = "thinking-section";
      var summaryText = plantTxt + " · " + agentTxt + " · " + RE.state.attemptLabel(ctx.attempt) + " — " + loaded.length + " files";
      var anchorLinks = loaded.map(function (entry, idx) {
        var label = entry.doc.filename || entry.doc.title || ("file " + (idx + 1));
        return '<a class="ctrl-link" href="#' + escapeHTML(docAnchorId(entry.doc, idx)) + '">' + escapeHTML(label) + "</a>";
      }).join(" · ");
      intro.innerHTML =
        '<h3 class="thinking-section-title">Inputs given to the LLM</h3>' +
        '<div class="thinking-section-subtitle">' +
        escapeHTML(summaryText) +
        '</div>' +
        '<div class="thinking-section-subtitle">' +
        (anchorLinks || "") +
        '</div>';
      container.appendChild(intro);

      if (!loaded.length) {
        var empty = document.createElement("div");
        empty.className = "markdown-doc-body";
        empty.innerHTML = '<div style="padding:6px 0;color:#64748b;">No prompt or input markdown files were copied for this attempt.</div>';
        intro.appendChild(empty);
        return;
      }

      loaded.forEach(function (entry, idx) {
        var section = document.createElement("section");
        section.className = "thinking-section";
        section.id = docAnchorId(entry.doc, idx);
        section.innerHTML =
          '<h3 class="thinking-section-title">' + escapeHTML(entry.doc.title || entry.doc.filename || "Input file") + '</h3>' +
          '<div class="thinking-section-subtitle">' + renderSubtitleWithFilename(entry.doc.subtitle || entry.doc.filename || "") + '</div>';
        var body = document.createElement("div");
        body.className = "markdown-doc-body";
        if (entry.error) {
          body.innerHTML = '<div style="padding:6px 0;color:#b00020;">Failed to load ' + escapeHTML(entry.doc.filename || "file") + ': ' + escapeHTML(entry.error.message || String(entry.error)) + "</div>";
        } else if (String(entry.text || "").trim()) {
          body.innerHTML = RE.docCommon.renderMarkdownNoLinks(entry.text);
          RE.docCommon.highlightBlocks(body);
          RE.docCommon.typesetMath(body);
        } else {
          body.innerHTML = '<div style="padding:6px 0;color:#64748b;">' + escapeHTML(entry.doc.filename || "File") + " is empty.</div>";
        }
        section.appendChild(body);
        container.appendChild(section);
      });
    }).catch(function (err) {
      if (container.dataset.key !== viewKey) return;
      container.innerHTML = '<div style="padding:20px;color:#b00020;">Failed to load prompt inputs: ' + escapeHTML(err.message || String(err)) + '</div>';
    });
  }

  RE.tabs = RE.tabs || {};
  RE.tabs.P = { render: render };
})();
