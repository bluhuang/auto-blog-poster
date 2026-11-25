(() => {
  "use strict";
  const root = document.querySelector("[data-private-space]");
  if (!root) return;
  // This isolated page loads no global analytics, advertising or CDN scripts.
  const preferredDark = matchMedia("(prefers-color-scheme: dark)");
  const applyTheme = () => {
    document.documentElement.classList.toggle("dark", preferredDark.matches);
    document.body.classList.toggle("dark", preferredDark.matches);
  };
  applyTheme();
  preferredDark.addEventListener("change", applyTheme);
  const form = root.querySelector("[data-private-form]");
  const password = form.querySelector("input[type=password]");
  const submit = root.querySelector("[data-private-submit]");
  const gate = root.querySelector("[data-private-gate]");
  const workspace = root.querySelector("[data-private-workspace]");
  const lockButton = root.querySelector("[data-private-lock]");
  const status = root.querySelector("[data-private-status]");
  const tree = root.querySelector("[data-private-tree]");
  const title = root.querySelector("[data-private-note-title]");
  const content = root.querySelector("[data-private-content]");
  const decoder = new TextDecoder("utf-8", {fatal: true});
  const fromBase64 = value => Uint8Array.from(atob(value), char => char.charCodeAt(0));
  let notes = new Map();
  let assetUrls = new Map();
  let generation = 0;

  function reset() {
    generation += 1;
    for (const url of assetUrls.values()) URL.revokeObjectURL(url);
    assetUrls.clear();
    notes.clear();
    tree.replaceChildren();
    content.replaceChildren();
    title.textContent = "选择一篇笔记";
    password.value = "";
    gate.hidden = false;
    workspace.hidden = true;
    lockButton.hidden = true;
    status.textContent = "";
    status.classList.remove("is-error");
  }

  function safeFragment(html) {
    const template = document.createElement("template");
    template.innerHTML = html;
    const allowed = new Set("A P DIV SPAN BR HR H1 H2 H3 H4 H5 H6 UL OL LI DL DT DD BLOCKQUOTE PRE CODE EM STRONG B I S DEL U SUB SUP MARK SMALL TABLE THEAD TBODY TFOOT TR TH TD CAPTION IMG DETAILS SUMMARY KBD SAMP VAR".split(" "));
    for (const element of [...template.content.querySelectorAll("*")]) {
      if (!allowed.has(element.tagName)) {
        element.remove();
        continue;
      }
      for (const attribute of [...element.attributes]) {
        if (!["href", "src", "alt", "title", "class", "colspan", "rowspan", "id"].includes(attribute.name)) element.removeAttribute(attribute.name);
      }
      if (element.hasAttribute("src")) {
        const value = element.getAttribute("src");
        const asset = value.startsWith("private-asset:") ? assetUrls.get(value.slice(14)) : null;
        element.removeAttribute("src");
        if (element.tagName === "IMG" && asset) element.src = asset;
      }
      if (element.hasAttribute("href")) {
        const value = element.getAttribute("href");
        element.removeAttribute("href");
        if (element.tagName !== "A") continue;
        if (value.startsWith("private-note:") && notes.has(value.slice(13))) {
          const id = value.slice(13);
          element.href = "#";
          element.addEventListener("click", event => { event.preventDefault(); showNote(id); });
        } else if (value.startsWith("private-asset:") && assetUrls.has(value.slice(14))) {
          element.href = assetUrls.get(value.slice(14));
          element.download = "attachment";
        } else if (/^(https?:|mailto:|#)/i.test(value)) {
          element.href = value;
          element.rel = "noreferrer noopener";
          if (!value.startsWith("#")) element.target = "_blank";
        }
      }
    }
    const fragment = document.createDocumentFragment();
    fragment.append(...template.content.childNodes);
    return fragment;
  }

  function showNote(id) {
    const note = notes.get(id);
    if (!note) return;
    title.textContent = note.title;
    content.replaceChildren(safeFragment(note.html));
    if (typeof window.renderMathInElement === "function") {
      window.renderMathInElement(content, {
        delimiters: [
          {left: "$$", right: "$$", display: true},
          {left: "\\[", right: "\\]", display: true},
          {left: "\\(", right: "\\)", display: false},
          {left: "$", right: "$", display: false},
        ],
        throwOnError: false,
        trust: false,
      });
    }
    for (const button of tree.querySelectorAll("[data-note-id]")) {
      if (button.dataset.noteId === id) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
    title.focus({preventScroll: true});
    if (matchMedia("(max-width: 767px)").matches) title.scrollIntoView({block: "start"});
  }

  function populate(payload) {
    if (!Array.isArray(payload.folders) || !payload.assets || typeof payload.assets !== "object") throw new Error("Invalid content");
    for (const [id, asset] of Object.entries(payload.assets)) {
      if (!/^[a-f0-9]+$/.test(id) || typeof asset.data !== "string") throw new Error("Invalid asset");
      const mime = /^(image\/(png|jpeg|gif|webp|avif|bmp)|application\/pdf)$/.test(asset.mime) ? asset.mime : "application/octet-stream";
      assetUrls.set(id, URL.createObjectURL(new Blob([fromBase64(asset.data)], {type: mime})));
    }
    for (const folder of payload.folders) {
      if (typeof folder.name !== "string" || !Array.isArray(folder.notes)) throw new Error("Invalid folder");
      for (const note of folder.notes) {
        if (typeof note.id !== "string" || typeof note.title !== "string" || typeof note.html !== "string" || notes.has(note.id)) throw new Error("Invalid note");
        notes.set(note.id, note);
      }
    }
    const folderLists = new Map();
    for (const folder of payload.folders) {
      const segments = folder.name.split("/").filter(Boolean);
      if (!segments.length || segments.some(segment => segment === "." || segment === "..")) throw new Error("Invalid folder path");
      let list = tree;
      for (let index = 0; index < segments.length; index += 1) {
        const folderPath = segments.slice(0, index + 1).join("/");
        if (!folderLists.has(folderPath)) {
          const details = document.createElement("details");
          details.className = "private-space-folder";
          const summary = document.createElement("summary");
          summary.textContent = segments[index];
          const children = document.createElement("div");
          children.className = "private-space-note-list";
          details.append(summary, children);
          list.append(details);
          folderLists.set(folderPath, children);
        }
        list = folderLists.get(folderPath);
      }
      for (const note of folder.notes) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "private-space-note-link";
        button.dataset.noteId = note.id;
        button.textContent = note.title;
        button.addEventListener("click", () => showNote(note.id));
        list.append(button);
      }
    }
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    if (!crypto.subtle) {
      status.textContent = "此浏览器不支持安全解密，请使用新版浏览器和 HTTPS 访问。";
      return;
    }
    const attempt = generation;
    submit.disabled = true;
    status.classList.remove("is-error");
    status.textContent = "正在解锁…";
    try {
      const bundleUrl = new URL(root.dataset.bundleUrl, location.href);
      if (bundleUrl.origin !== location.origin) throw new Error("Invalid bundle URL");
      const response = await fetch(bundleUrl, {cache: "no-store", credentials: "omit", redirect: "error"});
      if (!response.ok) throw new Error("Fetch failed");
      const bundle = await response.json();
      if (bundle.version !== 1 || bundle.kdf !== "PBKDF2-SHA256" || !Number.isInteger(bundle.iterations) || bundle.iterations < 100000 || bundle.iterations > 2000000) throw new Error("Invalid encryption metadata");
      const salt = fromBase64(bundle.salt);
      const iv = fromBase64(bundle.iv);
      if (salt.length < 16 || iv.length !== 12) throw new Error("Invalid encryption metadata");
      const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(password.value), "PBKDF2", false, ["deriveKey"]);
      password.value = "";
      const key = await crypto.subtle.deriveKey({name: "PBKDF2", salt, iterations: bundle.iterations, hash: "SHA-256"}, material, {name: "AES-GCM", length: 256}, false, ["decrypt"]);
      const plaintext = await crypto.subtle.decrypt({name: "AES-GCM", iv}, key, fromBase64(bundle.ciphertext));
      if (generation !== attempt) return;
      const payload = JSON.parse(decoder.decode(plaintext));
      populate(payload);
      gate.hidden = true;
      workspace.hidden = false;
      lockButton.hidden = false;
      status.textContent = "";
      tree.querySelector("summary")?.focus();
    } catch (_error) {
      reset();
      status.textContent = "无法解锁，请检查密码后重试。";
      status.classList.add("is-error");
      password.focus();
    } finally {
      password.value = "";
      submit.disabled = false;
    }
  });
  lockButton.addEventListener("click", () => { reset(); password.focus(); });
  window.addEventListener("pagehide", reset);
  window.addEventListener("pageshow", event => { if (event.persisted) reset(); });
  // Keep native form submission disabled until the local decrypt handler is
  // installed. The input has no name, so it can never become a query parameter.
  root.dataset.privateReady = "true";
  status.textContent = "";
  submit.disabled = false;
})();
