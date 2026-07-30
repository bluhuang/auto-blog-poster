(function () {
  "use strict";

  var root = document.querySelector("[data-home-guestbook]");
  if (!root) return;

  var composerHost = root.querySelector("[data-giscus-compose]");
  var composerFrame = null;
  var composerCommentCount = null;
  var successTimer = null;
  var moveRetryTimer = null;
  var frameInInteraction = false;
  var lastFocus = null;

  var CONFIG = {
    discussionUrl: "https://github.com/bluhuang/blogs-of-bluhuang/discussions/2",
    composerLight: "https://bluhuang.github.io/blogs-of-bluhuang/css/giscus-apple-composer-light-v2.css?v=20260730-2",
    composerDark: "https://bluhuang.github.io/blogs-of-bluhuang/css/giscus-apple-composer-dark-v2.css?v=20260730-2",
    interactionLight: "https://bluhuang.github.io/blogs-of-bluhuang/css/giscus-apple-interaction-light.css?v=20260730-2",
    interactionDark: "https://bluhuang.github.io/blogs-of-bluhuang/css/giscus-apple-interaction-dark.css?v=20260730-2"
  };

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function composerTheme() {
    return isDark() ? CONFIG.composerDark : CONFIG.composerLight;
  }

  function interactionTheme() {
    return isDark() ? CONFIG.interactionDark : CONFIG.interactionLight;
  }

  function postTheme(frame, theme) {
    if (!frame || !frame.contentWindow) return;
    frame.contentWindow.postMessage(
      { giscus: { setConfig: { theme: theme } } },
      "https://giscus.app"
    );
  }

  function createSuccessToast() {
    var toast = document.createElement("div");
    toast.className = "home-guestbook-submit-toast";
    toast.hidden = true;
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.innerHTML =
      '<span class="home-guestbook-submit-icon" aria-hidden="true">' +
        '<svg width="21" height="21" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6"/><path d="m8.5 12 2.2 2.2 4.8-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      '</span>' +
      '<span class="home-guestbook-submit-copy"><strong>留言发布成功</strong><span>右侧历史留言将在 1 分钟内自动刷新。</span></span>' +
      '<button class="home-guestbook-submit-close" type="button" aria-label="关闭提示">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="m7 7 10 10M17 7 7 17" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' +
      '</button>';
    document.body.appendChild(toast);
    toast.querySelector(".home-guestbook-submit-close").addEventListener("click", hideSuccessToast);
    return toast;
  }

  var successToast = createSuccessToast();

  function hideSuccessToast() {
    window.clearTimeout(successTimer);
    successToast.classList.remove("is-visible");
    window.setTimeout(function () {
      if (!successToast.classList.contains("is-visible")) successToast.hidden = true;
    }, 220);
  }

  function showSuccessToast() {
    window.clearTimeout(successTimer);
    successToast.hidden = false;
    window.requestAnimationFrame(function () {
      successToast.classList.add("is-visible");
    });
    successTimer = window.setTimeout(hideSuccessToast, 12000);
  }

  function createInteractionModal() {
    var modal = document.createElement("div");
    modal.className = "home-guestbook-interaction-modal";
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    modal.innerHTML =
      '<button class="home-guestbook-interaction-backdrop" type="button" aria-label="关闭互动面板"></button>' +
      '<section class="home-guestbook-interaction-dialog" role="dialog" aria-modal="true" aria-labelledby="home-guestbook-interaction-title">' +
        '<header class="home-guestbook-interaction-header">' +
          '<div><h2 id="home-guestbook-interaction-title">点赞、表情与回复</h2><p>在真实 GitHub Discussion 中完成互动。</p></div>' +
          '<div class="home-guestbook-interaction-actions">' +
            '<a class="home-guestbook-interaction-native" href="' + CONFIG.discussionUrl + '" target="_blank" rel="noopener">打开对应留言</a>' +
            '<button class="home-guestbook-interaction-close" type="button" aria-label="关闭">' +
              '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="m7 7 10 10M17 7 7 17" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' +
            '</button>' +
          '</div>' +
        '</header>' +
        '<div class="home-guestbook-interaction-body">' +
          '<div class="home-guestbook-interaction-loading">正在打开真实互动区…</div>' +
          '<div class="home-guestbook-interaction-host" data-giscus-interaction-host></div>' +
        '</div>' +
      '</section>';
    document.body.appendChild(modal);
    modal.querySelector(".home-guestbook-interaction-backdrop").addEventListener("click", closeInteraction);
    modal.querySelector(".home-guestbook-interaction-close").addEventListener("click", closeInteraction);
    return modal;
  }

  var interactionModal = createInteractionModal();
  var interactionHost = interactionModal.querySelector("[data-giscus-interaction-host]");
  var interactionLoading = interactionModal.querySelector(".home-guestbook-interaction-loading");
  var interactionNative = interactionModal.querySelector(".home-guestbook-interaction-native");
  var interactionTitle = interactionModal.querySelector("#home-guestbook-interaction-title");

  function syncFrameTheme() {
    if (!composerFrame) return;
    postTheme(composerFrame, frameInInteraction ? interactionTheme() : composerTheme());
  }

  function bindFrameReady(frame) {
    if (!frame || frame.dataset.homeGuestbookThemeBound === "1") return;
    frame.dataset.homeGuestbookThemeBound = "1";
    frame.addEventListener("load", syncFrameTheme);
    window.setTimeout(syncFrameTheme, 120);
    window.setTimeout(syncFrameTheme, 600);
    window.setTimeout(syncFrameTheme, 1400);
  }

  function locateFrame() {
    composerHost = root.querySelector("[data-giscus-compose]") || composerHost;
    composerFrame =
      (composerHost && composerHost.querySelector("iframe.giscus-frame")) ||
      interactionHost.querySelector("iframe.giscus-frame") ||
      composerFrame;
    bindFrameReady(composerFrame);
    return composerFrame;
  }

  function moveFrameIntoInteraction(attempt) {
    window.clearTimeout(moveRetryTimer);
    var frame = locateFrame();
    if (!frame) {
      if ((attempt || 0) < 30 && interactionModal.classList.contains("is-open")) {
        moveRetryTimer = window.setTimeout(function () {
          moveFrameIntoInteraction((attempt || 0) + 1);
        }, 100);
      }
      return;
    }

    if (frame.parentNode !== interactionHost) interactionHost.appendChild(frame);
    frameInInteraction = true;
    interactionLoading.hidden = true;
    postTheme(frame, interactionTheme());
  }

  function restoreFrameToComposer() {
    window.clearTimeout(moveRetryTimer);
    var frame = locateFrame();
    if (!frame || !composerHost) return;
    if (frame.parentNode !== composerHost) composerHost.appendChild(frame);
    frameInInteraction = false;
    postTheme(frame, composerTheme());
  }

  function openInteraction(url, mode, trigger) {
    lastFocus = trigger || document.activeElement;
    interactionTitle.textContent = mode === "reaction" ? "点赞与添加表情" : "表情与回复";
    interactionNative.href = url || CONFIG.discussionUrl;
    interactionLoading.hidden = false;
    interactionModal.hidden = false;
    interactionModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("home-guestbook-interaction-open");
    window.requestAnimationFrame(function () {
      interactionModal.classList.add("is-open");
      moveFrameIntoInteraction(0);
      interactionModal.querySelector(".home-guestbook-interaction-close").focus();
    });
  }

  function closeInteraction() {
    interactionModal.classList.remove("is-open");
    interactionModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("home-guestbook-interaction-open");
    restoreFrameToComposer();
    window.setTimeout(function () {
      if (!interactionModal.classList.contains("is-open")) interactionModal.hidden = true;
    }, 190);
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  root.addEventListener("click", function (event) {
    var action = event.target.closest(".home-guestbook-comment-action");
    if (!action) return;
    event.preventDefault();
    event.stopPropagation();
    openInteraction(
      action.getAttribute("href") || CONFIG.discussionUrl,
      action.classList.contains("home-guestbook-comment-reply") ? "reply" : "reaction",
      action
    );
  }, true);

  window.addEventListener("message", function (event) {
    if (event.origin !== "https://giscus.app") return;
    var payload = event.data && event.data.giscus;
    var frame = locateFrame();
    if (!payload || !frame || event.source !== frame.contentWindow) return;
    if (!payload.discussion) return;

    var count = Number(payload.discussion.totalCommentCount);
    if (!Number.isFinite(count)) return;

    if (composerCommentCount !== null && count > composerCommentCount) {
      showSuccessToast();
    }
    composerCommentCount = composerCommentCount === null ? count : Math.max(composerCommentCount, count);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && interactionModal.classList.contains("is-open")) {
      event.preventDefault();
      closeInteraction();
    }
  });

  new MutationObserver(function () {
    locateFrame();
    if (!frameInInteraction) syncFrameTheme();
  }).observe(root, { childList: true, subtree: true });

  new MutationObserver(syncFrameTheme).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"]
  });

  locateFrame();
})();