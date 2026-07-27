(function () {
  "use strict";

  var tocNav = document.getElementById("article-toc-nav");
  var drawerNav = document.getElementById("article-toc-drawer-nav");
  var trigger = document.getElementById("article-toc-trigger");
  var drawer = document.getElementById("article-toc-drawer");
  var overlay = document.getElementById("article-toc-overlay");
  var closeBtn = document.getElementById("article-toc-drawer-close");

  if (!tocNav && !drawerNav) return;

  var tocItems = [];
  var observer = null;
  var lastActiveId = null;

  function cloneHeadingContent(heading) {
    var clone = heading.cloneNode(true);
    var anchors = clone.querySelectorAll("a[href^='#']");
    for (var i = 0; i < anchors.length; i++) {
      anchors[i].parentNode.removeChild(anchors[i]);
    }
    var mathml = clone.querySelectorAll(".katex-mathml");
    for (var j = 0; j < mathml.length; j++) {
      mathml[j].parentNode.removeChild(mathml[j]);
    }
    return clone.innerHTML;
  }

  function buildTocItem(heading) {
    var id = heading.id;
    var level = parseInt(heading.tagName.charAt(1), 10);
    var html = cloneHeadingContent(heading);
    return { id: id, level: level, html: html, el: heading, links: [] };
  }

  function buildToc() {
    tocItems = [];
    var headings = document.querySelectorAll(
      ".article-content h2, .article-content h3"
    );
    for (var i = 0; i < headings.length; i++) {
      tocItems.push(buildTocItem(headings[i]));
    }
  }

  function createTocLink(item) {
    var a = document.createElement("a");
    a.href = "#" + item.id;
    a.className = item.level === 3 ? "toc-h3" : "";
    a.innerHTML = item.html;
    a.addEventListener("click", function (e) {
      e.preventDefault();
      var target = document.getElementById(item.id);
      if (target) {
        target.scrollIntoView({ behavior: "smooth" });
        history.replaceState(null, "", "#" + item.id);
      }
      closeDrawer();
    });
    return a;
  }

  function renderTocNav() {
    if (!tocNav) return;
    tocNav.innerHTML = "";
    for (var i = 0; i < tocItems.length; i++) {
      var link = createTocLink(tocItems[i]);
      tocItems[i].links.push(link);
      tocNav.appendChild(link);
    }
  }

  function renderDrawerNav() {
    if (!drawerNav) return;
    drawerNav.innerHTML = "";
    for (var i = 0; i < tocItems.length; i++) {
      var link = createTocLink(tocItems[i]);
      tocItems[i].links.push(link);
      drawerNav.appendChild(link);
    }
  }

  function setActiveToc(id) {
    if (id === lastActiveId) return;
    lastActiveId = id;
    for (var i = 0; i < tocItems.length; i++) {
      var item = tocItems[i];
      var isActive = item.id === id;
      for (var j = 0; j < item.links.length; j++) {
        var cls = item.links[j].classList;
        if (isActive) {
          cls.add("toc-active");
        } else {
          cls.remove("toc-active");
        }
      }
    }
  }

  function scrollTocToActive() {
    if (!tocNav) return;
    var activeLink = tocNav.querySelector(".toc-active");
    if (!activeLink) return;
    var navRect = tocNav.getBoundingClientRect();
    var linkRect = activeLink.getBoundingClientRect();
    if (linkRect.top < navRect.top || linkRect.bottom > navRect.bottom) {
      activeLink.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  function setupScrollSpy() {
    if (observer) observer.disconnect();

    var headings = [];
    for (var i = 0; i < tocItems.length; i++) {
      headings.push(tocItems[i].el);
    }

    if (!headings.length) return;

    observer = new IntersectionObserver(
      function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) {
            setActiveToc(entries[i].target.id);
            scrollTocToActive();
          }
        }
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: 0 }
    );

    for (var j = 0; j < headings.length; j++) {
      observer.observe(headings[j]);
    }
  }

  function openDrawer() {
    if (!drawer || !overlay) return;
    drawer.setAttribute("aria-hidden", "false");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (closeBtn) closeBtn.focus();
  }

  function closeDrawer() {
    if (!drawer || !overlay) return;
    drawer.setAttribute("aria-hidden", "true");
    overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (trigger) trigger.focus();
  }

  function handleKeyDown(e) {
    if (e.key === "Escape" && drawer && drawer.getAttribute("aria-hidden") === "false") {
      closeDrawer();
    }
  }

  if (trigger) {
    trigger.addEventListener("click", openDrawer);
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", closeDrawer);
  }
  if (overlay) {
    overlay.addEventListener("click", closeDrawer);
  }
  document.addEventListener("keydown", handleKeyDown);

  function init() {
    buildToc();
    if (!tocItems.length) return;
    renderTocNav();
    renderDrawerNav();
    setupScrollSpy();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
