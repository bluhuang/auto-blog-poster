"""Export the real homepage GitHub Discussion comments."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

_GRAPHQL_URL = "https://api.github.com/graphql"
_DEFAULT_DISCUSSION_NUMBER = 2


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _fallback_payload(owner: str, repo: str, discussion_number: int) -> dict[str, Any]:
    return {
        "available": False,
        "comments": [],
        "totalCount": 0,
        "discussionNumber": discussion_number,
        "discussionUrl": f"https://github.com/{owner}/{repo}/discussions/{discussion_number}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def export_home_guestbook(config: dict[str, Any]) -> None:
    """Write ``static/data/home-guestbook.json`` from one configured Discussion.

    The export is non-fatal. A failed request keeps the previous successful snapshot,
    so a temporary GitHub API failure cannot block the blog deployment.
    """

    static_dir = Path(config.get("output", {}).get("static_dir", "static/"))
    output_path = static_dir / "data" / "home-guestbook.json"
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    owner = str(config.get("output", {}).get("owner", "bluhuang"))
    repo = str(config.get("output", {}).get("repo", "blogs-of-bluhuang"))
    discussion_number = int(os.getenv("HOME_GUESTBOOK_DISCUSSION_NUMBER", _DEFAULT_DISCUSSION_NUMBER))

    if not token:
        print("WARNING: Guestbook export skipped: GH_PAT/GITHUB_TOKEN is missing")
        if not output_path.exists():
            _write_json(output_path, _fallback_payload(owner, repo, discussion_number))
        return

    query = """
    query HomeGuestbook($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        discussion(number: $number) {
          number
          title
          url
          comments(last: 30) {
            totalCount
            nodes {
              id
              bodyText
              createdAt
              updatedAt
              url
              author {
                login
                avatarUrl
                url
              }
              reactions {
                totalCount
              }
            }
          }
        }
      }
    }
    """

    try:
        response = requests.post(
            _GRAPHQL_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "query": query,
                "variables": {"owner": owner, "repo": repo, "number": discussion_number},
            },
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"])

        discussion = data.get("data", {}).get("repository", {}).get("discussion")
        if not discussion:
            raise RuntimeError(f"Discussion #{discussion_number} was not found")

        raw_comments = discussion.get("comments", {}).get("nodes", []) or []
        comments: list[dict[str, Any]] = []
        for comment in reversed(raw_comments):
            author = comment.get("author") or {}
            comments.append(
                {
                    "id": comment.get("id"),
                    "bodyText": comment.get("bodyText") or "",
                    "createdAt": comment.get("createdAt"),
                    "updatedAt": comment.get("updatedAt"),
                    "url": comment.get("url"),
                    "reactionCount": (comment.get("reactions") or {}).get("totalCount", 0),
                    "author": {
                        "login": author.get("login") or "GitHub User",
                        "avatarUrl": author.get("avatarUrl"),
                        "url": author.get("url"),
                    },
                }
            )

        payload = {
            "available": True,
            "discussionNumber": discussion.get("number"),
            "discussionTitle": discussion.get("title"),
            "discussionUrl": discussion.get("url"),
            "totalCount": discussion.get("comments", {}).get("totalCount", 0),
            "comments": comments[:12],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(output_path, payload)
        print(
            "Homepage guestbook snapshot: "
            f"discussion #{discussion_number}, "
            f"{len(payload['comments'])} recent / {payload['totalCount']} total"
        )
    except Exception as exc:
        print(f"WARNING: Guestbook export failed, keeping previous snapshot: {exc}")
        if not output_path.exists():
            _write_json(output_path, _fallback_payload(owner, repo, discussion_number))