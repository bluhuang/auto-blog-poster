"""Generate stable screenshots used by the repository README."""

from __future__ import annotations

import functools
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, sync_playwright

from modules.site_validator import _QuietStaticHandler, _StaticServer


_DEFAULT_ARTICLE_PATH = "/ai/0-paper/cnn-net/4-mobilenetv2---inverted-residuals-and-linear-bottlenecks/"


def capture_previews(config: dict) -> None:
    """Capture the homepage, blog library, and one article into ``public/readme``.

    The screenshots are produced from the exact Hugo build artifact that will be
    deployed. This keeps README previews current without requiring manual images.
    """
    validation_cfg = config.get("validation", {})
    preview_cfg = config.get("readme_preview", {})
    if preview_cfg.get("enabled", True) is False:
        print("README preview capture disabled.")
        return

    public_dir = Path(validation_cfg.get("public_dir", "public"))
    if not public_dir.is_dir():
        raise RuntimeError(f"README preview public directory not found: {public_dir}")

    host = preview_cfg.get("host", validation_cfg.get("host", "127.0.0.1"))
    port = int(preview_cfg.get("port", 1315))
    timeout_ms = int(preview_cfg.get("timeout_ms", validation_cfg.get("browser_timeout_ms", 30000)))
    viewport_width = int(preview_cfg.get("viewport_width", 1440))
    viewport_height = int(preview_cfg.get("viewport_height", 900))
    published_origin = validation_cfg.get("published_origin", "").rstrip("/")
    base_path = "/" + validation_cfg.get("base_path", "").strip("/")
    if base_path == "/":
        base_path = ""

    article_paths = validation_cfg.get("browser_test_paths", [])
    article_path = preview_cfg.get("article_path") or (article_paths[0] if article_paths else _DEFAULT_ARTICLE_PATH)
    pages = (
        ("homepage.png", "/", "[data-home-redesign], main"),
        ("blog-library.png", "/blogs/", ".library-shell, main"),
        ("article-reading.png", article_path, ".article-reading-layout, article, main"),
    )

    base_url = f"http://{host}:{port}"
    site_base_url = f"{base_url}{base_path}"
    output_dir = public_dir / "readme"
    output_dir.mkdir(parents=True, exist_ok=True)

    handler = functools.partial(_QuietStaticHandler, directory=str(public_dir.resolve()), mount_path=base_path)
    server = _StaticServer((host, port), handler)
    server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                color_scheme="light",
                device_scale_factor=1,
            )

            if published_origin:
                def serve_published_asset(route: Route) -> None:
                    local_url = f"{base_url}{urlparse(route.request.url).path}"
                    response = route.fetch(url=local_url)
                    route.fulfill(response=response)

                context.route(f"{published_origin}/**", serve_published_asset)

            page = context.new_page()
            for filename, path, selector in pages:
                url = f"{site_base_url}{_normalized_path(path)}"
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
                _prepare_page(page, timeout_ms)
                page.screenshot(path=str(output_dir / filename), full_page=False, animations="disabled")
                print(f"  captured {filename}: {path}")

            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=10)

    print(f"README previews saved to {output_dir}")


def _prepare_page(page: Page, timeout_ms: int) -> None:
    page.add_style_tag(
        content="""
        *, *::before, *::after {
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
          caret-color: transparent !important;
        }
        html { scroll-behavior: auto !important; }
        """
    )
    page.evaluate("document.fonts ? document.fonts.ready : Promise.resolve()")
    page.evaluate(
        """() => [...document.images].forEach(img => {
          img.loading = 'eager';
          img.decoding = 'sync';
        })"""
    )
    page.wait_for_function(
        "() => [...document.images].every(img => img.complete)",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")


def _normalized_path(path: str) -> str:
    normalized = "/" + str(path or "/").strip("/")
    return "/" if normalized == "/" else normalized + "/"
