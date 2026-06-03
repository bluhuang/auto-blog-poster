(function() {
  var container = document.getElementById("tree-nav-container");
  if (!container) return;

  fetch("/navigation.json")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var html = "<ul class='tree-nav' style='list-style:none;padding:0'>";
      data.forEach(function(node) { html += renderNode(node); });
      html += "</ul>";
      container.innerHTML = html;
    })
    .catch(function(e) {
      console.warn("tree-nav: failed to load navigation.json", e);
    });

  function renderNode(node) {
    if (node.children && node.children.length) {
      var id = "tree-" + node.title.replace(/\s+/g, "-").toLowerCase();
      var h = "<li style='margin:2px 0'>";
      h += "<details id='" + id + "'>";
      h += "<summary style='cursor:pointer;font-weight:500'>" + escapeHtml(node.title);
      if (node.url) {
        h += " <a href='" + node.url + "' style='text-decoration:none;font-size:0.8em'>&#8599;</a>";
      }
      h += "</summary>";
      h += "<ul style='list-style:none;padding-left:16px'>";
      node.children.forEach(function(child) { h += renderNode(child); });
      h += "</ul>";
      h += "</details>";
      h += "</li>";
      return h;
    }
    return "<li style='margin:2px 0'><a href='" + node.url + "'>" +
      escapeHtml(node.title) + "</a></li>";
  }

  function escapeHtml(t) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(t));
    return d.innerHTML;
  }
})();
