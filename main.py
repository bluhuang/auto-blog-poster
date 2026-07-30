import argparse
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
    guestbook_exporter,
    hugo_builder,
    rename_migrator,
    site_validator,
)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load and return the YAML configuration file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and publish the blog")
    parser.add_argument(
        "--skip-deepseek",
        "--deepseek-cache-only",
        dest="deepseek_cache_only",
        action="store_true",
        help="Use only an existing DeepSeek response cache; never call the API.",
    )
    parser.add_argument(
        "--no-deploy",
        action="store_true",
        help="Process, build, and validate locally without deploying or updating remote cache.",
    )
    parser.add_argument(
        "--only-path",
        action="append",
        default=[],
        help="Process only a source-note path (repeatable; useful for local validation).",
    )
    return parser.parse_args()


def main() -> None:
    print("=" * 60)
    print("  Auto Blog Poster")
    print("=" * 60)

    # Load environment variables
    load_dotenv(override=False)

    args = _parse_args()
    config = load_config()
    if args.deepseek_cache_only:
        config["_deepseek_cache_only"] = True
        print("DeepSeek mode: cache-only (API calls forbidden)")
    if args.only_path:
        config["_only_paths"] = args.only_path
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

    # Preserve generated output and LLM cache for source notes that only moved.
    print()
    print("[2b/7] Detecting cache-preserving note moves ...")
    try:
        rename_migrator.migrate_cache_preserving_renames(
            source_root=str(notes_root),
            config=config,
            hash_cache_path=cache_file,
        )
    except Exception as e:
        print(f"FATAL: Failed to migrate renamed-note cache: {e}")
        sys.exit(1)

    # ── Step 3: Process notes (incremental) ─────────────────────────
    print()
    print("[3/7] Processing notes (incremental) ...")
    try:
        deepseek_calls = 0

        def counted_deepseek_call(content: str, call_config: dict) -> str:
            nonlocal deepseek_calls
            deepseek_calls += 1
            if call_config.get("_deepseek_cache_only", False):
                raise AssertionError("DeepSeek API call attempted in cache-only mode")
            return deepseek_client.call_deepseek(content, call_config)

        content_processor.process_all_notes(
            source_root=str(notes_root),
            config=config,
            deepseek_client_func=counted_deepseek_call,
            hash_cache_path=cache_file,
        )
        print(f"DeepSeek API calls: {deepseek_calls}")
        if args.deepseek_cache_only and deepseek_calls != 0:
            raise AssertionError("DeepSeek API calls must be 0 in cache-only mode")
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

    # ── Step 3c: Export real homepage guestbook data ───────────────
    print()
    print("[3c/7] Exporting homepage guestbook ...")
    try:
        guestbook_exporter.export_home_guestbook(config)
    except Exception as e:
        print(f"WARNING: Homepage guestbook export failed: {e}")

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
    if args.no_deploy:
        print()
        print("[6/7] Deployment skipped (--no-deploy)")
    else:
        print()
        print("[6/7] Deploying to GitHub Pages ...")
        try:
            deployer.deploy(config)
        except Exception as e:
            print(f"FATAL: Deployment failed: {e}")
            sys.exit(1)

    # ── Step 7: Persist cache for next run ─────────────────────────
    if args.no_deploy:
        print()
        print("[7/7] Remote cache update skipped (--no-deploy)")
    else:
        print()
        print("[7/7] Saving processed cache ...")
        try:
            cache_persister.push_cache(config)
        except Exception as e:
            print(f"FATAL: Failed to save processed cache: {e}")
            sys.exit(1)

    print()
    print("=" * 60)
    print("  Pipeline completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
