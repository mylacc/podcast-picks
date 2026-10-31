#!/usr/bin/env python3
"""Merge a day's picks handed over as a JSON file into picks.json and videos.json.

The daily digest can't push to this repository, so it writes
<pending-dir>/YYYY-MM-DD.json ({"date": ..., "picks": [...], "videos": [...]},
same objects as picks.json and videos.json) and a session with push access
runs this script, commits and pushes. Already-present entries are skipped,
so running it twice is harmless. After the push succeeds, run it again with
--done to move the handed-over files to <pending-dir>/done/.

Usage: python3 scripts/publish_pending.py /mnt/project-files/podcast-picks/pending [--done]
Prints the dates of the files it read, one per line (nothing if there were none).
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICK_FIELDS = {"date", "rank", "show", "title", "match", "published", "episode_url", "why"}
VIDEO_FIELDS = {"date", "rank", "channel", "video_id", "title", "published", "summary", "why"}


def load(name, key):
    path = os.path.join(ROOT, name)
    with open(path, encoding="utf-8") as f:
        return path, json.load(f), key


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    pending = sys.argv[1]
    files = sorted(f for f in os.listdir(pending) if f.endswith(".json"))
    if not files:
        return
    ppath, picks, _ = load("picks.json", "picks")
    vpath, videos, _ = load("videos.json", "videos")
    have_picks = {(p["date"], p["show"], p["title"]) for p in picks["picks"]}
    have_videos = {v["video_id"] for v in videos["videos"]}
    merged = []
    for name in files:
        with open(os.path.join(pending, name), encoding="utf-8") as f:
            day = json.load(f)
        for p in day.get("picks", []):
            missing = PICK_FIELDS - p.keys()
            if missing:
                sys.exit("%s: pick %r is missing %s" % (name, p.get("title"), sorted(missing)))
            if isinstance(p.get("itunes_id"), str) and p["itunes_id"].isdigit():
                p["itunes_id"] = int(p["itunes_id"])
            if (p["date"], p["show"], p["title"]) not in have_picks:
                picks["picks"].append(p)
                have_picks.add((p["date"], p["show"], p["title"]))
        for v in day.get("videos", []):
            missing = VIDEO_FIELDS - v.keys()
            if missing:
                sys.exit("%s: video %r is missing %s" % (name, v.get("title"), sorted(missing)))
            if v["video_id"] not in have_videos:
                videos["videos"].append(v)
                have_videos.add(v["video_id"])
        merged.append(name)
    save(ppath, picks)
    save(vpath, videos)
    for name in merged:
        print(name[:-5])
    if "--done" in sys.argv:
        os.makedirs(os.path.join(pending, "done"), exist_ok=True)
        for name in merged:
            shutil.move(os.path.join(pending, name), os.path.join(pending, "done", name))


if __name__ == "__main__":
    main()
