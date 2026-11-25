"""Verify the real encrypted site without saving decrypted browser artifacts."""
import functools
import os
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright
from modules.site_validator import _QuietStaticHandler, _StaticServer


def validate_private_space(config):
    cfg = config.get('private_space', {})
    if not cfg.get('enabled', False):
        return
    validation = config.get('validation', {})
    host, port = validation.get('host', '127.0.0.1'), int(validation.get('port', 1314))
    base_path = '/' + validation.get('base_path', '').strip('/')
    handler = functools.partial(
        _QuietStaticHandler,
        directory=str(Path(validation.get('public_dir', 'public')).resolve()),
        mount_path=base_path,
    )
    server = _StaticServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://{host}:{port}'
    stage = 'starting'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for viewport in ({'width': 1440, 'height': 1000}, {'width': 390, 'height': 844}):
                stage = 'shared framework'
                context = browser.new_context(viewport=viewport)
                external = []
                context.on('request', lambda request: external.append(request.url)
                           if not request.url.startswith((origin + '/', 'blob:', 'data:')) else None)
                page = context.new_page()
                page.goto(origin + base_path + '/' + cfg.get('url', 'private-space/'), wait_until='networkidle')
                assert page.locator('header.site-header').is_visible()
                assert page.locator('footer').count() == 1
                assert page.locator('.library-shell .article-page-redesign .article-content-card .article-content').count() == 1
                tree = page.locator('[data-private-tree]')
                assert tree.inner_text() == ''
                assert not page.locator('[data-private-workspace]').is_visible()
                stage = 'wrong password'
                page.locator('input[type=password]').fill('invalid-private-space-test-password')
                page.locator('[data-private-submit]').click()
                page.locator('[data-private-status].is-error').wait_for()
                assert tree.inner_text() == ''
                stage = 'unlock'
                page.locator('input[type=password]').fill(os.environ[cfg.get('password_env', 'PRIVATE_SPACE_PASSWORD')])
                page.locator('[data-private-submit]').click()
                page.locator('[data-private-workspace]').wait_for(state='visible')
                stage = 'article rendering'
                assert tree.locator('[data-note-id]').count() > 0
                tree.locator('summary').first.click()
                tree.locator('[data-note-id]').first.click()
                assert page.locator('[data-private-content]').inner_text().strip()
                assert page.locator('[data-private-content] .katex-error').count() == 0
                assert page.locator('.article-title[data-private-note-title]').inner_text().strip()
                stage = 'same-origin resources'
                assert not external
                stage = 'storage and lock'
                assert page.evaluate('Object.keys(localStorage).every(key => key === "theme") && sessionStorage.length === 0')
                page.locator('[data-private-lock]').click()
                assert tree.inner_text() == ''
                assert page.locator('[data-private-content]').inner_text() == ''
                assert page.locator('#article-toc-nav').inner_text() == ''
                assert page.locator('#article-toc-drawer-nav').inner_text() == ''
                context.close()
            browser.close()
    except Exception:
        # Playwright call logs may contain fill() arguments. Never propagate
        # them to public Actions logs when the argument is a password.
        raise RuntimeError(f'Private Space browser verification failed ({stage})') from None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
    print('Private Space browser checks passed (desktop and mobile).')
