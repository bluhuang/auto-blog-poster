import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from modules import (
    cache_persister,
    content_processor,
    deepseek_client,
    deployer,
    git_ops,
    hugo_builder,
    site_validator,
)


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

    cache_file = config.get("processing", {}).get(
        "cache_file", ".hash_cache.json"
    )

    # ── Step 1: Pull source notes ──────────────────────────────────
    print()
    local_vault = config.get("processing", {}).get("local_vault_path", "")
    if local_vault and os.path.isdir(local_vault):
        notes_subdir = config.get("source", {}).get("notes_subdir", "")
        vault_notes = os.path.join(local_vault, notes_subdir)
        if os.path.isdir(vault_notes):
            print(f"[1/7] Using local vault: {vault_notes}")
            notes_root = Path(vault_notes)
            config["_source_repo_dir"] = local_vault
        else:
            print(f"WARNING: vault notes dir not found at {vault_notes}, falling back to git clone")
            notes_root = git_ops.pull_source_repo(config)
    else:
        print("[1/7] Pulling source notes repository ...")
        try:
            notes_root = git_ops.pull_source_repo(config)
        except Exception as e:
            print(f"FATAL: Failed to pull source repo: {e}")
            sys.exit(1)

    # ── Step 2: Restore cache from previous run ─────────────────────
    print()
    print("[2/7] Restoring processed cache ...")
    try:
        cache_persister.pull_cache(config)
    except Exception as e:
        print(f"FATAL: Failed to restore cache: {e}")
        sys.exit(1)

    # ── Step 3: Process notes (incremental) ─────────────────────────
    print()
    print("[3/7] Processing notes (incremental) ...")
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

    # ── Step 3b: Generate navigation tree ───────────────────────────
    print()
    print("[3b/7] Generating navigation tree ...")
    try:
        content_processor.generate_navigation_json()
    except Exception as e:
        print(f"WARNING: Navigation tree generation failed: {e}")

    # ── Step 4: Build Hugo site ────────────────────────────────────
    print()
    print("[4/7] Building Hugo site ...")
    try:
        hugo_builder.build_site(config)
    except Exception as e:
        print(f"FATAL: Hugo build failed: {e}")
        sys.exit(1)

    # ── Step 5: Validate rendered output ───────────────────────────
    print()
    print("[5/7] Validating rendered output ...")
    try:
        site_validator.validate_generated_site(config)
    except Exception as e:
        print(f"FATAL: Pre-deploy validation failed: {e}")
        sys.exit(1)

    # ── Step 6: Deploy to GitHub Pages ─────────────────────────────
    print()
    print("[6/7] Deploying to GitHub Pages ...")
    try:
        deployer.deploy(config)
    except Exception as e:
        print(f"FATAL: Deployment failed: {e}")
        sys.exit(1)

    # ── Step 7: Persist cache for next run ─────────────────────────
    print()
    print("[7/7] Saving processed cache ...")
    try:
        cache_persister.push_cache(config)
    except Exception as e:
        print(f"FATAL: Failed to save cache: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Pipeline completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
