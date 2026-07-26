"""Fail-fast validation for generated Markdown and browser-rendered HTML."""

import functools
import http.server
import re
import socketserver
import threading
from pathlib import Path
from typing import List
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
            page = browser.new_page()
            if published_origin:
                def serve_published_asset(route) -> None:
                    local_url = f"{base_url}{urlparse(route.request.url).path}"
                    response = route.fetch(url=local_url)
                    route.fulfill(response=response)

                page.route(
                    f"{published_origin}/**",
                    serve_published_asset,
                )
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
            for url in urls:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                if page.locator("pre.mermaid").count():
                    page.wait_for_function(
                        """() => [...document.querySelectorAll('pre.mermaid')]
                        .every(node => node.dataset.mermaidRendered === 'true' &&
                          node.querySelector('svg'))""",
                        timeout=timeout_ms,
                    )
                page_path = urlparse(url).path
                if any(
                    page_path.endswith(check_path)
                    for check_path in image_check_paths
                ):
                    images = page.locator(".content img[src*='/images/']")
                    images.evaluate_all(
                        """imgs => imgs.forEach(img => {
                          img.loading = 'eager';
                          img.scrollIntoView({block: 'center'});
                        })"""
                    )
                    page.wait_for_function(
                        """() => [...document.querySelectorAll(
                          ".content img[src*='/images/']"
                        )].every(img => img.complete)""",
                        timeout=timeout_ms,
                    )
                    broken_images = images.evaluate_all(
                        "imgs => imgs.filter(img => !img.complete || img.naturalWidth === 0).map(img => img.src)"
                    )
                    if broken_images:
                        raise RuntimeError(
                            f"{url}: broken content images: {broken_images}"
                        )
                checked += 1
            browser.close()
        print(f"  Browser validation checked {checked} internal page(s)")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=10)


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
