# Auto Blog Poster

Automatically fetch Obsidian notes from a private repo, process them via
DeepSeek API, build a Hugo site, and deploy to GitHub Pages.

## Environment Variables

| Variable           | Description                        |
|--------------------|------------------------------------|
| `DEEPSEEK_API_KEY` | API key for DeepSeek               |
| `GH_PAT`           | Personal access token for Git ops  |

Copy `.env.example` to `.env` and fill in the values.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python main.py
```
