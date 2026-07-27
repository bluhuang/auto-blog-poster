"""Fail-fast validation for generated Markdown and browser-rendered HTML."""

import functools
import http.server
import re
import socketserver
import threading
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from modules.structured_content import PLACEHOLDER_RE, validate_math_delimiters


BROKEN_ATTACHMENT_RE = re.compile(
    r"(?<!!)\[attachments/[^]\n]+\.(?:png|jpe?g|gif|webp|svg)\]", re.I
)


def validate_generated_site(config: dict) -> None:
    """Validate generated artifacts and live browser output before deploy."""
    validation_cfg = config.get("validation", {})
    content_dir = Path(config.get("output", {}).get("content_dir", "content"))
    public_dir = Path(validation_cfg.get("public_dir", "public"))
    errors: List[str] = []

    for markdown_path in content_dir.rglob("*.md"):
        content = markdown_path.read_text(encoding="utf-8")
        try:
            validate_math_delimiters(content)
        except ValueError as exc:
            errors.append(f"{markdown_path}: {exc}")
        if PLACEHOLDER_RE.search(content):
            errors.append(f"{markdown_path}: protected placeholder remains")
        if BROKEN_ATTACHMENT_RE.search(content):
            errors.append(f"{markdown_path}: damaged attachment image reference")

    for html_path in public_dir.rglob("*.html"):
        html = html_path.read_text(encoding="utf-8")
        if "$$" in _strip_code(_extract_main(html)):
            errors.append(f"{html_path}: raw $$ remains in rendered body")
        if PLACEHOLDER_RE.search(html):
            errors.append(f"{html_path}: protected placeholder remains")
        if BROKEN_ATTACHMENT_RE.search(html):
            errors.append(f"{html_path}: damaged attachment image reference")

    if errors:
        raise RuntimeError("Static validation failed:\n" + "\n".join(errors[:30]))

    _validate_in_browser(config)
    print("Pre-deploy validation passed.")


def _validate_in_browser(config: dict) -> None:
    validation_cfg = config.get("validation", {})
    host = validation_cfg.get("host", "127.0.0.1")
    port = int(validation_cfg.get("port", 1314))
    timeout_ms = int(validation_cfg.get("browser_timeout_ms", 30000))
    image_check_paths = validation_cfg.get("image_check_paths", [])
    published_origin = validation_cfg.get("published_origin", "").rstrip("/")
    public_dir = Path(validation_cfg.get("public_dir", "public"))
    base_url = f"http://{host}:{port}"
    base_path = "/" + validation_cfg.get("base_path", "").strip("/")
    if base_path == "/":
        base_path = ""
    site_base_url = f"{base_url}{base_path}"
    handler = functools.partial(
        _QuietStaticHandler,
        directory=str(public_dir.resolve()),
        mount_path=base_path,
    )
    server = _StaticServer((host, port), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            if published_origin:
                def serve_published_asset(route) -> None:
                    local_url = f"{base_url}{urlparse(route.request.url).path}"
                    response = route.fetch(url=local_url)
                    route.fulfill(response=response)
            urls = []
            for html_path in public_dir.rglob("*.html"):
                relative = html_path.relative_to(public_dir).as_posix()
                if relative == "index.html":
                    urls.append(f"{site_base_url}/")
                elif relative.endswith("/index.html"):
                    urls.append(f"{site_base_url}/{relative[:-10]}")
                else:
                    urls.append(f"{site_base_url}/{relative}")
            checked = 0
            requested_paths = validation_cfg.get("browser_test_paths", [])
            test_urls = [
                url for url in urls
                if not requested_paths
                or any(urlparse(url).path.endswith(path) for path in requested_paths)
            ]
            if not test_urls:
                raise RuntimeError("Browser validation has no matching test page")
            for url in test_urls:
                for viewport, color_scheme in (
                    ({"width": 1440, "height": 1000}, "light"),
                    ({"width": 1440, "height": 1000}, "dark"),
                    ({"width": 390, "height": 844}, "light"),
                    ({"width": 390, "height": 844}, "dark"),
                ):
                    context = browser.new_context(
                        viewport=viewport, color_scheme=color_scheme
                    )
                    if published_origin:
                        context.route(
                            f"{published_origin}/**", serve_published_asset
                        )
                    page = context.new_page()
                    console_errors: List[str] = []
                    css_responses: List[Tuple[str, int]] = []
                    third_party_404s: List[str] = []
                    page.on(
                        "console",
                        lambda message: console_errors.append(message.text)
                        if message.type == "error" else None,
                    )
                    page.on(
                        "response",
                        lambda response: (
                            css_responses.append((response.url, response.status))
                            if ".css" in response.url else None,
                            third_party_404s.append(response.url)
                            if response.status == 404 and "giscus.app/" in response.url else None,
                        ),
                    )
                    page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                    _assert_browser_page(page, url, timeout_ms)
                    if not any(status == 200 for _url, status in css_responses):
                        raise RuntimeError(f"{url}: KaTeX CSS request did not succeed")
                    relevant_console_errors = console_errors[
                        len(third_party_404s):
                    ] if all(
                        error.startswith("Failed to load resource")
                        for error in console_errors
                    ) else console_errors
                    if relevant_console_errors:
                        raise RuntimeError(f"{url}: browser console errors: {console_errors}")
                    context.close()
                    checked += 1
            browser.close()
        print(f"  Browser validation checked {checked} desktop/mobile light/dark page view(s)")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=10)


def _assert_browser_page(page, url: str, timeout_ms: int) -> None:
    """Assert one fully rendered browser page before deployment."""
    if page.locator("pre.mermaid").count():
        page.wait_for_function(
            """() => [...document.querySelectorAll('pre.mermaid')].every(node =>
              node.dataset.mermaidRendered === 'true' && node.querySelector('svg'))""",
            timeout=timeout_ms,
        )
    mermaid_errors = page.locator("pre.mermaid[data-mermaid-error='true']").count()
    if mermaid_errors:
        raise RuntimeError(f"{url}: {mermaid_errors} Mermaid diagram(s) failed")
    if page.locator("main h1").count() != 1:
        raise RuntimeError(f"{url}: expected exactly one H1")

    body_text = page.locator("main").inner_text()
    for token in ("$$", "![[", "@@PROTECTED"):
        if token in body_text:
            raise RuntimeError(f"{url}: rendered body retains {token}")

    mathml_ok = page.locator(".katex-mathml").evaluate_all(
        """nodes => nodes.every(node => {
          const style = getComputedStyle(node);
          const rect = node.getBoundingClientRect();
          return style.position === 'absolute' && rect.width <= 1 && rect.height <= 1;
        })"""
    )
    katex_html_ok = page.locator(".katex-html").evaluate_all(
        """nodes => nodes.every(node => {
          const style = getComputedStyle(node);
          return style.display !== 'none' && style.visibility !== 'hidden';
        })"""
    )
    if not mathml_ok or not katex_html_ok:
        raise RuntimeError(f"{url}: KaTeX MathML/HTML visibility is incorrect")

    images = page.locator(".content img")
    images.evaluate_all(
        """imgs => imgs.forEach(img => {
          img.loading = 'eager'; img.scrollIntoView({block: 'center'});
        })"""
    )
    page.wait_for_function(
        "() => [...document.querySelectorAll('.content img')].every(img => img.complete)",
        timeout=timeout_ms,
    )
    broken_images = images.evaluate_all(
        "imgs => imgs.filter(img => !img.naturalWidth || !img.alt.trim()).map(img => img.src)"
    )
    if broken_images:
        raise RuntimeError(f"{url}: broken or missing-alt content images: {broken_images}")

    missing_toc_targets = page.locator("#TableOfContents a[href^='#']").evaluate_all(
        """links => links.filter(link => !document.getElementById(
          decodeURIComponent(link.getAttribute('href').slice(1))
        )).map(link => link.getAttribute('href'))"""
    )
    if missing_toc_targets:
        raise RuntimeError(f"{url}: TOC target(s) missing: {missing_toc_targets}")
    if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"):
        raise RuntimeError(f"{url}: page has horizontal overflow")


class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the exact Hugo build artifact without noisy request logging."""

    def __init__(
        self, *args: object, mount_path: str = "", **kwargs: object
    ) -> None:
        self.mount_path = mount_path
        super().__init__(*args, **kwargs)

    def translate_path(self, path: str) -> str:
        if self.mount_path and (
            path == self.mount_path or path.startswith(f"{self.mount_path}/")
        ):
            path = path[len(self.mount_path):] or "/"
        return super().translate_path(path)

    def log_message(self, format: str, *args: object) -> None:
        return

    def end_headers(self) -> None:
        # Published-origin routes are fulfilled by this local server during
        # browser validation.  SRI stylesheet requests use crossorigin, so
        # mirror the CDN's permissive CORS response locally.
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


class _StaticServer(http.server.ThreadingHTTPServer):
    """Avoid reverse-DNS lookup while binding the local validation server."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = int(port)


def _extract_main(html: str) -> str:
    match = re.search(r"(?is)<main\b[^>]*>(.*?)</main>", html)
    return match.group(1) if match else html


def _strip_code(html: str) -> str:
    return re.sub(r"(?is)<(?:pre|code)\b[^>]*>.*?</(?:pre|code)>", "", html)
