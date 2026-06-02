import os
import sys

import yaml
from dotenv import load_dotenv

from modules import content_processor, deepseek_client, deployer, git_ops, hugo_builder


def load_config(config_path: str = "config.yaml") -> dict:
    """Load and return the YAML configuration file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    print("=" * 60)
    print("  Auto Blog Poster")
    print("=" * 60)

    # Load environment variables
    load_dotenv(override=False)

    config = load_config()
    source_cfg = config.get("source", {})
    output_cfg = config.get("output", {})
    print(f"Source repo: {source_cfg.get('owner')}/{source_cfg.get('repo')}")
    print(f"Output repo: {output_cfg.get('owner')}/{output_cfg.get('repo')}")

    # Cache path
    cache_file = config.get("processing", {}).get(
        "cache_file", ".hash_cache.json"
    )

    # ── Step 1: Pull source notes ──────────────────────────────────
    print()
    print("[1/4] Pulling source notes repository ...")
    try:
        notes_root = git_ops.pull_source_repo(config)
    except Exception as e:
        print(f"FATAL: Failed to pull source repo: {e}")
        sys.exit(1)

    # ── Step 2: Process notes (incremental) ────────────────────────
    print()
    print("[2/4] Processing notes (incremental) ...")
    try:
        content_processor.process_all_notes(
            source_root=str(notes_root),
            config=config,
            deepseek_client_func=deepseek_client.call_deepseek,
            hash_cache_path=cache_file,
        )
    except Exception as e:
        print(f"FATAL: Content processing failed: {e}")
        sys.exit(1)

    # ── Step 3: Build Hugo site ────────────────────────────────────
    print()
    print("[3/4] Building Hugo site ...")
    try:
        hugo_builder.build_site(config)
    except Exception as e:
        print(f"FATAL: Hugo build failed: {e}")
        sys.exit(1)

    # ── Step 4: Deploy to GitHub Pages ─────────────────────────────
    print()
    print("[4/4] Deploying to GitHub Pages ...")
    try:
        deployer.deploy(config)
    except Exception as e:
        print(f"FATAL: Deployment failed: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Pipeline completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
