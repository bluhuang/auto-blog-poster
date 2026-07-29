(function () {
  "use strict";

  var page = document.querySelector("[data-home-redesign]");
  if (!page) return;
  document.body.classList.add("home-redesign-active");

  var root = document.querySelector("[data-home-guestbook]");
  if (!root) return;

  var composeCard = root.querySelector(".home-guestbook-compose-final");
  var history = root.querySelector("[data-guestbook-history]");
  var total = root.querySelector("[data-guestbook-total]");
  var more = root.querySelector("[data-guestbook-more]");
  var source = root.getAttribute("data-source");
  var discussionUrl = "https://github.com/bluhuang/blogs-of-bluhuang/discussions/2";
  var giscusHost = null;
  var giscusLoading = null;
  var currentFingerprint = "";
  var requestSerial = 0;
  var refreshTimer = null;
  var burstTimers = [];
  var lastMetadataSignal = null;
  var lastAcceptedTotal = null;
  var lastAcceptedGeneratedAt = 0;
  var pendingRegressionKey = "";
  var pendingRegressionSince = 0;

  var POLL_INTERVAL_MS = 5000;
  var REGRESSION_CONFIRM_MS = 4500;

  var GISCUS_CONFIG = {
    repo: "bluhang/blogs-of-bluhuang".replace("bluhang", "bluhuang"),
    repoId: "R_kgDOStnEPg",
    category: "Announcements",
    categoryId: "DIC_kwDOStnEPs4C-eIQ",
    term: "blogs-of-bluhuang/guestbook/",
    lightTheme: "https://bluhuang.github.io/blogs-of-bluhuang/css/giscus-apple-composer-light.css?v=20260729-1",
    darkTheme: "https://bluhuang.github.io/blogs-of-bluhuang/css/giscus-apple-composer-dark.css?v=20260729-1"
  };

  function mountRealComposer() {
    if (!composeCard) return;

    giscusHost = composeCard.querySelector("[data-giscus-compose]");
    giscusLoading = composeCard.querySelector("[data-giscus-loading]");
    if (giscusHost) return;

    composeCard.innerHTML =
      '<header class="home-guestbook-compose-header">' +
        '<div class="home-guestbook-compose-title">' +
          '<span class="home-guestbook-final-icon" aria-hidden="true">' +
            '<svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M6.5 5.25h11A2.75 2.75 0 0 1 20.25 8v6.25A2.75 2.75 0 0 1 17.5 17H11l-4.75 3v-3H6.5a2.75 2.75 0 0 1-2.75-2.75V8A2.75 2.75 0 0 1 6.5 5.25Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 10h8M8 13h5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>' +
          '</span>' +
          '<div><h2 id="home-guestbook-title">在这里留下一句话</h2><p>写下想聊的内容，登录 GitHub 后直接发布。</p></div>' +
        '</div>' +
        '<a class="home-giscus-upload-link" href="' + discussionUrl + '#new_comment_field" target="_blank" rel="noopener">添加图片</a>' +
      '</header>' +
      '<div class="home-giscus-compose-shell" data-giscus-shell>' +
        '<div class="home-giscus-compose-loading" data-giscus-loading>正在连接 GitHub Discussions…</div>' +
        '<div class="giscus home-giscus-compose" data-giscus-compose></div>' +
      '</div>';

    giscusHost = composeCard.querySelector("[data-giscus-compose]");
    giscusLoading = composeCard.querySelector("[data-giscus-loading]");
  }

  function getGiscusTheme() {
    return document.documentElement.classList.contains("dark")
      ? GISCUS_CONFIG.darkTheme
      : GISCUS_CONFIG.lightTheme;
  }

  function markGiscusReady() {
    if (!giscusHost) return;
    giscusHost.classList.add("is-ready");
    if (giscusLoading) giscusLoading.hidden = true;
  }

  function loadGiscus() {
    if (!giscusHost || giscusHost.querySelector("iframe.giscus-frame") || giscusHost.querySelector("script[src*='giscus.app/client.js']")) return;

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
    giscusHost.appendChild(script);

    new MutationObserver(function () {
      var frame = giscusHost.querySelector("iframe.giscus-frame");
      if (!frame) return;
      markGiscusReady();
      frame.addEventListener("load", markGiscusReady, { once: true });
    }).observe(giscusHost, { childList: true, subtree: true });
  }

  function syncGiscusTheme() {
    if (!giscusHost) return;
    var frame = giscusHost.querySelector("iframe.giscus-frame");
    if (!frame || !frame.contentWindow) return;
    frame.contentWindow.postMessage(
      { giscus: { setConfig: { theme: getGiscusTheme() } } },
      "https://giscus.app"
    );
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

  function configureExternalAction(element, url) {
    element.href = url || discussionUrl;
    element.target = "_blank";
    element.rel = "noopener";
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
    var reactions = document.createElement("a");
    reactions.className = "home-guestbook-comment-action";
    reactions.textContent = "♡ " + Number(comment.reactionCount || 0);
    reactions.setAttribute("aria-label", "添加表情");
    configureExternalAction(reactions, comment.url);
    var reply = document.createElement("a");
    reply.className = "home-guestbook-comment-action home-guestbook-comment-reply";
    reply.textContent = "表情与回复 ›";
    configureExternalAction(reply, comment.url);
    footer.appendChild(reactions);
    footer.appendChild(reply);

    content.appendChild(meta);
    content.appendChild(body);
    content.appendChild(footer);
    article.appendChild(avatar);
    article.appendChild(content);
    return article;
  }

  function fingerprint(data) {
    var comments = data && Array.isArray(data.comments) ? data.comments : [];
    return [
      data && data.available,
      data && data.totalCount,
      comments.map(function (comment) {
        return [comment.id, comment.updatedAt, comment.reactionCount, comment.bodyText].join(":");
      }).join("|")
    ].join("::");
  }

  function shouldAcceptSnapshot(data) {
    var nextTotal = Number(data && data.totalCount);
    var generatedAt = Date.parse(data && data.generatedAt) || 0;
    var comments = data && Array.isArray(data.comments) ? data.comments : [];

    if (lastAcceptedGeneratedAt && generatedAt && generatedAt < lastAcceptedGeneratedAt) return false;

    if (lastAcceptedTotal !== null && Number.isFinite(nextTotal) && nextTotal < lastAcceptedTotal) {
      var regressionKey = nextTotal + "|" + comments.map(function (comment) { return comment.id; }).join("|");
      var now = Date.now();
      if (pendingRegressionKey !== regressionKey) {
        pendingRegressionKey = regressionKey;
        pendingRegressionSince = now;
        return false;
      }
      if (now - pendingRegressionSince < REGRESSION_CONFIRM_MS) return false;
    } else {
      pendingRegressionKey = "";
      pendingRegressionSince = 0;
    }

    if (Number.isFinite(nextTotal)) lastAcceptedTotal = nextTotal;
    if (generatedAt) lastAcceptedGeneratedAt = Math.max(lastAcceptedGeneratedAt, generatedAt);
    return true;
  }

  function renderGuestbook(data) {
    if (!history || !total) return;
    var oldScrollTop = history.scrollTop;
    var wasAtTop = oldScrollTop < 8;

    history.replaceChildren();
    history.setAttribute("tabindex", "0");
    history.setAttribute("aria-label", "历史留言，可上下滚动");

    if (data && data.discussionUrl) discussionUrl = data.discussionUrl;
    if (more) {
      more.href = discussionUrl;
      more.hidden = false;
    }

    var comments = data && Array.isArray(data.comments) ? data.comments : [];
    var totalCount = data && Number.isFinite(Number(data.totalCount))
      ? Number(data.totalCount)
      : comments.length;
    total.textContent = totalCount + " 条留言";

    if (!data || data.available === false) {
      history.appendChild(createState("暂时无法读取留言", "稍后会自动重新连接。"));
      return;
    }
    if (!comments.length) {
      history.appendChild(createState("还没有历史留言", "第一条留言发布后会显示在这里。"));
      return;
    }

    comments.forEach(function (comment) {
      history.appendChild(createComment(comment));
    });

    if (wasAtTop) {
      history.scrollTop = 0;
    } else {
      history.scrollTop = Math.min(oldScrollTop, Math.max(0, history.scrollHeight - history.clientHeight));
    }
  }

  async function loadGuestbook(force) {
    if (!source) {
      if (!currentFingerprint) renderGuestbook({ available: false, comments: [] });
      return;
    }

    var serial = ++requestSerial;
    try {
      var separator = source.indexOf("?") === -1 ? "?" : "&";
      var url = source + separator + "_rt=" + Date.now();
      var response = await window.fetch(url, {
        cache: "no-store",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Cache-Control": "no-cache",
          Pragma: "no-cache"
        }
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      var data = await response.json();
      if (serial !== requestSerial) return;
      if (!shouldAcceptSnapshot(data)) return;
      var nextFingerprint = fingerprint(data);
      if (!force && nextFingerprint === currentFingerprint) return;
      currentFingerprint = nextFingerprint;
      renderGuestbook(data);
    } catch (_) {
      if (!currentFingerprint) {
        renderGuestbook({ available: false, comments: [], discussionUrl: discussionUrl });
      }
    }
  }

  function clearBurstTimers() {
    burstTimers.forEach(function (timer) { window.clearTimeout(timer); });
    burstTimers = [];
  }

  function scheduleBurstRefresh() {
    clearBurstTimers();
    [500, 1500, 3000, 5000, 8000, 12000, 20000, 30000, 45000, 60000].forEach(function (delay) {
      burstTimers.push(window.setTimeout(function () {
        loadGuestbook(true);
      }, delay));
    });
  }

  function startRealtimeRefresh() {
    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(function () {
      if (!document.hidden) loadGuestbook(false);
    }, POLL_INTERVAL_MS);
  }

  window.addEventListener("message", function (event) {
    if (event.origin !== "https://giscus.app") return;
    var payload = event.data && event.data.giscus;
    if (!payload) return;
    markGiscusReady();

    if (payload.discussion) {
      var commentCount = Number(payload.discussion.totalCommentCount);
      if (Number.isFinite(commentCount) && total) {
        total.textContent = commentCount + " 条留言";
      }

      var signal = [
        payload.discussion.totalCommentCount,
        payload.discussion.totalReplyCount,
        payload.discussion.reactionCount
      ].join(":");

      if (
        (lastMetadataSignal !== null && signal !== lastMetadataSignal) ||
        (lastAcceptedTotal !== null && Number.isFinite(commentCount) && commentCount !== lastAcceptedTotal)
      ) {
        scheduleBurstRefresh();
      }
      lastMetadataSignal = signal;
    }
  });

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) loadGuestbook(true);
  });
  window.addEventListener("focus", function () { loadGuestbook(true); });
  window.addEventListener("online", function () { loadGuestbook(true); });

  new MutationObserver(syncGiscusTheme).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"]
  });

  mountRealComposer();
  loadGiscus();
  loadGuestbook(true);
  startRealtimeRefresh();
})();