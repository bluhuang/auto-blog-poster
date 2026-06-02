import os
import shutil
import subprocess

from pathlib import Path


def deploy(config: dict) -> None:
    """Deploy the Hugo ``public/`` output to the target GitHub Pages repository.

    Steps:

    1. Clone / pull the target repo into ``.temp/deploy_repo``.
    2. Clear all files except ``.git``.
    3. Copy ``public/`` contents into the deploy repo.
    4. Commit and push to the target branch.

    Authentication uses the ``GH_PAT`` environment variable.

    Args:
        config: Full application configuration dict.

    Raises:
        ValueError: If ``GH_PAT`` is not set or ``public/`` is missing.
        RuntimeError: If any Git command fails.
    """
    deploy_cfg = config.get("deployment", {})
    target_repo = deploy_cfg.get("target_repo", "")
    target_branch = deploy_cfg.get("target_branch", "gh-pages")
    commit_message = deploy_cfg.get("commit_message", "Auto deploy [skip ci]")

    if not target_repo:
        raise ValueError("Missing config: deployment.target_repo")

    token = os.getenv("GH_PAT")
    if not token:
        raise ValueError("Missing GH_PAT environment variable")

    public_dir = os.path.join(os.getcwd(), "public")
    if not os.path.isdir(public_dir):
        raise ValueError(f"public/ directory not found: {public_dir}")

    deploy_path = os.path.join(".temp", "deploy_repo")
    clone_url = f"https://{token}@github.com/{target_repo}.git"

    # 1. Clone or pull
    if not os.path.isdir(deploy_path):
        print(f"Cloning {target_repo} to {deploy_path} ...")
        subprocess.run(
            ["git", "clone", clone_url, deploy_path],
            check=True,
            timeout=120,
        )
    else:
        print(f"Pulling latest for {target_repo} ...")
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=deploy_path,
            check=True,
            timeout=60,
        )

    # Switch to target branch (create if absent)
    _ensure_branch(deploy_path, target_branch)

    # 2. Clear deploy repo (keep .git)
    _clear_repo(deploy_path)

    # 3. Copy public/ contents
    print(f"Copying {public_dir} -> {deploy_path} ...")
    _copytree(public_dir, deploy_path)

    # 4. Commit and push
    os.chdir(deploy_path)

    # Ensure git identity is set (required in CI environments)
    subprocess.run(
        ["git", "config", "user.name", "Auto Blog Poster"],
        check=False,
        timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.email", "auto-blog-poster@users.noreply.github.com"],
        check=False,
        timeout=10,
    )

    subprocess.run(
        ["git", "add", "."],
        check=True,
        timeout=30,
    )

    # Check if there are staged changes
    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        timeout=10,
    )
    if diff_result.returncode == 0:
        print("No changes to deploy. Skipping commit.")
    else:
        print(f"Committing: {commit_message}")
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True,
            timeout=30,
        )
        print(f"Pushing to {target_branch} ...")
        subprocess.run(
            ["git", "push", "origin", target_branch],
            check=True,
            timeout=120,
        )
        print("Deploy finished.")

    os.chdir(os.path.dirname(deploy_path))  # back to project root via .temp/..
    os.chdir("..")  # back to project root


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_branch(repo_path: str, branch: str) -> None:
    """Checkout *branch*, creating it orphaned if it does not exist."""
    # Check if branch exists locally or remotely
    result = subprocess.run(
        ["git", "branch", "-a"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    branches = result.stdout

    # Match branch name in local or remote listing
    if branch in branches or f"remotes/origin/{branch}" in branches:
        subprocess.run(
            ["git", "checkout", branch],
            cwd=repo_path,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=repo_path,
            check=True,
            timeout=60,
        )
        print(f"Checked out existing branch: {branch}")
    else:
        # Create a fresh orphan branch and push it
        print(f"Creating orphan branch: {branch}")
        subprocess.run(
            ["git", "checkout", "--orphan", branch],
            cwd=repo_path,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "rm", "-rf", "."],
            cwd=repo_path,
            check=False,
            timeout=30,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", f"Init {branch}"],
            cwd=repo_path,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo_path,
            check=True,
            timeout=120,
        )
        print(f"Created and pushed orphan branch: {branch}")


def _clear_repo(repo_path: str) -> None:
    """Remove all files and folders from *repo_path* except ``.git``."""
    for entry in os.listdir(repo_path):
        if entry == ".git":
            continue
        full = os.path.join(repo_path, entry)
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
    print("Cleared deploy repo (kept .git).")


def _copytree(src: str, dst: str) -> None:
    """Recursively copy all content from *src* into *dst*, handling nested
    directories properly."""
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
            shutil.copy2(s, d)
