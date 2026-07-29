(function () {
  "use strict";

  var page = document.querySelector("[data-home-redesign]");
  if (!page) return;
  document.body.classList.add("home-redesign-active");

  var root = document.querySelector("[data-home-guestbook]");
  if (!root) return;

  var input = root.querySelector("[data-guestbook-input]");
  var count = root.querySelector("[data-guestbook-count]");
  var publishButton = root.querySelector("[data-guestbook-publish]");
  var history = root.querySelector("[data-guestbook-history]");
  var total = root.querySelector("[data-guestbook-total]");
  var more = root.querySelector("[data-guestbook-more]");
  var toast = root.querySelector("[data-guestbook-toast]");
  var source = root.getAttribute("data-source");
  var discussionUrl = "https://github.com/bluhuang/blogs-of-bluhuang/discussions/2";
  var draftKey = "bluhuang-home-guestbook-draft-v1";
  var toastTimer = null;
  var modal = null;
  var modalClose = null;
  var modalGiscusRoot = null;
  var previousFocus = null;
  var giscusLoaded = false;
  var refreshTimer = null;

  var GISCUS_CONFIG = {
    repo: "bluhuang/blogs-of-bluhuang",
    repoId: "R_kgDOStnEPg",
    category: "Announcements",
    categoryId: "DIC_kwDOStnEPs4C-eIQ",
    term: "blogs-of-bluhuang/guestbook/"
  };

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 2600);
  }

  function updateCount() {
    if (!input || !count) return;
    count.textContent = input.value.length + "/500";
    try { window.localStorage.setItem(draftKey, input.value); } catch (_) {}
  }

  function restoreDraft() {
    if (!input) return;
    try {
      var saved = window.localStorage.getItem(draftKey);
      if (saved) input.value = saved.slice(0, 500);
    } catch (_) {}
    updateCount();
  }

  function insertText(before, after, fallback) {
    if (!input) return;
    var start = input.selectionStart || 0;
    var end = input.selectionEnd || start;
    var selected = input.value.slice(start, end) || fallback;
    input.setRangeText(before + selected + after, start, end, "end");
    input.focus();
    updateCount();
  }

  function formatTime(value) {
    if (!value) return "";
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    var deltaSeconds = Math.round((date.getTime() - Date.now()) / 1000);
    var abs = Math.abs(deltaSeconds);
    var unit = "second";
    var amount = deltaSeconds;
    if (abs >= 86400) {
      unit = "day";
      amount = Math.round(deltaSeconds / 86400);
    } else if (abs >= 3600) {
      unit = "hour";
      amount = Math.round(deltaSeconds / 3600);
    } else if (abs >= 60) {
      unit = "minute";
      amount = Math.round(deltaSeconds / 60);
    }
    try {
      return new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" }).format(amount, unit);
    } catch (_) {
      return date.toLocaleDateString("zh-CN");
    }
  }

  function createState(title, description) {
    var state = document.createElement("div");
    state.className = "home-guestbook-history-state";
    var icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = '<svg width="21" height="21" viewBox="0 0 24 24" fill="none"><path d="M6.5 5.25h11A2.75 2.75 0 0 1 20.25 8v6.25A2.75 2.75 0 0 1 17.5 17H11l-4.75 3v-3H6.5a2.75 2.75 0 0 1-2.75-2.75V8A2.75 2.75 0 0 1 6.5 5.25Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    var copy = document.createElement("div");
    var strong = document.createElement("strong");
    var paragraph = document.createElement("p");
    strong.textContent = title;
    paragraph.textContent = description;
    copy.appendChild(strong);
    copy.appendChild(paragraph);
    state.appendChild(icon);
    state.appendChild(copy);
    return state;
  }

  function createComment(comment) {
    var article = document.createElement("article");
    article.className = "home-guestbook-comment";
    var avatar = document.createElement("span");
    avatar.className = "home-guestbook-comment-avatar";
    var author = comment.author || {};
    if (author.avatarUrl) {
      var image = document.createElement("img");
      image.src = author.avatarUrl;
      image.alt = "";
      image.loading = "lazy";
      image.referrerPolicy = "no-referrer";
      avatar.appendChild(image);
    } else {
      avatar.textContent = String(author.login || "?").slice(0, 1).toUpperCase();
    }

    var content = document.createElement("div");
    var meta = document.createElement("div");
    meta.className = "home-guestbook-comment-meta";
    var name = document.createElement("strong");
    name.textContent = author.login || "GitHub User";
    var time = document.createElement("time");
    time.dateTime = comment.createdAt || "";
    time.textContent = formatTime(comment.createdAt);
    meta.appendChild(name);
    meta.appendChild(time);

    var body = document.createElement("p");
    body.className = "home-guestbook-comment-body";
    body.textContent = comment.bodyText || "";

    var footer = document.createElement("div");
    footer.className = "home-guestbook-comment-footer";
    var reactions = document.createElement("button");
    reactions.type = "button";
    reactions.className = "home-guestbook-comment-action";
    reactions.textContent = "♡ " + Number(comment.reactionCount || 0);
    reactions.setAttribute("aria-label", "添加表情");
    var reply = document.createElement("button");
    reply.type = "button";
    reply.className = "home-guestbook-comment-action home-guestbook-comment-reply";
    reply.textContent = "表情与回复 ›";
    reactions.addEventListener("click", function () { openGiscus(false); });
    reply.addEventListener("click", function () { openGiscus(false); });
    footer.appendChild(reactions);
    footer.appendChild(reply);

    content.appendChild(meta);
    content.appendChild(body);
    content.appendChild(footer);
    article.appendChild(avatar);
    article.appendChild(content);
    return article;
  }

  function renderGuestbook(data) {
    if (!history || !total) return;
    history.replaceChildren();
    if (data && data.discussionUrl) discussionUrl = data.discussionUrl;
    if (more) {
      more.href = discussionUrl;
      more.hidden = false;
    }
    var comments = data && Array.isArray(data.comments) ? data.comments : [];
    var totalCount = data && Number.isFinite(Number(data.totalCount)) ? Number(data.totalCount) : comments.length;
    total.textContent = totalCount + " 条留言";
    if (!data || data.available === false) {
      history.appendChild(createState("暂时无法读取留言", "打开完整留言板仍可继续留言和互动。"));
      return;
    }
    if (!comments.length) {
      history.appendChild(createState("还没有历史留言", "第一条留言发布后会显示在这里。"));
      return;
    }
    comments.forEach(function (comment) { history.appendChild(createComment(comment)); });
  }

  async function loadGuestbook() {
    if (!source) {
      renderGuestbook({ available: false, comments: [] });
      return;
    }
    try {
      var response = await window.fetch(source, { cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      renderGuestbook(await response.json());
    } catch (_) {
      renderGuestbook({ available: false, comments: [], discussionUrl: discussionUrl });
    }
  }

  function getGiscusTheme() {
    return document.documentElement.classList.contains("dark") ? "noborder_dark" : "noborder_light";
  }

  function syncGiscusTheme() {
    if (!modal) return;
    var frame = modal.querySelector("iframe.giscus-frame");
    if (!frame || !frame.contentWindow) return;
    frame.contentWindow.postMessage({ giscus: { setConfig: { theme: getGiscusTheme() } } }, "https://giscus.app");
  }

  function createGiscusModal() {
    if (modal) return;
    modal = document.createElement("div");
    modal.className = "home-giscus-modal";
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    modal.innerHTML = '<div class="home-giscus-backdrop" data-giscus-close></div>' +
      '<section class="home-giscus-dialog" role="dialog" aria-modal="true" aria-labelledby="home-giscus-title">' +
      '<header class="home-giscus-dialog-header"><div><h2 id="home-giscus-title">留言与互动</h2><p>登录 GitHub 后可发布、回复和添加表情。</p></div>' +
      '<div class="home-giscus-header-actions"><button class="home-giscus-native-link" type="button" data-giscus-image>添加图片</button>' +
      '<button class="home-giscus-close" type="button" aria-label="关闭" data-giscus-close><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button></div></header>' +
      '<div class="home-giscus-dialog-body"><div class="home-giscus-loading" data-giscus-loading>正在加载 GitHub Discussion…</div><div class="home-giscus-root" data-giscus-root></div></div>' +
      '</section>';
    document.body.appendChild(modal);
    modalClose = modal.querySelector(".home-giscus-close");
    modalGiscusRoot = modal.querySelector("[data-giscus-root]");
    modal.querySelectorAll("[data-giscus-close]").forEach(function (element) {
      element.addEventListener("click", closeGiscus);
    });
    modal.querySelector("[data-giscus-image]").addEventListener("click", function () {
      openNativeDiscussion(true);
    });
  }

  function loadGiscus() {
    if (giscusLoaded || !modalGiscusRoot) return;
    giscusLoaded = true;
    var script = document.createElement("script");
    script.src = "https://giscus.app/client.js";
    script.setAttribute("data-repo", GISCUS_CONFIG.repo);
    script.setAttribute("data-repo-id", GISCUS_CONFIG.repoId);
    script.setAttribute("data-category", GISCUS_CONFIG.category);
    script.setAttribute("data-category-id", GISCUS_CONFIG.categoryId);
    script.setAttribute("data-mapping", "specific");
    script.setAttribute("data-term", GISCUS_CONFIG.term);
    script.setAttribute("data-strict", "1");
    script.setAttribute("data-reactions-enabled", "1");
    script.setAttribute("data-emit-metadata", "1");
    script.setAttribute("data-input-position", "top");
    script.setAttribute("data-theme", getGiscusTheme());
    script.setAttribute("data-lang", "zh-CN");
    script.setAttribute("crossorigin", "anonymous");
    script.async = true;
    modalGiscusRoot.appendChild(script);
  }

  function copyDraft() {
    if (!input || !input.value.trim() || !navigator.clipboard || !navigator.clipboard.writeText) return;
    navigator.clipboard.writeText(input.value.trim()).then(function () {
      showToast("草稿已复制，可直接粘贴到留言框");
    }).catch(function () {});
  }

  function openNativeDiscussion(shouldCopyDraft) {
    var target = discussionUrl + (discussionUrl.indexOf("#") === -1 ? "#new_comment_field" : "");
    var opened = window.open(target, "_blank", "noopener");
    if (shouldCopyDraft) copyDraft();
    if (!opened) showToast("浏览器阻止了新窗口，请允许弹窗后重试");
  }

  function openGiscus(shouldCopyDraft) {
    createGiscusModal();
    previousFocus = document.activeElement;
    if (shouldCopyDraft) copyDraft();
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("home-giscus-open");
    window.requestAnimationFrame(function () {
      modal.classList.add("is-open");
      if (modalClose) modalClose.focus();
    });
    loadGiscus();
    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(loadGuestbook, 30000);
  }

  function closeGiscus() {
    if (!modal || modal.hidden) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("home-giscus-open");
    window.clearInterval(refreshTimer);
    window.setTimeout(function () {
      modal.hidden = true;
      if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
    }, 180);
    loadGuestbook();
  }

  root.querySelectorAll("[data-guestbook-tool]").forEach(function (button) {
    button.addEventListener("click", function () {
      var action = button.getAttribute("data-guestbook-tool");
      if (action === "markdown") insertText("**", "**", "文字");
      if (action === "image") openNativeDiscussion(true);
      if (action === "preview") openGiscus(true);
    });
  });

  if (input) input.addEventListener("input", updateCount);
  if (publishButton) publishButton.addEventListener("click", function () { openGiscus(true); });
  if (more) more.addEventListener("click", function (event) {
    event.preventDefault();
    openGiscus(false);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && modal && !modal.hidden) closeGiscus();
  });

  window.addEventListener("message", function (event) {
    if (event.origin !== "https://giscus.app") return;
    var payload = event.data && event.data.giscus;
    if (!payload) return;
    var loading = modal && modal.querySelector("[data-giscus-loading]");
    if (loading) loading.hidden = true;
    if (payload.discussion && total) {
      var metadataCount = Number(payload.discussion.totalCommentCount);
      if (Number.isFinite(metadataCount)) total.textContent = metadataCount + " 条留言";
    }
  });

  new MutationObserver(syncGiscusTheme).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"]
  });

  restoreDraft();
  loadGuestbook();
})();