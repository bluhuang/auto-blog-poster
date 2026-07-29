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
  var preview = root.querySelector("[data-guestbook-preview]");
  var history = root.querySelector("[data-guestbook-history]");
  var total = root.querySelector("[data-guestbook-total]");
  var more = root.querySelector("[data-guestbook-more]");
  var toast = root.querySelector("[data-guestbook-toast]");
  var source = root.getAttribute("data-source");
  var discussionUrl = root.getAttribute("data-fallback-url") || "https://github.com/bluhuang/blogs-of-bluhuang/discussions";
  var draftKey = "bluhuang-home-guestbook-draft-v1";
  var toastTimer = null;

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
    try {
      window.localStorage.setItem(draftKey, input.value);
    } catch (_) {
      // Storage can be unavailable in privacy modes; editing should still work.
    }
  }

  function restoreDraft() {
    if (!input) return;
    try {
      var saved = window.localStorage.getItem(draftKey);
      if (saved) input.value = saved.slice(0, 500);
    } catch (_) {
      // Ignore unavailable storage.
    }
    updateCount();
  }

  function insertText(before, after, fallback) {
    if (!input) return;
    var start = input.selectionStart || 0;
    var end = input.selectionEnd || start;
    var selected = input.value.slice(start, end) || fallback;
    var replacement = before + selected + after;
    input.setRangeText(replacement, start, end, "end");
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
    var reactions = document.createElement("span");
    reactions.textContent = "♡ " + Number(comment.reactionCount || 0);
    var link = document.createElement("a");
    link.href = comment.url || discussionUrl;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "查看与回复 ›";
    footer.appendChild(reactions);
    footer.appendChild(link);

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
    if (more && discussionUrl) {
      more.href = discussionUrl;
      more.hidden = false;
    }

    var comments = data && Array.isArray(data.comments) ? data.comments : [];
    var totalCount = data && Number.isFinite(Number(data.totalCount)) ? Number(data.totalCount) : comments.length;
    total.textContent = totalCount + " 条留言";

    if (!data || data.available === false) {
      history.appendChild(createState("暂时无法读取留言", "GitHub 数据同步暂不可用，请稍后刷新或前往 Discussions 查看。"));
      return;
    }

    if (!comments.length) {
      history.appendChild(createState("还没有历史留言", "第一条真实留言发布后会显示在这里。"));
      return;
    }

    comments.forEach(function (comment) {
      history.appendChild(createComment(comment));
    });
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

  async function publishDraft() {
    if (!input) return;
    var text = input.value.trim();
    if (!text) {
      input.focus();
      showToast("先写下一句话");
      return;
    }

    try {
      window.localStorage.setItem(draftKey, input.value);
    } catch (_) {
      // The draft remains in the textarea even if storage is unavailable.
    }

    var copied = false;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch (_) {
      // Clipboard permissions vary by browser.
    }

    var target = discussionUrl + (discussionUrl.indexOf("#") === -1 ? "#new_comment_field" : "");
    window.open(target, "_blank", "noopener");
    showToast(copied ? "内容已复制，请在 GitHub 中粘贴并发布" : "已打开 GitHub；草稿仍保存在本页");
  }

  root.querySelectorAll("[data-guestbook-tool]").forEach(function (button) {
    button.addEventListener("click", function () {
      var action = button.getAttribute("data-guestbook-tool");
      if (action === "markdown") insertText("**", "**", "文字");
      if (action === "image") insertText("![", "](图片链接)", "图片说明");
      if (action === "preview" && preview) {
        preview.hidden = !preview.hidden;
        preview.textContent = input && input.value.trim() ? input.value : "输入内容后可在这里预览。";
      }
    });
  });

  if (input) input.addEventListener("input", updateCount);
  if (publishButton) publishButton.addEventListener("click", publishDraft);

  restoreDraft();
  loadGuestbook();
})();
