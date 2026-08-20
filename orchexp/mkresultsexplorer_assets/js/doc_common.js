(function () {
  var RE = (window.ResultsExplorer = window.ResultsExplorer || {});

  var textCache = {};
  var MATH_DELIMITER_TOKENS = [
    { raw: "\\(", token: "@@RE_MATH_INLINE_OPEN@@" },
    { raw: "\\)", token: "@@RE_MATH_INLINE_CLOSE@@" },
    { raw: "\\[", token: "@@RE_MATH_DISPLAY_OPEN@@" },
    { raw: "\\]", token: "@@RE_MATH_DISPLAY_CLOSE@@" },
  ];

  function loadText(path) {
    if (!path) return Promise.resolve("");
    if (textCache[path]) return Promise.resolve(textCache[path]);
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    }).then(function (text) {
      textCache[path] = text;
      return text;
    });
  }

  function renderMarkdownNoLinks(text) {
    if (!window.marked) return "<pre><code>" + escapeHTML(text || "") + "</code></pre>";
    var html;
    try {
      html = window.marked.parse(protectMathDelimiters(text || ""));
    } catch (e) {
      return "<pre><code>" + escapeHTML(text || "") + "</code></pre>";
    }
    var box = document.createElement("div");
    box.innerHTML = html;
    box.querySelectorAll("a").forEach(function (a) {
      var frag = document.createDocumentFragment();
      while (a.firstChild) frag.appendChild(a.firstChild);
      a.replaceWith(frag);
    });
    return restoreMathDelimiters(box.innerHTML);
  }

  function protectMathDelimiters(text) {
    var out = String(text || "");
    MATH_DELIMITER_TOKENS.forEach(function (entry) {
      out = out.split(entry.raw).join(entry.token);
    });
    return out;
  }

  function restoreMathDelimiters(text) {
    var out = String(text || "");
    MATH_DELIMITER_TOKENS.forEach(function (entry) {
      out = out.split(entry.token).join(entry.raw);
    });
    return out;
  }

  function highlightBlocks(root) {
    if (!window.hljs) return;
    root.querySelectorAll("pre code").forEach(function (block) {
      if (block.classList.contains("no-highlight")) return;
      block.removeAttribute("data-highlighted");
      block.classList.remove("hljs");
      try { window.hljs.highlightElement(block); } catch (e) {}
    });
  }

  function typesetMath(root) {
    if (!root || !window.MathJax || typeof window.MathJax.typesetPromise !== "function") {
      return Promise.resolve();
    }
    return window.MathJax.typesetPromise([root]).catch(function () {});
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  RE.docCommon = {
    loadText: loadText,
    renderMarkdownNoLinks: renderMarkdownNoLinks,
    highlightBlocks: highlightBlocks,
    typesetMath: typesetMath,
    escapeHTML: escapeHTML,
  };
})();
