# Private Space

`config.yaml` is the canonical configuration. `private_space.source_dirs` lists
directories relative to the Vault's `2 Notes` folder. These notes never enter
the public Markdown pipeline, AI API, public navigation, search, RSS, sitemap,
homepage, or plaintext processed cache. The library shows only a generic link.

Set the Actions secret named by `private_space.password_env` (by default
`PRIVATE_SPACE_PASSWORD`). Never commit the password. A missing password or
unresolved private reference stops deployment, rather than falling back to
public content. Private Markdown uses the same Hugo markup configuration and
render hooks as public articles. Its temporary source, rendered fragments and
Hugo caches stay in an isolated owner-only temporary directory, which is
removed on success or failure. Only encrypted content is published, as a single
AES-256-GCM authenticated ciphertext with PBKDF2-SHA256 key derivation.

Private Markdown wrapper notes can contain `![[Vault-relative/path/to/note]]`.
Obsidian embeds the original; the build resolves it recursively, using the
original note's folder for attachments. Originals remain the only editing
source. Every build rereads these references, so edits become visible after
the original is committed, pushed, and successfully deployed. Reference cycles,
ambiguous missing targets, and references outside the Vault are rejected.

The unlock page reuses the blog's shared layout, header, stylesheet and article
components, while omitting telemetry, third-party scripts and comments. It loads
only same-origin reading scripts. Passwords, keys,
decrypted text, and attachment blobs are not written to browser storage; locking
or leaving the page clears the reader. Unchanged public notes retain their
normal incremental cache. Private notes are not sent to DeepSeek.

Test with `python -m unittest discover -s tests -p 'test_*.py'` and the browser
fixture `node scripts/check_private_space_ui.cjs` (requires Playwright on the
Node module path). `npm ci` and `bash scripts/regenerate-theme.sh` prepare the
local math renderer before Hugo builds.

Previously public copies are not made private merely by adding encryption.
Clean old generated Git history, Actions logs and artifacts separately, and
keep any recovery backup outside public repositories. External forks, saved
copies, search-engine caches and GitHub's retained objects require separate
coordination; rewriting branch history cannot guarantee their deletion.
