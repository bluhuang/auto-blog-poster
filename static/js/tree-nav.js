// Tree Navigation — renders /navigation.json into #tree-nav-container
// 使用 DOM API（document.createElement / textContent）构造节点，
// 避免任何 innerHTML / 字符串拼接，从根本上消除 XSS 注入面。
// 同时对 node.url 做协议白名单校验，丢弃 javascript: / data: 等危险 scheme。

(function () {
  "use strict";

  var container = document.getElementById("tree-nav-container");
  if (!container) return;

  // 协议白名单：仅允许同源相对路径、http(s) 和站内 mailto
  function sanitizeUrl(raw) {
    if (!raw) return null;
    var trimmed = String(raw).trim();
    if (!trimmed) return null;
    // 站内相对路径：/, ./, ../, 或纯相对
    if (trimmed.charAt(0) === "/" || trimmed.charAt(0) === ".") return trimmed;
    try {
      var u = new URL(trimmed, window.location.origin);
      if (u.protocol === "http:" || u.protocol === "https:" || u.protocol === "mailto:") {
        return u.toString();
      }
      return null; // 拒绝 javascript: / data: / vbscript: 等
    } catch (e) {
      return null;
    }
  }

  // 加载失败时的可见提示（兼顾 a11y，role=status 让屏幕阅读器公告）
  function renderError(message) {
    container.innerHTML = "";
    var li = document.createElement("li");
    li.setAttribute("role", "status");
    li.style.cssText = "color:var(--color-text-light,#717171);font-size:0.85em;padding:4px 0";
    li.textContent = message;
    container.appendChild(li);
  }

  // 用基于节点路径的稳定 id，规避标题重复导致的 id 冲突
  function makeNodeId(pathArr) {
    return (
      "tree-" +
      pathArr
        .map(function (seg) {
          return String(seg).replace(/[^\w\u4e00-\u9fa5-]/g, "-");
        })
        .join("-")
    );
  }

  function buildLink(url, text) {
    var safe = sanitizeUrl(url);
    if (!safe) return null;
    var a = document.createElement("a");
    a.href = safe;
    // textContent 自动转义，杜绝 HTML 注入
    a.textContent = text;
    return a;
  }

  function renderNode(node, pathArr) {
    var li = document.createElement("li");
    li.style.margin = "2px 0";

    var hasChildren = Array.isArray(node.children) && node.children.length > 0;
    var title = node.title == null ? "" : String(node.title);

    if (hasChildren) {
      var details = document.createElement("details");
      details.id = makeNodeId(pathArr);

      var summary = document.createElement("summary");
      summary.style.cssText = "cursor:pointer;font-weight:500;list-style:none";
      // 移除默认的 disclosure 三角
      summary.addEventListener("click", function (e) {
        e.preventDefault();
        details.open = !details.open;
      });

      // 标题文本（textContent 自动转义）
      var titleSpan = document.createElement("span");
      titleSpan.textContent = title;
      summary.appendChild(titleSpan);

      // 可选跳转链接
      var link = buildLink(node.url, "↗");
      if (link) {
        link.style.cssText = "text-decoration:none;font-size:0.8em;margin-left:6px";
        link.addEventListener("click", function (e) {
          e.stopPropagation();
        });
        summary.appendChild(link);
      }

      details.appendChild(summary);

      var subUl = document.createElement("ul");
      subUl.style.cssText = "list-style:none;padding-left:16px;margin:0";
      node.children.forEach(function (child, idx) {
        subUl.appendChild(renderNode(child, pathArr.concat([idx])));
      });
      details.appendChild(subUl);

      li.appendChild(details);
    } else {
      var leafLink = buildLink(node.url, title);
      if (leafLink) {
        li.appendChild(leafLink);
      } else {
        // url 非法或缺失：仅展示纯文本，避免点击危险链接
        var span = document.createElement("span");
        span.textContent = title;
        li.appendChild(span);
      }
    }
    return li;
  }

  fetch("/navigation.json", { credentials: "same-origin" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      if (!Array.isArray(data)) throw new Error("navigation.json 格式错误：非数组");
      var ul = document.createElement("ul");
      ul.className = "tree-nav";
      ul.style.cssText = "list-style:none;padding:0;margin:0";
      data.forEach(function (node, idx) {
        ul.appendChild(renderNode(node, [idx]));
      });
      container.innerHTML = "";
      container.appendChild(ul);
    })
    .catch(function (e) {
      console.warn("tree-nav: failed to load navigation.json", e);
      renderError("导航加载失败，请刷新页面");
    });
})();
