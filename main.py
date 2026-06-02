import sys
import yaml
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    print("=== Auto Blog Poster ===")
    config = load_config()
    print(f"Config loaded: {config['source']['repo']} -> {config['output']['repo']}")

    print("[1/5] Pulling Obsidian notes from source repo ...")
    from modules.git_ops import pull_source_repo
    source_path = pull_source_repo(config)
    print(f"  Source notes at: {source_path}")

    print("[2/5] Parsing Obsidian markdown ...")
    from modules.obsidian_parser import parse_notes
    notes = parse_notes(source_path, config)
    print(f"  Parsed {len(notes)} notes")

    print("[3/5] Processing content with DeepSeek ...")
    from modules.content_processor import filter_new_notes, save_cache
    from modules.deepseek_client import call_deepseek
    notes = filter_new_notes(notes, config)
    for note in notes:
        note["content"] = call_deepseek(note["content"], config)
    save_cache(notes, config)
    print(f"  Processed {len(notes)} notes")

    print("[4/5] Building Hugo site ...")
    from modules.hugo_builder import build_site
    build_site(config)
    print("  Hugo build complete")

    print("[5/5] Deploying to output repo ...")
    from modules.deployer import deploy
    deploy(config)
    print("  Deployment complete")

    print("=== Done ===")


if __name__ == "__main__":
    main()
