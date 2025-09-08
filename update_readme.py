#!/usr/bin/env python3
# update_readme_using_readme_stats.py
# Nutzt github-readme-stats (https://github.com/anuraghazra/github-readme-stats) als Bild-URL-Generator
# Voraussetzungen: pip install -r requirements.txt

import os
from pathlib import Path
from git import Repo
import datetime
import requests

# Konfiguration
USERNAME = os.environ.get("GH_USERNAME", "your-username")
REPO_NAME = os.environ.get("GH_REPO", USERNAME)
README_PATH = "README.md"
IMAGE_PATH = "assets/github-stats.png"  # wir speichern das von the service erzeugte PNG lokal
COMMIT_MESSAGE = "chore: update profile stats (github-readme-stats)"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# github-readme-stats endpoints (Bild-URLs)
# Beispiel: https://github-readme-stats.vercel.app/api?username=anuraghazra&show_icons=true&theme=dark
def build_stats_url(username, theme="default", show_icons="true"):
    base = "https://github-readme-stats.vercel.app/api"
    qs = f"?username={username}&show_icons={show_icons}&theme={theme}"
    return base + qs

def download_image(url, out_path):
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    os.makedirs(Path(out_path).parent, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(1024):
            f.write(chunk)
    return out_path

def update_readme_with_image(repo_dir, image_rel_path):
    readme_file = Path(repo_dir) / README_PATH
    if not readme_file.exists():
        readme_file.write_text(f"# {USERNAME}\n\n")
    content = readme_file.read_text(encoding="utf-8")
    start_marker = "<!-- STATS:START -->"
    end_marker = "<!-- STATS:END -->"
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    new_section = (
        f"{start_marker}\n"
        f"![github-stats]({image_rel_path})\n\n"
        f"- **Last update (UTC):** {timestamp}\n"
        f"{end_marker}"
    )
    if start_marker in content and end_marker in content:
        pre = content.split(start_marker)[0]
        post = content.split(end_marker)[1]
        new_content = pre + new_section + post
    else:
        if not content.endswith("\n"):
            content += "\n"
        new_content = content + "\n" + new_section + "\n"
    readme_file.write_text(new_content, encoding="utf-8")
    return readme_file

def commit_and_push(repo_dir, commit_message):
    repo = Repo(repo_dir)
    repo.git.add(all=True)
    if repo.is_dirty(untracked_files=True):
        repo.index.commit(commit_message)
        origin = repo.remote(name="origin")
        origin.push()
        return True
    return False

def main():
    repo_dir = Path.cwd()
    stats_url = build_stats_url(USERNAME, theme="gruvbox")
    download_image(stats_url, IMAGE_PATH)
    update_readme_with_image(repo_dir, IMAGE_PATH)
    changed = commit_and_push(repo_dir, COMMIT_MESSAGE)
    if changed:
        print("Updated README with github-readme-stats and pushed.")
    else:
        print("No changes detected.")

if __name__ == "__main__":
    main()
