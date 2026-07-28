/* Blog Library Browser — folder tree, recent view, mobile sheet. */
(function () {
  "use strict";

  var root = document.querySelector("[data-library-root]");
  if (!root) return;

  var body = document.body;
  var main = document.getElementById("library-main");
  var views = [].slice.call(root.querySelectorAll("[data-library-view]"));
  var recentTriggers = [].slice.call(document.querySelectorAll("[data-library-view-trigger='recent']"));
  var defaultLinks = [].slice.call(document.querySelectorAll("[data-library-default-link]"));
  var menuButton = document.getElementById("mobileMenuButton");
  var sheet = document.getElementById("libraryMobileSheet");
  var backdrop = document.getElementById("librarySheetBackdrop");
  var closeButton = document.getElementById("librarySheetClose");
  var lastSheetTrigger = null;

  body.classList.add("library-page-active");

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function currentViewFromURL() {
    try {
      return new URL(window.location.href).searchParams.get("view") === "recent" ? "recent" : "default";
    } catch (_) {
      return "default";
    }
  }

  function updateURL(view, replace) {
    var url = new URL(window.location.href);
    if (view === "recent") url.searchParams.set("view", "recent");
    else url.searchParams.delete("view");
    window.history[replace ? "replaceState" : "pushState"]({}, "", url.pathname + url.search + url.hash);
  }

  function setView(view, options) {
    options = options || {};
    var next = view === "recent" ? "recent" : "default";

    views.forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-library-view") !== next;
    });
    recentTriggers.forEach(function (trigger) {
      var active = next === "recent";
      trigger.classList.toggle("is-active", active);
      trigger.setAttribute("aria-pressed", String(active));
    });
    defaultLinks.forEach(function (link) {
      if (next === "recent") link.classList.remove("is-active");
    });

    if (options.updateURL) updateURL(next, Boolean(options.replace));
    if (options.scroll && main) {
      main.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    }
    closeSheet(false);
  }

  recentTriggers.forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      setView("recent", { updateURL: true, scroll: true });
    });
  });

  function setTreeExpanded(key, expanded) {
    [].slice.call(document.querySelectorAll("[data-library-tree-node]")).forEach(function (node) {
      if (node.getAttribute("data-library-tree-node") !== key) return;
      node.classList.toggle("is-expanded", expanded);
      var toggle = node.querySelector(":scope > .library-tree-row [data-library-tree-toggle]");
      if (toggle) {
        toggle.setAttribute("aria-expanded", String(expanded));
        var label = toggle.getAttribute("aria-label") || "";
        toggle.setAttribute("aria-label", label.replace(/^(展开|收起)/, expanded ? "收起" : "展开"));
      }
    });
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-library-tree-toggle]");
    if (!toggle) return;
    event.preventDefault();
    event.stopPropagation();
    var node = toggle.closest("[data-library-tree-node]");
    if (!node) return;
    setTreeExpanded(node.getAttribute("data-library-tree-node"), !node.classList.contains("is-expanded"));
  });

  function openSheet() {
    if (!sheet || !backdrop) return;
    lastSheetTrigger = document.activeElement;
    sheet.classList.add("is-open");
    sheet.setAttribute("aria-hidden", "false");
    backdrop.classList.add("is-open");
    backdrop.setAttribute("aria-hidden", "false");
    if (menuButton) menuButton.setAttribute("aria-expanded", "true");
    body.style.overflow = "hidden";
    window.requestAnimationFrame(function () {
      if (closeButton) closeButton.focus();
    });
  }

  function closeSheet(restoreFocus) {
    if (!sheet || !backdrop) return;
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    backdrop.classList.remove("is-open");
    backdrop.setAttribute("aria-hidden", "true");
    if (menuButton) menuButton.setAttribute("aria-expanded", "false");
    body.style.overflow = "";
    if (restoreFocus !== false && lastSheetTrigger && typeof lastSheetTrigger.focus === "function") {
      lastSheetTrigger.focus();
    }
  }

  if (menuButton) {
    menuButton.addEventListener("click", function () {
      if (sheet && sheet.classList.contains("is-open")) closeSheet(true);
      else openSheet();
    });
  }
  if (closeButton) closeButton.addEventListener("click", function () { closeSheet(true); });
  if (backdrop) backdrop.addEventListener("click", function () { closeSheet(true); });

  if (sheet) {
    sheet.addEventListener("click", function (event) {
      if (event.target.closest("a[href]")) closeSheet(false);
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sheet && sheet.classList.contains("is-open")) {
      event.preventDefault();
      closeSheet(true);
    }
  });

  function updateMobileButton() {
    if (!menuButton) return;
    menuButton.style.display = window.innerWidth <= 820 ? "grid" : "none";
    if (window.innerWidth > 820) closeSheet(false);
  }

  window.addEventListener("resize", updateMobileButton);
  window.addEventListener("popstate", function () {
    setView(currentViewFromURL(), { updateURL: false, scroll: false });
  });

  updateMobileButton();
  setView(currentViewFromURL(), { updateURL: false, scroll: false });
})();
