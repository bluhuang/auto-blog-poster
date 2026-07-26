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
    const source = decodeSource(node);
    const { svg, bindFunctions } = await mermaid.render(
      `mermaid-${Date.now()}-${index}`,
      source
    );
    node.innerHTML = svg;
    node.dataset.mermaidRendered = "true";
    bindFunctions?.(node);
  }
}

let renderQueue = Promise.resolve();
const queueRender = () => {
  renderQueue = renderQueue.then(renderMermaid).catch((error) => {
    console.error("Mermaid rendering failed", error);
  });
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
