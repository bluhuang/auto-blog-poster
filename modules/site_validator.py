"""Fail-fast validation for generated Markdown and browser-rendered HTML."""

import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import List

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
    executable = config.get("hugo", {}).get("executable", "hugo")
    host = validation_cfg.get("host", "127.0.0.1")
    port = int(validation_cfg.get("port", 1314))
    timeout_ms = int(validation_cfg.get("browser_timeout_ms", 30000))
    public_dir = Path(validation_cfg.get("public_dir", "public"))
    base_url = f"http://{host}:{port}"
    process = subprocess.Popen(
        [
            executable, "server", "--bind", host, "--port", str(port),
            "--baseURL", f"{base_url}/", "--appendPort=false", "--renderToMemory",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_server(process, base_url, timeout_ms)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            urls = []
            for html_path in public_dir.rglob("*.html"):
                relative = html_path.relative_to(public_dir).as_posix()
                if relative == "index.html":
                    urls.append(f"{base_url}/")
                elif relative.endswith("/index.html"):
                    urls.append(f"{base_url}/{relative[:-10]}")
                else:
                    urls.append(f"{base_url}/{relative}")
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
                broken_images = page.locator(
                    ".content img[src*='/images/']"
                ).evaluate_all(
                    "imgs => imgs.filter(img => !img.complete || img.naturalWidth === 0).map(img => img.src)"
                )
                if broken_images:
                    raise RuntimeError(f"{url}: broken content images: {broken_images}")
                checked += 1
            browser.close()
        print(f"  Browser validation checked {checked} internal page(s)")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _wait_for_server(process: subprocess.Popen, base_url: str, timeout_ms: int) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Hugo validation server exited early:\n{output[-2000:]}")
        try:
            with urllib.request.urlopen(base_url, timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for validation server at {base_url}")


def _extract_main(html: str) -> str:
    match = re.search(r"(?is)<main\b[^>]*>(.*?)</main>", html)
    return match.group(1) if match else html


def _strip_code(html: str) -> str:
    return re.sub(r"(?is)<(?:pre|code)\b[^>]*>.*?</(?:pre|code)>", "", html)
