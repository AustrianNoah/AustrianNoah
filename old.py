#!/usr/bin/env python3
# update_readme_matplotlib_lines.py
# Erzeugt Stat-Bilder mit matplotlib und zählt Codezeilen über alle (nicht-fork) Repos.
# requirements.txt includes: requests, gitpython, matplotlib, pillow

import os
import datetime
import tempfile
from pathlib import Path
import requests
from git import Repo, GitCommandError
import matplotlib.pyplot as plt
import subprocess

# ------------- Konfiguration -------------
USERNAME = os.environ.get("GH_USERNAME", "AustrianNoah")
REPO_NAME = os.environ.get("GH_REPO", USERNAME)
README_PATH = "README.md"
OUT_DIR = "assets/stats"
PNG_LANGS = f"{OUT_DIR}/github_stats_langs.png"
SVG_LANGS = f"{OUT_DIR}/github_stats_langs.svg"
PNG_CARD = f"{OUT_DIR}/github_stats_card.png"
SVG_CARD = f"{OUT_DIR}/github_stats_card.svg"
COMMIT_MESSAGE = "chore: update profile stats (matplotlib + line counts)"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Optional but recommended
# Dateiendungen, die als Quellcode/Text gezählt werden
CODE_EXTS = {".py",".js",".ts",".java",".c",".cpp",".h",".hpp",".go",".rb",".rs",".swift",
             ".kt",".kts",".scala",".php",".html",".css",".scss",".md",".json",".yaml",".yml",
             ".sh",".ps1",".rs",".lua",".pl",".r"}
# Max Repos to clone (safety)
MAX_CLONES = 20
# ------------- Ende Konfiguration -------------

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def fetch_user_info(username):
    r = requests.get(f"https://api.github.com/users/{username}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

def fetch_repos(username):
    repos = []
    page = 1
    while True:
        r = requests.get(f"https://api.github.com/users/{username}/repos", params={"per_page":100,"page":page,"sort":"updated"}, headers=HEADERS, timeout=20)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos

def count_lines_in_dir(path: Path):
    total = 0
    files_counted = 0
    for p in path.rglob('*'):
        if p.is_file():
            if p.suffix.lower() in CODE_EXTS:
                try:
                    with p.open('rb') as f:
                        # decode heuristics: try utf-8, fallback latin-1
                        try:
                            content = f.read().decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                content = f.read().decode('latin-1')
                            except Exception:
                                continue
                        lines = content.count('\n') + 1 if content else 0
                        total += lines
                        files_counted += 1
                except Exception:
                    continue
    return total, files_counted

def clone_and_count(repo_clone_url, default_branch, tmpdir, auth_token=None):
    # Clone single-repo shallow default branch
    clone_path = Path(tmpdir) / (repo_clone_url.split('/')[-1].replace('.git',''))
    git_url = repo_clone_url
    if auth_token:
        # insert token for private access: https://<token>@github.com/owner/repo.git
        git_url = git_url.replace("https://", f"https://{auth_token}@")
    try:
        Repo.clone_from(git_url, clone_path, branch=default_branch, depth=1, single_branch=True)
    except GitCommandError:
        # Try without specifying branch
        try:
            Repo.clone_from(git_url, clone_path, depth=1)
        except Exception:
            return 0,0
    lines, files = count_lines_in_dir(clone_path)
    return lines, files

def aggregate_language_bytes(repos):
    totals = {}
    for r in repos:
        if r.get("fork"):
            continue
        langs_url = r.get("languages_url")
        if not langs_url:
            continue
        try:
            lr = requests.get(langs_url, headers=HEADERS, timeout=15)
            lr.raise_for_status()
            langs = lr.json()
            for lang, b in langs.items():
                totals[lang] = totals.get(lang, 0) + b
        except Exception:
            continue
    return totals

def make_bar_chart_top_languages(lang_totals, username, out_png, out_svg, top_n=8):
    if not lang_totals:
        lang_totals = {"No code": 1}
    items = sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    labels = [k for k,v in items][::-1]
    values = [v for k,v in items][::-1]
    total = sum(values)
    perc = [v/total for v in values]

    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(8,4.5), dpi=150)
    bars = ax.barh(range(len(labels)), values, color=plt.cm.tab20.colors[:len(labels)])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Bytes of code")
    ax.set_title(f"{username} — Top {len(labels)} languages")
    for i, b in enumerate(bars):
        w = b.get_width()
        ax.text(w + total*0.01, b.get_y() + b.get_height()/2, f"{perc[i]*100:.1f}%", va="center", fontsize=9)
    plt.tight_layout()
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)

def make_summary_card(user_info, repo_count, follower_count, total_lines, out_png, out_svg):
    plt.style.use("classic")
    fig, ax = plt.subplots(figsize=(8,2), dpi=150)
    ax.axis("off")
    name = user_info.get("name") or user_info.get("login")
    bio = user_info.get("bio") or ""
    created = user_info.get("created_at", "")[:10]
    text = f"{name}  •  @{user_info.get('login')}\n\n{bio}\n\nRepos: {repo_count}    Followers: {follower_count}    Code lines (est.): {total_lines:,}    Joined: {created}"
    ax.text(0, 0.9, text, fontsize=11, va="top")
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)

def commit_and_push(repo_dir, message):
    repo = Repo(repo_dir)
    repo.git.add(all=True)
    if repo.is_dirty(untracked_files=True):
        repo.index.commit(message)
        origin = repo.remote(name="origin")
        origin.push()
        return True
    return False

if __name__ == "__main__":
    repo_dir = Path.cwd()
    user = fetch_user_info(USERNAME)
    repos = fetch_repos(USERNAME)
    nonfork_repos = [r for r in repos if not r.get("fork")]
    lang_totals = aggregate_language_bytes(nonfork_repos)
    repo_count = user.get("public_repos", len(nonfork_repos))
    follower_count = user.get("followers", 0)

    total_lines = 0
    total_files = 0
    clones = 0
    with tempfile.TemporaryDirectory() as td:
        for r in nonfork_repos:
            if clones >= MAX_CLONES:
                break
            clones += 1
            clone_url = r.get("clone_url")
            default_branch = r.get("default_branch") or None
            lines, files = clone_and_count(clone_url, default_branch, td, auth_token=GITHUB_TOKEN)
            total_lines += lines
            total_files += files

    # Create visuals
    make_bar_chart_top_languages(lang_totals, USERNAME, PNG_LANGS, SVG_LANGS)
    make_summary_card(user, repo_count, follower_count, total_lines, PNG_CARD, SVG_CARD)

    # Update README
    readme = Path(repo_dir) / README_PATH
    if not readme.exists():
        readme.write_text(f"# {USERNAME}\n\n")
    content = readme.read_text(encoding="utf-8")
    start = "<!-- STATS:START -->"
    end = "<!-- STATS:END -->"
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    section = (
        f"{start}\n"
        f"![languages]({OUT_DIR}/github_stats_langs.png)\n\n"
        f"<img src=\"{OUT_DIR}/github_stats_card.svg\" alt=\"summary card\">\n\n"
        f"- **Repos:** {repo_count}\n"
        f"- **Followers:** {follower_count}\n"
        f"- **Estimated code lines (counted {clones} repos):** {total_lines:,}\n"
        f"- **Updated (UTC):** {ts}\n"
        f"{end}"
    )
    if start in content and end in content:
        pre = content.split(start)[0]
        post = content.split(end)[1]
        new = pre + section + post
    else:
        if not content.endswith("\n"):
            content += "\n"
        new = content + "\n" + section + "\n"
    readme.write_text(new, encoding="utf-8")

    changed = commit_and_push(repo_dir, COMMIT_MESSAGE)
    if changed:
        print(f"Updated images and README, pushed changes. Lines: {total_lines}, files: {total_files}, repos counted: {clones}")
    else:
        print("No changes to commit.")
