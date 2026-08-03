import os
import subprocess


def build_site(config: dict) -> None:
    """Run Hugo to generate the static site into the ``public/`` directory.

    Reads ``hugo.executable`` (default ``"hugo"``) and optional
    ``hugo.build_options`` (e.g. ``"--minify"``) from *config*.  Executes
    the build in the current working directory with a 120-second timeout.

    Args:
        config: Full application configuration dict.

    Raises:
        RuntimeError: If the Hugo build exits with a non-zero return code.
    """
    hugo_cfg = config.get("hugo", {})
    executable = hugo_cfg.get("executable", "hugo")
    build_options = hugo_cfg.get("build_options", "")

    cmd = [executable]
    if build_options:
        cmd.extend(build_options.split())

    print(f"Building Hugo site ({' '.join(cmd)}) ...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Hugo build timed out after 600 seconds"
        ) from e

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout_tail = result.stdout.strip()[-500:] if result.stdout else "(empty)"
        raise RuntimeError(
            f"Hugo build failed with exit code {result.returncode}.\n"
            f"STDERR: {stderr}\n"
            f"STDOUT (tail): {stdout_tail}"
        )

    print("Hugo build finished.")

    # README screenshots are generated from the exact build artifact before
    # validation and deployment. A preview failure should not block publishing.
    try:
        from modules import readme_preview

        print("Capturing README previews ...")
        readme_preview.capture_previews(config)
    except Exception as exc:
        print(f"WARNING: README preview capture failed: {exc}")
