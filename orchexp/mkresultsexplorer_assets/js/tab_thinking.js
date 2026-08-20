(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  var cache = {};

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function stripPreviewMarkdown(text) {
    return String(text || "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/^[>*-]\s+/gm, "")
      .replace(/\r/g, "");
  }

  function snippet(text, n) {
    if (!text) return "";
    var s = stripPreviewMarkdown(text).replace(/\s+/g, " ").trim();
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  function basename(path) {
    return String(path || "").split("/").pop() || "";
  }

  function languageFromPath(path) {
    if (!path) return "";
    if (/\.py$/i.test(path)) return "python";
    if (/\.(sh|bash|zsh)$/i.test(path)) return "bash";
    if (/\.jsonl?$/i.test(path)) return "json";
    if (/\.(diff|patch)$/i.test(path)) return "diff";
    return "";
  }

  function detectLanguage(text, preferred) {
    if (preferred) return preferred;
    var s = String(text || "").trim();
    if (!s) return "";
    if (s.startsWith("{") || s.startsWith("[")) {
      try {
        JSON.parse(s);
        return "json";
      } catch (e) {}
    }
    if (s.indexOf("*** Begin Patch") >= 0 || /^--- .*\n\+\+\+ /m.test(s) || /^@@ /m.test(s)) return "diff";
    if (/^#!.*\b(bash|sh|zsh)\b/m.test(s)) return "bash";
    return "";
  }

  function detectOutputLanguage(text) {
    var s = String(text || "").trim();
    if (!s) return "";
    if (s.startsWith("{") || s.startsWith("[")) {
      try {
        JSON.parse(s);
        return "json";
      } catch (e) {}
    }
    if (s.indexOf("*** Begin Patch") >= 0 || /^--- .*\n\+\+\+ /m.test(s) || /^@@ /m.test(s)) return "diff";
    return "";
  }

  function codeBlock(text, language, noHighlight) {
    var classes = [];
    if (language) classes.push("language-" + language);
    if (noHighlight) classes.push("no-highlight");
    var cls = classes.length ? ' class="' + classes.join(" ") + '"' : "";
    return "<pre><code" + cls + ">" + escapeHTML(text || "") + "</code></pre>";
  }

  function eventTitle(ev) {
    if (ev.kind === "meta") return ev.label || "meta";
    if (ev.kind === "reasoning") return "Reasoning";
    if (ev.kind === "assistant_text") return "Assistant";
    if (ev.kind === "user_text") return "User";
    if (ev.kind === "tool_use") return "Tool: " + (ev.tool_name || "?");
    if (ev.kind === "tool_result") return "Tool result";
    if (ev.kind === "result") return "Run result";
    return ev.kind || "event";
  }

  function eventSnippet(ev) {
    if (ev.kind === "meta") return ev.detail || "";
    if (ev.kind === "reasoning" || ev.kind === "assistant_text" || ev.kind === "user_text" || ev.kind === "result") {
      return snippet(ev.text || "", 200);
    }
    if (ev.kind === "tool_use" && ev.tool_name === "FileChange" && Array.isArray(ev.tool_changes) && ev.tool_changes.length) {
      return ev.tool_changes.map(function (change) {
        return (change.kind || "change") + " " + (change.path_rel || change.path || "");
      }).join(" · ");
    }
    if (ev.kind === "tool_use") {
      var input = ev.tool_input;
      if (typeof input === "string") return snippet(input, 200);
      try { return snippet(JSON.stringify(input), 200); } catch (e) { return ""; }
    }
    if (ev.kind === "tool_result") return snippet(ev.tool_output || "", 200);
    return "";
  }

  function renderToolChange(change, ctx) {
    var pathText = escapeHTML(change.path_rel || change.path || "");
    var html = '<div class="tool-meta-line"><b>' + escapeHTML(change.kind || "change") + "</b> " + pathText;
    var fileName = basename(change.path || change.path_rel || "");
    var target = null;
    if (ctx && Array.isArray(ctx.items) && fileName) {
      target = ctx.items.find(function (it) {
        return it && it.controller_basename === fileName;
      }) || null;
    }
    if (target) {
      html += ' · <a href="#" class="ctrl-jump-link" data-run="' + escapeHTML(String(target.run_index)) + '">open in Controller code</a>';
    }
    html += "</div>";
    if (change.kind === "update" && !target) {
      html += '<div class="tool-meta-line">Open the matching controller in the Controller code tab from the iteration list.</div>';
    }
    return html;
  }

  function renderToolResultMeta(meta) {
    if (!meta || typeof meta !== "object") return "";
    var html = "";
    if (meta.filePath) {
      html += '<div class="tool-meta-line"><b>path:</b> ' + escapeHTML(meta.filePath) + "</div>";
    }
    if (meta.type) {
      html += '<div class="tool-meta-line"><b>result type:</b> ' + escapeHTML(meta.type) + "</div>";
    }
    if (Array.isArray(meta.structuredPatch) && meta.structuredPatch.length) {
      var patchText = meta.structuredPatch.map(function (hunk) {
        return Array.isArray(hunk.lines) ? hunk.lines.join("\n") : "";
      }).filter(Boolean).join("\n");
      if (patchText) {
        html += codeBlock(patchText, "diff", true);
      }
    } else if (meta.content && meta.filePath) {
      html += codeBlock(meta.content, languageFromPath(meta.filePath), true);
    } else if (meta.file && meta.file.content) {
      html += '<div class="tool-meta-line"><b>path:</b> ' + escapeHTML(meta.file.filePath || "") + "</div>";
      html += codeBlock(meta.file.content, languageFromPath(meta.file.filePath), true);
    }
    return html;
  }

  function renderBody(ev, ctx) {
    var html = "";
    if (ev.kind === "reasoning" || ev.kind === "assistant_text" || ev.kind === "user_text") {
      html = RE.docCommon.renderMarkdownNoLinks(ev.text || "");
    } else if (ev.kind === "tool_use") {
      if (ev.tool_name === "FileChange" && Array.isArray(ev.tool_changes) && ev.tool_changes.length) {
        html = ev.tool_changes.map(function (change) {
          return renderToolChange(change, ctx);
        }).join("");
      } else {
        var input = ev.tool_input;
        var inputText = typeof input === "string" ? input : JSON.stringify(input, null, 2);
        var meta = "";
        if (ev.tool_id) meta += '<div class="tool-meta-line"><b>id:</b> ' + escapeHTML(ev.tool_id) + "</div>";
        if (ev.exit_code !== undefined && ev.exit_code !== null) {
          meta += '<div class="tool-meta-line"><b>exit:</b> ' + escapeHTML(String(ev.exit_code)) + "</div>";
        }
        meta += '<div class="tool-meta-line"><b>tool:</b> ' + escapeHTML(ev.tool_name || "?") + "</div>";
        var inputLang = detectLanguage(inputText, /bash/i.test(ev.tool_name || "") ? "bash" : "");
        html = meta + codeBlock(inputText, inputLang);
        if (ev.tool_output) {
          html += '<div class="tool-meta-line"><b>output:</b></div>';
          var bashOutput = /bash/i.test(ev.tool_name || "");
          html += codeBlock(ev.tool_output, bashOutput ? "" : detectOutputLanguage(ev.tool_output), bashOutput);
        }
      }
    } else if (ev.kind === "tool_result") {
      var idLine = ev.tool_use_id ? '<div class="tool-meta-line"><b>tool_use_id:</b> ' + escapeHTML(ev.tool_use_id) + "</div>" : "";
      var metaHtml = renderToolResultMeta(ev.tool_result_meta);
      html = idLine + metaHtml;
      if (ev.tool_output && !metaHtml) {
        html += codeBlock(ev.tool_output, detectOutputLanguage(ev.tool_output), true);
      }
    } else if (ev.kind === "result") {
      var hdr =
        "subtype=" + escapeHTML(ev.subtype || "") +
        "  status=" + (ev.is_error ? "error" : "success") +
        "  duration_ms=" + ev.duration_ms +
        "  turns=" + ev.num_turns;
      html = '<div class="tool-meta-line">' + hdr + "</div>" + codeBlock(ev.text || "", "");
    } else if (ev.kind === "meta") {
      html = "<div>" + escapeHTML(ev.detail || "") + "</div>";
    } else {
      html = codeBlock(JSON.stringify(ev.raw || ev, null, 2), "json");
    }
    return html;
  }

  function loadLog(path) {
    if (cache[path]) return Promise.resolve(cache[path]);
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    }).then(function (text) {
      var lines = text.split("\n");
      var events = [];
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        try {
          events.push(JSON.parse(line));
        } catch (e) {}
      }
      cache[path] = events;
      return events;
    });
  }

  function bindControllerLinks(root, ctx) {
    if (!ctx) return;
    root.querySelectorAll("a.ctrl-jump-link[data-run]").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var runIndex = parseInt(a.dataset.run, 10);
        if (isNaN(runIndex)) return;
        RE.state.crossTabJump(ctx.plant, ctx.agent, ctx.attempt, runIndex, "C");
      });
    });
  }

  function ensureRendered(elDiv, ev, ctx) {
    var body = elDiv.querySelector(".log-event-body");
    if (body.dataset.lazy !== "1") return;
    body.innerHTML = renderBody(ev, ctx);
    body.dataset.lazy = "0";
    bindControllerLinks(body, ctx);
    RE.docCommon.highlightBlocks(body);
    RE.docCommon.typesetMath(body);
  }

  function setAllCollapsed(container, collapsed, ctx) {
    container.querySelectorAll(".log-event").forEach(function (elDiv) {
      elDiv.classList.toggle("collapsed", collapsed);
      if (!collapsed) {
        var idx = parseInt(elDiv.dataset.eventIndex, 10);
        var events = cache[container.dataset.path] || [];
        if (!isNaN(idx) && events[idx]) ensureRendered(elDiv, events[idx], ctx);
      }
    });
  }

  function render(state) {
    var container = document.getElementById("tab-b-content");
    if (!container) return;
    var ctx = RE.state.focusedAttemptContext();
    if (!ctx) {
      container.dataset.path = "";
      container.innerHTML = '<div style="padding:20px;color:#64748b;">No attempt selected.</div>';
      return;
    }
    var logPath = ctx.items.length ? ctx.items[0].log_file : null;
    var summaryPath = ctx.items.length ? ctx.items[0].summary_file : null;
    if (!logPath) {
      container.dataset.path = "";
      container.innerHTML = '<div style="padding:20px;color:#64748b;">No log file for this attempt.</div>';
      return;
    }
    container.dataset.path = logPath;
    container.innerHTML = '<div style="padding:20px;color:#64748b;">Loading log…</div>';

    Promise.all([
      loadLog(logPath),
      summaryPath ? RE.docCommon.loadText(summaryPath).catch(function () { return ""; }) : Promise.resolve(""),
    ]).then(function (loaded) {
      var events = loaded[0];
      var summaryText = loaded[1];
      if (container.dataset.path !== logPath) return;
      container.innerHTML = "";
      var labels = (state.catalog && state.catalog.plant_labels) || {};
      var aLabels = (state.catalog && state.catalog.agent_labels) || {};
      var plantTxt = (labels[ctx.plant] && labels[ctx.plant].short_name) || ctx.plant;
      var agentTxt = (aLabels[ctx.agent] && aLabels[ctx.agent].short_name) || ctx.agent;

      var summarySection = document.createElement("section");
      summarySection.className = "thinking-section";
      summarySection.innerHTML =
        '<h3 class="thinking-section-title">Summary of the thinking process</h3>' +
        '<div class="thinking-section-subtitle">from the LLM, as in <tt>summary.md</tt></div>';
      var summaryBody = document.createElement("div");
      summaryBody.className = "markdown-doc-body";
      if (summaryText.trim()) {
        summaryBody.innerHTML = RE.docCommon.renderMarkdownNoLinks(summaryText);
        RE.docCommon.highlightBlocks(summaryBody);
        RE.docCommon.typesetMath(summaryBody);
      } else {
        summaryBody.innerHTML = '<div style="padding:6px 0;color:#64748b;">No summary.md for this attempt.</div>';
      }
      summarySection.appendChild(summaryBody);
      container.appendChild(summarySection);

      var fullSection = document.createElement("section");
      fullSection.className = "thinking-section";
      fullSection.innerHTML =
        '<h3 class="thinking-section-title">The full thinking process</h3>';
      container.appendChild(fullSection);

      var header = document.createElement("div");
      header.className = "thinking-header";
      header.innerHTML =
        '<span>' + escapeHTML(plantTxt + " · " + agentTxt + " · " + RE.state.attemptLabel(ctx.attempt) +
        " — " + events.length + " events") + "</span>" +
        '<span class="listbox-actions"> · <a href="#" class="select-link" data-act="fold">fold</a> or ' +
        '<a href="#" class="select-link" data-act="unfold">unfold</a> all</span>';
      fullSection.appendChild(header);
      header.querySelectorAll("a[data-act]").forEach(function (a) {
        a.addEventListener("click", function (e) {
          e.preventDefault();
          setAllCollapsed(container, a.dataset.act === "fold", ctx);
        });
      });

      events.forEach(function (ev, idx) {
        var elDiv = document.createElement("div");
        elDiv.className = "log-event collapsed kind-" + (ev.kind || "unknown");
        elDiv.dataset.eventIndex = String(idx);
        if (ev.is_error) elDiv.classList.add("is-error");
        var hdr = document.createElement("div");
        hdr.className = "log-event-header";
        hdr.innerHTML = '<span class="kind-badge">' + escapeHTML(eventTitle(ev)) + '</span>' +
          '<span style="color:#9aa1a9;font-size:10px;">#' + (idx + 1) + '</span>' +
          '<span class="snippet">' + escapeHTML(eventSnippet(ev)) + '</span>';
        elDiv.appendChild(hdr);
        var body = document.createElement("div");
        body.className = "log-event-body";
        body.dataset.lazy = "1";
        elDiv.appendChild(body);
        hdr.addEventListener("click", function () {
          var collapsed = elDiv.classList.toggle("collapsed");
          if (!collapsed) ensureRendered(elDiv, ev, ctx);
        });
        fullSection.appendChild(elDiv);
      });
    }).catch(function (err) {
      if (container.dataset.path !== logPath) return;
      container.innerHTML = '<div style="padding:20px;color:#b00020;">Failed to load log: ' + escapeHTML(err.message) + '</div>';
    });
  }

  RE.tabs = RE.tabs || {};
  RE.tabs.B = { render: render };
})();
