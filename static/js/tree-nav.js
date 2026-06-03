(function () {
  const container = document.getElementById("tree-nav-container");
  if (!container) return;

  fetch("/navigation.json")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var html = "<ul class='tree-nav'>";
      data.forEach(function (node) { html += renderNode(node); });
      html += "</ul>";
      container.innerHTML = html;
    })
    .catch(function (e) { console.warn("tree-nav: failed to load navigation.json", e); });

  function renderNode(node) {
    if (node.children && node.children.length) {
      var id = "tree-" + node.title.replace(/\s+/g, "-").toLowerCase();
      var html = "<li>";
      html += "<details id='" + id + "'>";
      html += "<summary>" + escapeHtml(node.title);
      if (node.url) { html += " <a href='" + node.url + "' class='tree-folder-link'>â†—</a>"; }
      html += "</summary>";
      html += "<ul>";
      node.children.forEach(function (child) { html += renderNode(child); });
      html += "</ul>";
      html += "</details>";
      html += "</li>";
      return html;
    }
    return "<li><a href='" + node.url + "'>" + escapeHtml(node.title) + "</a></li>";
  }

  function escapeHtml(t) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(t));
    return d.innerHTML;
  }
})();
