# Auto Blog Poster

Automatically fetch Obsidian notes from a private repo, process them via
DeepSeek API, build a Hugo site, and deploy to GitHub Pages.

## Environment Variables

| Variable           | Description                        |
|--------------------|------------------------------------|
| `DEEPSEEK_API_KEY` | API key for DeepSeek               |
| `GH_PAT`           | Personal access token for Git ops and homepage Discussions export |

Copy `.env.example` to `.env` and fill in the values.

## Homepage Guestbook

During each build, the pipeline reads the homepage GitHub Discussion with
`GH_PAT` and writes a real-comment snapshot to
`static/data/home-guestbook.json`. The homepage renders only that snapshot;
it does not create demonstration users or messages. The custom editor stores
the draft locally, copies it on publish, and opens the matching GitHub
Discussion for authorization and posting.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python main.py
```
