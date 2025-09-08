#!/usr/bin/env python3
# update_readme_matplotlib.py
# Erzeugt eigene Stat-Bilder mit matplotlib, speichert PNG+SVG, aktualisiert README und pusht Änderungen.
# Voraussetzungen: pip install -r requirements.txt
# requirements.txt: requests==2.31.0 gitpython==3.1.31 matplotlib==3.8.0 pillow==10.1.0

import os
import datetime
from pathlib import Path
import requests
from git import Repo
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# ------------- Konfiguration -------------
USERNAME = os.environ.get("GH_USERNAME", "AustrianNoah")
REPO_NAME = os.environ.get("GH_REPO", USERNAME)
README_PATH = "README.md"
OUT_DIR = "assets/stats"
PNG_PATH = f"{OUT_DIR}/github_stats.png"
SVG_PATH = f"{OUT_DIR}/github_stats.svg"
COMMIT_MESSAGE = "chore: update profile stats (matplotlib)"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Optional, für API höhere Rate limits
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
        r = requests.get(f"https://api.github.com/users/{username}/repos", params={"per_page":100,"page":page}, headers=HEADERS, timeout=20)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos

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
    # show percent labels
    for i, b in enumerate(bars):
        w = b.get_width()
        ax.text(w + total*0.01, b.get_y() + b.get_height()/2, f"{perc[i]*100:.1f}%", va="center", fontsize=9)
    plt.tight_layout()
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)

def make_summary_card(user_info, repo_count, follower_count, out_png, out_svg):
    # Simple card: text summary with small horizontal bars for repos/followers
    plt.style.use("classic")
    fig, ax = plt.subplots(figsize=(8,2), dpi=150)
    ax.axis("off")
    name = user_info.get("name") or user_info.get("login")
    bio = user_info.get("bio") or ""
    created = user_info.get("created_at", "")[:10]
    # Text block
    text = f"{name}  •  @{user_info.get('login')}\n\n{bio}\n\nRepos: {repo_count}    Followers: {follower_count}    Joined: {created}"
    ax.text(0, 0.9, text, fontsize=11, va="top")
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    plt.close(fig)

def update_readme_with_images(repo_dir, png_path, svg_path):
    readme = Path(repo_dir) / README_PATH
    if not readme.exists():
        readme.write_text(f"# {USERNAME}\n\n")
    content = readme.read_text(encoding="utf-8")
    start = "<!-- STATS:START -->"
    end = "<!-- STATS:END -->"
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    section = (
        f"{start}\n"
        f"![stats]({png_path})\n\n"
        f"<!-- svg fallback -->\n"
        f"<img src=\"{svg_path}\" alt=\"stats svg\">\n\n"
        f"- **Repos:** {repo_count}\n"
        f"- **Followers:** {follower_count}\n"
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
    lang_totals = aggregate_language_bytes(repos)
    repo_count = user.get("public_repos", len(repos))
    follower_count = user.get("followers", 0)

    # Create visuals
    make_bar_chart_top_languages(lang_totals, USERNAME, PNG_PATH.replace(".png","_langs.png"), SVG_PATH.replace(".svg","_langs.svg"))
    make_summary_card(user, repo_count, follower_count, PNG_PATH.replace(".png","_card.png"), SVG_PATH.replace(".svg","_card.svg"))

    # Update README (reference the two generated PNGs)
    png_lang = f"{OUT_DIR}/github_stats_langs.png"
    svg_lang = f"{OUT_DIR}/github_stats_langs.svg"
    png_card = f"{OUT_DIR}/github_stats_card.png"
    svg_card = f"{OUT_DIR}/github_stats_card.svg"

    # global vars used in function scope
    # write README section using both images
    readme = Path(repo_dir) / README_PATH
    if not readme.exists():
        readme.write_text(f"# {USERNAME}\n\n")
    content = readme.read_text(encoding="utf-8")
    start = "<!-- STATS:START -->"
    end = "<!-- STATS:END -->"
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    section = (
        f"{start}\n"
        f"![languages]({png_lang})\n\n"
        f"<img src=\"{svg_card}\" alt=\"summary card\">\n\n"
        f"- **Repos:** {repo_count}\n"
        f"- **Followers:** {follower_count}\n"
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
        print("Updated images and README, pushed changes.")
    else:
        print("No changes to commit.")
