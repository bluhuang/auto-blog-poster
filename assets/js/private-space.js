(() => {
  "use strict";
  const root = document.querySelector("[data-private-space]");
  if (!root) return;
  // Share the blog chrome and theme; decrypted data remains session-only.
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
  const folderLabel = root.querySelector("[data-private-folder-label]");
  const breadcrumb = root.querySelector("[data-private-breadcrumb]");
  const author = root.querySelector("[data-private-author]");
  const lockedNav = root.querySelector("[data-private-nav-locked]");
  const folderSheet = root.querySelector("[data-private-sheet]");
  const sheetBackdrop = root.querySelector("[data-private-sheet-backdrop]");
  const sheetClose = root.querySelector("[data-private-sheet-close]");
  const treePanel = root.querySelector("[data-private-tree-panel]");
  const desktopHost = root.querySelector("[data-private-desktop-tree-host]");
  const mobileHost = root.querySelector("[data-private-mobile-tree-host]");
  const menuButton = document.getElementById("mobileMenuButton");
  const mobileView = matchMedia("(max-width: 820px)");
  document.body.classList.add("library-page-active");

  function closeFolderSheet() {
    folderSheet?.classList.remove("is-open");
    folderSheet?.setAttribute("aria-hidden", "true");
    sheetBackdrop?.classList.remove("is-open");
    sheetBackdrop?.setAttribute("aria-hidden", "true");
    menuButton?.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
  }

  function moveFolderTree() {
    if (!treePanel || !desktopHost || !mobileHost) return;
    (mobileView.matches ? mobileHost : desktopHost).append(treePanel);
    if (!mobileView.matches) closeFolderSheet();
  }

  function openFolderSheet() {
    if (!folderSheet || !mobileView.matches) return;
    moveFolderTree();
    folderSheet.classList.add("is-open");
    folderSheet.setAttribute("aria-hidden", "false");
    sheetBackdrop?.classList.add("is-open");
    sheetBackdrop?.setAttribute("aria-hidden", "false");
    menuButton?.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }
  moveFolderTree();
  mobileView.addEventListener("change", moveFolderTree);
  menuButton?.addEventListener("click", () => folderSheet?.classList.contains("is-open") ? closeFolderSheet() : openFolderSheet());
  sheetClose?.addEventListener("click", closeFolderSheet);
  sheetBackdrop?.addEventListener("click", closeFolderSheet);
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeFolderSheet(); });

  function articleUpdated() {
    document.dispatchEvent(new CustomEvent("article:updated", {detail: {private: true}}));
  }
  const decoder = new TextDecoder("utf-8", {fatal: true});
  const fromBase64 = value => Uint8Array.from(atob(value), char => char.charCodeAt(0));
  let notes = new Map();
  let assetUrls = new Map();
  let assetTypes = new Map();
  let generation = 0;
  let imageLightbox = null;

  function reset() {
    generation += 1;
    imageLightbox?.destroy();
    imageLightbox = null;
    for (const url of assetUrls.values()) URL.revokeObjectURL(url);
    assetUrls.clear();
    assetTypes.clear();
    notes.clear();
    tree.replaceChildren();
    content.replaceChildren();
    title.textContent = "选择一篇笔记";
    if (folderLabel) folderLabel.textContent = "";
    if (breadcrumb) breadcrumb.textContent = "";
    if (author) author.textContent = "";
    if (lockedNav) lockedNav.hidden = false;
    root.querySelectorAll("[data-private-toc]").forEach(element => { element.hidden = true; });
    closeFolderSheet();
    articleUpdated();
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
    const allowed = new Set("a p div span br hr h1 h2 h3 h4 h5 h6 ul ol li dl dt dd blockquote pre code em strong b i s del u sub sup mark small table thead tbody tfoot tr th td caption img figure figcaption section abbr details summary kbd samp var input math semantics annotation mrow mi mn mo mtext mfrac msqrt mroot msup msub msubsup munder mover munderover mtable mtr mtd mspace mpadded mstyle mphantom menclose mmultiscripts mprescripts none svg path".split(" "));
    const attributes = new Set("href src alt title class colspan rowspan id style aria-hidden role tabindex data-language data-lang data-mermaid-source xmlns display encoding mathvariant stretchy fence separator lspace rspace accent accentunder columnalign columnspacing rowspacing rowalign columnlines rowlines linethickness scriptlevel displaystyle mathsize mathcolor mathbackground width height depth voffset notation viewbox preserveaspectratio d fill type checked disabled start".split(" "));
    const styleProperties = new Set("color background-color font-weight font-style font-size font-family text-decoration text-align text-indent white-space line-height height width min-width max-width min-height max-height vertical-align position top left right bottom margin margin-left margin-right margin-top margin-bottom padding padding-left padding-right padding-top padding-bottom border border-color border-width border-style border-top-width border-right-width border-bottom-width border-left-width border-top-style border-right-style border-bottom-style border-left-style display overflow tab-size -moz-tab-size -o-tab-size -webkit-text-size-adjust".split(" "));
    for (const element of [...template.content.querySelectorAll("*")]) {
      const tag = element.localName.toLowerCase();
      if (!allowed.has(tag)) { element.remove(); continue; }
      for (const attribute of [...element.attributes]) {
        if (!attributes.has(attribute.name.toLowerCase())) element.removeAttribute(attribute.name);
      }
      if (element.hasAttribute("fill") && !/^(none|currentcolor|#[0-9a-f]{3,8}|rgba?\([\d.,% ]+\))$/i.test(element.getAttribute("fill").trim())) element.removeAttribute("fill");
      if (element.hasAttribute("style")) {
        const declarations = [...element.style].map(name => [name, element.style.getPropertyValue(name)]);
        element.removeAttribute("style");
        for (const [name, value] of declarations) {
          if (!styleProperties.has(name) || /url\s*\(|expression\s*\(|@import|behavior|javascript:|data:|-moz-binding/i.test(value)) continue;
          if (name === "position" && !/^(relative|absolute|static)$/.test(value.trim())) continue;
          element.style.setProperty(name, value);
        }
      }
      if (tag === "input") {
        element.type = "checkbox";
        element.disabled = true;
        element.removeAttribute("name");
      }
      if (element.hasAttribute("src")) {
        const value = element.getAttribute("src");
        const asset = value.startsWith("private-asset:") ? assetUrls.get(value.slice(14)) : null;
        element.removeAttribute("src");
        if (tag === "img" && asset) element.src = asset;
      }
      if (element.hasAttribute("href")) {
        const value = element.getAttribute("href");
        element.removeAttribute("href");
        if (tag !== "a") continue;
        if (value.startsWith("private-note:") && notes.has(value.slice(13))) {
          const id = value.slice(13);
          element.href = "#";
          element.addEventListener("click", event => { event.preventDefault(); showNote(id); });
        } else if (value.startsWith("private-asset:") && assetUrls.has(value.slice(14))) {
          element.href = assetUrls.get(value.slice(14));
          if ((assetTypes.get(value.slice(14)) || "").startsWith("image/")) element.classList.add("glightbox");
          else element.download = "attachment";
        } else if (value.startsWith("#")) {
          element.href = value;
          element.addEventListener("click", event => {
            event.preventDefault();
            content.querySelectorAll("[id]").forEach(target => {
              if ("#" + target.id === value) target.scrollIntoView({block: "start", behavior: "smooth"});
            });
          });
        } else if (/^(https?:|mailto:)/i.test(value)) {
          element.href = value;
          element.rel = "noreferrer noopener";
          element.target = "_blank";
        }
      }
    }
    return template.content;
  }

  function showNote(id) {
    const note = notes.get(id);
    if (!note) return;
    title.textContent = note.title;
    if (author) author.textContent = note.author || "";
    imageLightbox?.destroy();
    imageLightbox = null;
    content.replaceChildren(safeFragment(note.html));
    if (folderLabel) folderLabel.textContent = note.folder;
    if (breadcrumb) breadcrumb.textContent = "› " + note.title;
    if (lockedNav) lockedNav.hidden = true;
    const hasHeadings = !!content.querySelector("h2, h3");
    root.querySelectorAll("[data-private-toc]").forEach(element => { element.hidden = !hasHeadings; });
    articleUpdated();
    if (typeof window.GLightbox === "function") imageLightbox = window.GLightbox({selector: '#article-content a.glightbox[href^="blob:"]'});
    closeFolderSheet();
    for (const button of tree.querySelectorAll("[data-note-id]")) {
      if (button.dataset.noteId === id) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
    title.focus({preventScroll: true});
    if (matchMedia("(max-width: 767px)").matches) title.scrollIntoView({block: "start"});
  }

  function populate(payload) {
    if (payload.renderer !== "hugo") throw new Error("Unsupported content renderer");
    if (!Array.isArray(payload.folders) || !payload.assets || typeof payload.assets !== "object") throw new Error("Invalid content");
    for (const [id, asset] of Object.entries(payload.assets)) {
      if (!/^[a-f0-9]+$/.test(id) || typeof asset.data !== "string") throw new Error("Invalid asset");
      const mime = /^(image\/(png|jpeg|gif|webp|avif|bmp)|application\/pdf)$/.test(asset.mime) ? asset.mime : "application/octet-stream";
      assetUrls.set(id, URL.createObjectURL(new Blob([fromBase64(asset.data)], {type: mime})));
      assetTypes.set(id, mime);
    }
    for (const folder of payload.folders) {
      if (typeof folder.name !== "string" || !Array.isArray(folder.notes)) throw new Error("Invalid folder");
      for (const note of folder.notes) {
        if (typeof note.id !== "string" || typeof note.title !== "string" || typeof note.html !== "string" || notes.has(note.id)) throw new Error("Invalid note");
        notes.set(note.id, {...note, folder: folder.name});
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
      if (lockedNav) lockedNav.hidden = true;
      openFolderSheet();
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
