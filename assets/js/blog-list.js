/*
 * Blog List Redesign — Interaction logic
 * Handles: category filtering, mobile sheet, sidebar scrolling.
 * Search modal is handled globally by search.js.
 */
(function () {
  "use strict";

  // Only run on pages that have the blog list container
  var root = document.querySelector(".blogs-list-page");
  if (!root) return;

  var segments = [].slice.call(document.querySelectorAll(".segment"));
  var sidebarItems = [].slice.call(document.querySelectorAll("[data-sidebar-filter]"));
  var mobileFilters = [].slice.call(document.querySelectorAll(".mobile-filter"));
  var categorySections = [].slice.call(document.querySelectorAll(".category-section"));
  var resultCount = document.getElementById("resultCount");
  var emptyState = document.getElementById("emptyState");
  var sheet = document.getElementById("mobileSheet");
  var backdrop = document.getElementById("sheetBackdrop");
  var menuButton = document.getElementById("mobileMenuButton");
  var activeFilter = "all";

  /* ---------- Filtering ---------- */

  function setFilter(next, scrollTo) {
    activeFilter = next;
    segments.forEach(function (btn) {
      var selected = btn.getAttribute("data-filter") === next;
      btn.classList.toggle("active", selected);
      btn.setAttribute("aria-selected", String(selected));
    });
    sidebarItems.forEach(function (item) {
      item.classList.toggle("active", item.getAttribute("data-sidebar-filter") === next);
    });
    mobileFilters.forEach(function (item) {
      item.classList.toggle("active", item.getAttribute("data-filter") === next);
    });
    applyFilter(scrollTo);
  }

  function applyFilter(scrollTo) {
    var visibleItems = 0;

    categorySections.forEach(function (section) {
      var cat = section.getAttribute("data-section-category");
      var rows = [].slice.call(section.querySelectorAll(".article-row"));
      var match = activeFilter === "all" || cat === activeFilter;
      var sectionVisible = false;

      rows.forEach(function (row) {
        var rowMatch = match;
        row.hidden = !rowMatch;
        if (rowMatch) {
          sectionVisible = true;
          visibleItems += 1;
        }
      });

      section.hidden = !sectionVisible;
    });

    // Update featured cards visibility
    var featuredGrid = document.getElementById("featured");
    if (featuredGrid) {
      var cards = [].slice.call(featuredGrid.querySelectorAll(".featured-card"));
      var featuredVisible = cards.some(function (card) {
        var cat = card.getAttribute("data-category");
        var match = activeFilter === "all" || cat === activeFilter;
        card.hidden = !match;
        return match;
      });
      featuredGrid.hidden = !featuredVisible;
    }

    if (resultCount) {
      resultCount.textContent = "\u663e\u793a " + visibleItems + " \u7bc7\u6587\u7ae0";
    }

    if (emptyState) {
      emptyState.style.display = visibleItems === 0 ? "block" : "none";
    }

    if (scrollTo) {
      var targetSection = document.querySelector(".category-section:not([hidden])");
      if (targetSection) {
        targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }

  /* ---------- Segment buttons ---------- */

  segments.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setFilter(btn.getAttribute("data-filter"), true);
    });
  });

  /* ---------- Sidebar filter items ---------- */

  sidebarItems.forEach(function (item) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      setFilter(item.getAttribute("data-sidebar-filter"), true);
    });
  });

  /* ---------- Mobile sheet ---------- */

  function openSheet() {
    sheet.classList.add("open");
    sheet.setAttribute("aria-hidden", "false");
    backdrop.style.display = "block";
    backdrop.setAttribute("aria-hidden", "false");
    if (menuButton) menuButton.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }

  function closeSheet() {
    sheet.classList.remove("open");
    sheet.setAttribute("aria-hidden", "true");
    backdrop.style.display = "none";
    backdrop.setAttribute("aria-hidden", "true");
    if (menuButton) menuButton.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
  }

  if (menuButton) {
    menuButton.addEventListener("click", function () {
      if (sheet.classList.contains("open")) {
        closeSheet();
      } else {
        openSheet();
      }
    });
  }

  if (backdrop) {
    backdrop.addEventListener("click", closeSheet);
  }

  mobileFilters.forEach(function (item) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      setFilter(item.getAttribute("data-filter"), true);
      closeSheet();
    });
  });

  /* ---------- Keyboard ---------- */

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (sheet && sheet.classList.contains("open")) {
        e.preventDefault();
        closeSheet();
      }
    }
  });

  /* ---------- Mobile menu button visibility ---------- */
  /* Show the mobile menu button on narrow screens */
  function updateMenuButton() {
    if (menuButton) {
      if (window.innerWidth <= 820) {
        menuButton.style.display = "grid";
      } else {
        menuButton.style.display = "none";
      }
    }
  }

  updateMenuButton();
  window.addEventListener("resize", updateMenuButton);

  /* ---------- Initial filter sync ---------- */
  applyFilter(false);
})();
