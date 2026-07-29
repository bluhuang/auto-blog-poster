# Auto Blog Poster

Automatically fetch Obsidian notes from a private repo, process them via
DeepSeek API, build a Hugo site, and deploy to GitHub Pages.

## Environment Variables

| Variable | Description |
|---|---|
| `DEEPSEEK_API_KEY` | API key for DeepSeek |
| `GH_PAT` | Personal access token for Git operations and homepage Discussions export |
| `HOME_GUESTBOOK_DISCUSSION_NUMBER` | Optional homepage Discussion number; defaults to `2` |

Copy `.env.example` to `.env` and fill in the values.

## Homepage Guestbook

The homepage keeps its two-card layout. The left card embeds the real Giscus
composer directly and uses custom Apple-style light and dark themes. The custom
themes keep login, writing, Markdown preview, and publishing in the real GitHub
Discussion flow while hiding the duplicate comment timeline from the left card.
Image uploads continue through the native Discussion editor.

The right card renders a real comment snapshot from
`static/data/home-guestbook.json`. Its comment list scrolls independently while
the existing header and action button stay fixed. The deployment repository
refreshes the snapshot whenever Discussion #2 comments change and on a schedule
for reaction counts. The homepage also bypasses caches and polls the snapshot
every 15 seconds, with accelerated refreshes after Giscus metadata changes.

The deployer preserves `.github` so the synchronization workflow survives later
site deployments.

## Local Development

```bash
pip install -r requirements.txt
python main.py
```