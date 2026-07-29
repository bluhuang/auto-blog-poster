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
all authenticated interactions. The in-page interaction layer is pinned to
Discussion #2 and provides GitHub login, posting, replies, reactions, Markdown
preview, and GitHub-supported attachments. The right card renders a real comment
snapshot from `static/data/home-guestbook.json`.

The deployment repository contains a `discussion_comment` workflow that refreshes
the snapshot when Discussion #2 changes. The deployer preserves `.github` so the
workflow survives later site deployments.

## Local Development

```bash
pip install -r requirements.txt
python main.py
```