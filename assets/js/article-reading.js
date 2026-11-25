(function () {
  "use strict";
  let updateReadingProgress = () => {};
  function initArticleMetrics() {
      const article = document.getElementById("article-content");
      const readingTime = document.getElementById("article-reading-time");
      const wordCount = document.getElementById("article-word-count");
      const pageProgress = document.getElementById("article-reading-progress-bar");
      const tocProgress = document.getElementById("article-toc-progress-bar");
      const tocPercent = document.getElementById("article-toc-percent");
      if (!article || !readingTime || !wordCount) return;
      if (!article.textContent.trim() || article.closest('[data-private-workspace][hidden]')) {
        readingTime.textContent = "";
        wordCount.textContent = "";
        if (pageProgress) pageProgress.style.width = "0%";
        if (tocProgress) tocProgress.style.width = "0%";
        if (tocPercent) tocPercent.textContent = "0%";
        updateReadingProgress = () => {};
        return;
      }

      const clone = article.cloneNode(true);
      let codeCharacters = 0;
      const proseBlockLanguages = new Set(["", "text", "test", "txt", "plaintext", "plain", "mermaid"]);

      clone.querySelectorAll("pre").forEach((node) => {
        const wrapperLanguage = node.closest("[data-language]")?.getAttribute("data-language") || "";
        const codeLanguage = node.querySelector("code")?.getAttribute("data-lang") || "";
        const classLanguage = Array.from(node.querySelector("code")?.classList || []).find((name) => name.startsWith("language-"))?.slice(9) || "";
        const language = (wrapperLanguage || codeLanguage || classLanguage).toLowerCase();
        const isMermaid = node.classList.contains("mermaid");
        if (!isMermaid && !proseBlockLanguages.has(language)) codeCharacters += node.textContent.trim().length;
        node.remove();
      });

      clone.querySelectorAll("script, style, template, noscript, svg, .katex, .mermaid, [aria-hidden='true']").forEach((node) => node.remove());

      const text = clone.textContent.replace(/\s+/g, " ").trim();
      const chineseCharacters = (text.match(/[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/g) || []).length;
      const englishText = text.replace(/[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/g, " ");
      const englishWords = (englishText.match(/\b[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*\b/g) || []).length;
      const minutes = Math.max(1, Math.ceil(chineseCharacters / 450 + englishWords / 230 + codeCharacters / 360));

      readingTime.textContent = `约 ${minutes} 分钟`;
      wordCount.textContent = `${chineseCharacters} 字 · ${englishWords} 词`;

      updateReadingProgress = () => {
        const articleTop = article.getBoundingClientRect().top + window.scrollY;
        const articleHeight = Math.max(1, article.offsetHeight);
        const viewportAnchor = window.scrollY + window.innerHeight * 0.35;
        const progress = Math.max(0, Math.min(1, (viewportAnchor - articleTop) / articleHeight));
        const percentage = Math.round(progress * 100);
        if (pageProgress) pageProgress.style.width = `${percentage}%`;
        if (tocProgress) tocProgress.style.width = `${percentage}%`;
        if (tocPercent) tocPercent.textContent = `${percentage}%`;
      };

      updateReadingProgress();
  }
  window.addEventListener("scroll", () => updateReadingProgress(), {passive:true});
  window.addEventListener("resize", () => updateReadingProgress());
  document.addEventListener("article:updated", initArticleMetrics);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initArticleMetrics);
  else initArticleMetrics();
})();

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
        if (!target.closest("[data-private-space]")) history.replaceState(null, "", "#" + item.id);
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
    if (observer) observer.disconnect();
    lastActiveId = null;
    buildToc();
    renderTocNav();
    renderDrawerNav();
    if (!tocItems.length) { closeDrawer(); return; }
    setupScrollSpy();
  }

  document.addEventListener("article:updated", init);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
