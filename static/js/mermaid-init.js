const decodeSource = (node) => {
  const bytes = Uint8Array.from(atob(node.dataset.mermaidSource), (char) =>
    char.charCodeAt(0)
  );
  return new TextDecoder().decode(bytes);
};

const currentTheme = () =>
  document.documentElement.classList.contains("dark") ? "dark" : "default";

let mermaidModule;

async function renderMermaid() {
  const nodes = [...document.querySelectorAll(".mermaid")];
  if (!nodes.length) return;

  try {
    mermaidModule ??= await import(
      "https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.esm.min.mjs"
    );
    const mermaid = mermaidModule.default;
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: currentTheme(),
    });

    for (const [index, node] of nodes.entries()) {
      try {
        const source = decodeSource(node);
        const { svg, bindFunctions } = await mermaid.render(
          `mermaid-${Date.now()}-${index}`,
          source
        );
        node.innerHTML = svg;
        node.dataset.mermaidRendered = "true";
        delete node.dataset.mermaidError;
        bindFunctions?.(node);
      } catch (_error) {
        node.innerHTML = '<div class="mermaid-error" role="alert">流程图渲染失败。</div>';
        node.dataset.mermaidRendered = "error";
        node.dataset.mermaidError = "true";
      }
    }
  } catch (_error) {
    for (const node of nodes) {
      node.innerHTML = '<div class="mermaid-error" role="alert">流程图加载失败。</div>';
      node.dataset.mermaidRendered = "error";
      node.dataset.mermaidError = "true";
    }
  }
}

let renderQueue = Promise.resolve();
const queueRender = () => {
  renderQueue = renderQueue.then(renderMermaid);
};

document.addEventListener("DOMContentLoaded", queueRender);

new MutationObserver((mutations) => {
  if (
    mutations.some(
      (mutation) =>
        mutation.type === "attributes" &&
        mutation.attributeName === "class"
    )
  ) {
    for (const node of document.querySelectorAll(".mermaid")) {
      node.textContent = decodeSource(node);
      delete node.dataset.mermaidRendered;
    }
    queueRender();
  }
}).observe(document.documentElement, { attributes: true });
