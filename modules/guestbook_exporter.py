"""Export real GitHub Discussion comments for the homepage guestbook."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

_GRAPHQL_URL = "https://api.github.com/graphql"


def _normalise_path(value: str) -> str:
    value = "/" + value.strip().strip("/") + "/"
    return value.replace("//", "/")


def _score_discussion(discussion: dict[str, Any], target_path: str, target_url: str) -> int:
    title = str(discussion.get("title") or "").strip()
    body = str(discussion.get("bodyText") or "")
    score = 0
    if title == target_path:
        score += 100
    if title == target_url:
        score += 100
    if title.endswith(target_path):
        score += 50
    if target_url in title:
        score += 45
    if target_url in body:
        score += 35
    if target_path in body:
        score += 20
    if title.count("/") == target_path.count("/"):
        score += 8
    return score


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def export_home_guestbook(config: dict[str, Any]) -> None:
    """Fetch homepage discussion comments and write ``static/data/home-guestbook.json``.

    The export is intentionally non-fatal. A failed network request preserves the
    previous successful snapshot when one exists, so a transient GitHub API issue
    cannot block the whole blog deployment.
    """

    static_dir = Path(config.get("output", {}).get("static_dir", "static/"))
    output_path = static_dir / "data" / "home-guestbook.json"

    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    owner = config.get("output", {}).get("owner", "bluhuang")
    repo = config.get("output", {}).get("repo", "blogs-of-bluhuang")
    base_path = config.get("validation", {}).get("base_path", f"/{repo}")
    origin = config.get("validation", {}).get(
        "published_origin", f"https://{owner}.github.io"
    )
    target_path = _normalise_path(base_path)
    target_url = origin.rstrip("/") + target_path

    if not token:
        print("WARNING: Guestbook export skipped: GH_PAT/GITHUB_TOKEN is missing")
        if not output_path.exists():
            _write_json(
                output_path,
                {
                    "available": False,
                    "comments": [],
                    "discussionUrl": f"https://github.com/{owner}/{repo}/discussions",
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
        return

    query = """
    query HomeGuestbook($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        discussions(first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            number
            title
            bodyText
            url
            updatedAt
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
            json={"query": query, "variables": {"owner": owner, "repo": repo}},
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"])

        discussions = (
            data.get("data", {})
            .get("repository", {})
            .get("discussions", {})
            .get("nodes", [])
        )
        ranked = sorted(
            (
                (_score_discussion(item, target_path, target_url), item)
                for item in discussions
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        discussion = ranked[0][1] if ranked and ranked[0][0] > 0 else None

        if discussion is None:
            payload = {
                "available": True,
                "comments": [],
                "totalCount": 0,
                "discussionUrl": f"https://github.com/{owner}/{repo}/discussions",
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "message": "Homepage discussion has not been created yet.",
            }
        else:
            raw_comments = discussion.get("comments", {}).get("nodes", []) or []
            comments = []
            for comment in reversed(raw_comments):
                author = comment.get("author") or {}
                comments.append(
                    {
                        "id": comment.get("id"),
                        "bodyText": comment.get("bodyText") or "",
                        "createdAt": comment.get("createdAt"),
                        "updatedAt": comment.get("updatedAt"),
                        "url": comment.get("url"),
                        "reactionCount": (comment.get("reactions") or {}).get(
                            "totalCount", 0
                        ),
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
            f"{len(payload.get('comments', []))} recent / "
            f"{payload.get('totalCount', 0)} total"
        )
    except Exception as exc:
        print(f"WARNING: Guestbook export failed, keeping previous snapshot: {exc}")
        if not output_path.exists():
            _write_json(
                output_path,
                {
                    "available": False,
                    "comments": [],
                    "discussionUrl": f"https://github.com/{owner}/{repo}/discussions",
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
