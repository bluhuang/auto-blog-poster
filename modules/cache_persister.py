import os
import shutil
import subprocess

_ITEMS = ["content", "static/images", ".hash_cache.json"]
_CACHE_BRANCH = "processed-cache"


def pull_cache(config: dict) -> None:
    """Restore processed content, images, and hash cache from the
    ``processed-cache`` branch of the output repository.

    Clones / pulls ``deployment.target_repo`` into ``.temp/cache_repo``,
    checks out the ``processed-cache`` branch, and copies its contents
    (``content/``, ``static/images/``, ``.hash_cache.json``) to the
    project root.

    If the branch does not exist (first run), the function prints a
    warning and returns without error.
    """
    target_repo = config.get("deployment", {}).get("target_repo", "")
    if not target_repo:
        raise ValueError("Missing config: deployment.target_repo")

    token = os.getenv("GH_PAT")
    if not token:
        raise ValueError("Missing GH_PAT environment variable")

    project_root = os.getcwd()
    cache_path = os.path.join(project_root, ".temp", "cache_repo")
    clone_url = f"https://{token}@github.com/{target_repo}.git"

    _clone_or_pull(cache_path, clone_url)

    if not _branch_exists(cache_path, _CACHE_BRANCH):
        print(f"Branch '{_CACHE_BRANCH}' not found — this appears to be "
              f"the first run, skipping cache restore.")
        return

    _checkout_and_pull(cache_path, _CACHE_BRANCH)

    print(f"Restoring cache from {target_repo}@{_CACHE_BRANCH} ...")
    for item in _ITEMS:
        src = os.path.join(cache_path, item)
        dst = os.path.join(project_root, item)
        if not os.path.exists(src):
            print(f"  (skip) {item}: not in cache branch")
            continue
        if item == "content":
            # Merge-copy: cache files overwrite local, but local-only files survive
            if not os.path.isdir(dst):
                os.makedirs(dst, exist_ok=True)
            for root_dir, _dirs, files in os.walk(src):
                rel_dir = os.path.relpath(root_dir, src)
                target_dir = os.path.join(dst, rel_dir)
                os.makedirs(target_dir, exist_ok=True)
                for fname in files:
                    s = os.path.join(root_dir, fname)
                    d = os.path.join(target_dir, fname)
                    shutil.copy2(s, d)
        elif os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        elif os.path.isfile(src):
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copy2(src, dst)
        print(f"  restored {item}")
    print("Cache restore complete.")


def push_cache(config: dict) -> None:
    """Persist processed content, images, and hash cache to the
    ``processed-cache`` branch of the output repository.

    Copies ``content/``, ``static/images/``, and ``.hash_cache.json``
    from the project root into ``.temp/cache_repo``, commits them to the
    ``processed-cache`` branch, and pushes.  If there are no changes the
    commit is skipped.

    The commit message includes ``[skip ci]`` to prevent a recursive
    workflow trigger.
    """
    target_repo = config.get("deployment", {}).get("target_repo", "")
    if not target_repo:
        raise ValueError("Missing config: deployment.target_repo")

    token = os.getenv("GH_PAT")
    if not token:
        raise ValueError("Missing GH_PAT environment variable")

    project_root = os.getcwd()
    cache_path = os.path.join(project_root, ".temp", "cache_repo")
    clone_url = f"https://{token}@github.com/{target_repo}.git"

    _clone_or_pull(cache_path, clone_url)
    _ensure_branch(cache_path, _CACHE_BRANCH, clone_url)

    # Clear repo except .git
    for entry in os.listdir(cache_path):
        if entry == ".git":
            continue
        full = os.path.join(cache_path, entry)
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)

    # Copy items from project root to cache repo
    print(f"Saving cache to {target_repo}@{_CACHE_BRANCH} ...")
    for item in _ITEMS:
        src = os.path.join(project_root, item)
        dst = os.path.join(cache_path, item)
        if not os.path.exists(src):
            print(f"  (skip) {item}: not found in project root")
            continue
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        print(f"  saved {item}")

    # Commit and push
    orig_cwd = os.getcwd()
    os.chdir(cache_path)

    subprocess.run(
        ["git", "config", "user.name", "Auto Blog Poster"],
        check=False, timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.email", "auto-blog-poster@users.noreply.github.com"],
        check=False, timeout=10,
    )

    subprocess.run(["git", "add", "."], check=True, timeout=30)

    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        timeout=10,
    )
    if diff_result.returncode == 0:
        print("No cache changes — skipping commit.")
    else:
        msg = "Update processed cache [skip ci]"
        subprocess.run(["git", "commit", "-m", msg], check=True, timeout=30)
        print(f"Pushing to {_CACHE_BRANCH} ...")
        subprocess.run(
            ["git", "push", "origin", _CACHE_BRANCH],
            check=True, timeout=120,
        )
        print("Cache push complete.")

    os.chdir(orig_cwd)


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------

def _clone_or_pull(repo_path: str, clone_url: str) -> None:
    """Clone if missing, otherwise fetch."""
    if not os.path.isdir(repo_path):
        os.makedirs(os.path.dirname(repo_path) or ".", exist_ok=True)
        subprocess.run(
            ["git", "clone", clone_url, repo_path],
            check=True, timeout=120,
        )
    else:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=repo_path, check=True, timeout=60,
        )


def _branch_exists(repo_path: str, branch: str) -> bool:
    """Return True if *branch* exists locally or on origin."""
    result = subprocess.run(
        ["git", "branch", "-a"],
        cwd=repo_path,
        capture_output=True, text=True, timeout=10,
    )
    return branch in result.stdout or f"remotes/origin/{branch}" in result.stdout


def _checkout_and_pull(repo_path: str, branch: str) -> None:
    """Checkout *branch* and pull latest."""
    subprocess.run(
        ["git", "checkout", branch],
        cwd=repo_path, check=True, timeout=30,
    )
    subprocess.run(
        ["git", "pull", "origin", branch],
        cwd=repo_path, check=True, timeout=60,
    )


def _ensure_branch(repo_path: str, branch: str, clone_url: str) -> None:
    """Checkout *branch*, creating it orphaned if it does not exist,
    then push so it is available remotely."""
    if _branch_exists(repo_path, branch):
        _checkout_and_pull(repo_path, branch)
        return

    print(f"Creating orphan branch: {branch}")
    subprocess.run(
        ["git", "checkout", "--orphan", branch],
        cwd=repo_path, check=True, timeout=30,
    )
    subprocess.run(
        ["git", "rm", "-rf", "."],
        cwd=repo_path, check=False, timeout=30,
    )
    subprocess.run(
        ["git", "config", "user.name", "Auto Blog Poster"],
        cwd=repo_path, check=False, timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.email", "auto-blog-poster@users.noreply.github.com"],
        cwd=repo_path, check=False, timeout=10,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", f"Init {branch}"],
        cwd=repo_path, check=True, timeout=30,
    )
    subprocess.run(
        ["git", "push", "origin", branch],
        cwd=repo_path, check=True, timeout=120,
    )
    print(f"Created and pushed orphan branch: {branch}")
