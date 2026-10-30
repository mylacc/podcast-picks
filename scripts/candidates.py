#!/usr/bin/env python3
"""List recent uploads from the channels in youtube-channels.json, plus recent
search hits from channels not on the list, for the daily digest to choose from.

Runs in GitHub Actions (YouTube isn't reachable from where the digest runs).
Reads each channel's public uploads list with yt-dlp in flat mode, which gives
title, id, views, length and an approximate upload date, but no description or
captions. YouTube's own channel RSS feeds have been returning 404 since late
2025, so they aren't used.

Usage: python3 scripts/candidates.py --out candidates.json [--days 14]
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Search filter: uploaded this week, videos only
SEARCH_SP = "EgQIAxAB"


def log(msg):
    print(msg, flush=True)


def warn(msg):
    print("::warning::" + msg, flush=True)


def flat(url, n):
    cmd = ["yt-dlp", "--flat-playlist", "--playlist-end", str(n), "--ignore-no-formats-error",
           "--extractor-args", "youtubetab:approximate_date", "-J", url]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if out.returncode:
        raise RuntimeError((out.stderr.strip().splitlines() or ["yt-dlp failed"])[-1])
    return json.loads(out.stdout)


def clock(seconds):
    if not seconds:
        return None
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def video(e, now, channel=None):
    ts = e.get("timestamp")
    published = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date() if ts else None
    age = (now.date() - published).days if published else None
    views = e.get("view_count")
    return {
        "video_id": e["id"],
        "url": "https://www.youtube.com/watch?v=" + e["id"],
        "title": e.get("title"),
        "channel": (channel or {}).get("name") or e.get("channel") or e.get("uploader"),
        "channel_id": (channel or {}).get("channel_id") or e.get("channel_id"),
        "role": (channel or {}).get("role", "unlisted"),
        "podcast": (channel or {}).get("podcast"),
        "published_approx": published.isoformat() if published else None,
        "age_days": age,
        "views": views,
        "views_per_day": round(views / max(age, 1)) if views and age is not None else None,
        "duration": clock(e.get("duration")),
        "duration_s": e.get("duration"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="candidates.json")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--per-channel", type=int, default=8)
    args = ap.parse_args()
    with open(os.path.join(ROOT, "youtube-channels.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    now = dt.datetime.now(dt.timezone.utc)
    channels, videos, failures = [], [], []
    listed = {c["channel_id"] for c in cfg["channels"]}
    for c in cfg["channels"]:
        try:
            d = flat("https://www.youtube.com/channel/%s/videos" % c["channel_id"], args.per_channel)
            entries = [video(e, now, c) for e in d.get("entries", []) if e.get("id")]
            recent = [v for v in entries if v["age_days"] is None or v["age_days"] <= args.days]
            videos += recent
            channels.append({"name": c["name"], "channel_id": c["channel_id"], "ok": True,
                             "title_on_youtube": d.get("channel") or d.get("title"),
                             "recent": len(recent), "newest": entries[0]["title"] if entries else None})
            log("OK   %-32s %2d recent  newest: %s" % (c["name"], len(recent), entries[0]["title"] if entries else "-"))
        except Exception as e:  # noqa: BLE001
            failures.append(c["name"])
            channels.append({"name": c["name"], "channel_id": c["channel_id"], "ok": False, "error": str(e)})
            warn("%s (%s): %s" % (c["name"], c["channel_id"], e))
    hits, seen = [], set()
    for q in cfg.get("search", []):
        url = "https://www.youtube.com/results?search_query=%s&sp=%s" % (urllib.parse.quote_plus(q), SEARCH_SP)
        try:
            d = flat(url, 15)
        except Exception as e:  # noqa: BLE001
            warn("search %r: %s" % (q, e))
            continue
        for e in d.get("entries", []):
            if not e.get("id") or e["id"] in seen or e.get("channel_id") in listed:
                continue
            if (e.get("duration") or 0) < 240:  # skip Shorts and clips
                continue
            seen.add(e["id"])
            v = video(e, now)
            if v["age_days"] is not None and v["age_days"] > args.days:
                continue
            v["query"] = q
            hits.append(v)
        log("search %-40s %d kept so far" % (repr(q), len(hits)))
    videos.sort(key=lambda v: (v["published_approx"] or "", v["views"] or 0), reverse=True)
    hits.sort(key=lambda v: v["views"] or 0, reverse=True)
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "note": ("Recent uploads from youtube-channels.json and recent search hits from other channels. "
                 "published_approx comes from YouTube's relative dates ('3 days ago') and can be a day off. "
                 "No descriptions or captions: YouTube asks automated readers to sign in for those."),
        "days": args.days,
        "channels": channels,
        "videos": videos,
        "search_hits": hits,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    log("Wrote %d channel videos and %d search hits; %d channels failed." % (len(videos), len(hits), len(failures)))
    if len(failures) == len(cfg["channels"]):
        sys.exit("Every channel failed; not publishing candidates.")


if __name__ == "__main__":
    main()
