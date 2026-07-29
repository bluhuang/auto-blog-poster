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

The homepage keeps its two-card layout while using the real Giscus client for
GitHub login, posting, replies, reactions, and Markdown preview. The integration
is pinned to Discussion #2. Image uploads open the native Discussion editor so
GitHub's real drag-and-drop and file picker remain available instead of exposing
an incomplete custom upload implementation.

The right card renders a real comment snapshot from
`static/data/home-guestbook.json`. The deployment repository refreshes that
snapshot on Discussion comment changes and every five minutes for reaction-count
updates. The deployer preserves `.github` so the sync workflow survives later
site deployments.

## Local Development

```bash
pip install -r requirements.txt
python main.py
```