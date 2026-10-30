#!/usr/bin/env python3
"""Build feed.xml, videos.xml and index.html from picks.json and videos.json.

For each pick, find the show's own RSS feed (feed_url, else Apple's lookup by
itunes_id, else Apple's search by name), find the episode in it by the "match"
text, and point the enclosure at the show's original audio file. Nothing is
re-hosted. Standard library only.

Usage: python3 scripts/build.py [--out _site] [--offline]
"""

import argparse
import datetime as dt
import email.utils
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import videos

SITE_URL = "https://mylacc.github.io/podcast-picks/"
FEED_URL = SITE_URL + "feed.xml"
COVER_URL = SITE_URL + "cover.png"
REPO_URL = "https://github.com/mylacc/podcast-picks"
TITLE = "FI Podcast Picks"
DESCRIPTION = (
    "A few hand-picked episodes a day on financial independence, retirement "
    "and investing, mostly from shows beyond the usual FI favorites, each "
    "with a short note on the argument and why it's worth a listen."
)
UA = "podcast-picks/1.0 (+" + REPO_URL + ")"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
CONTENT = "http://purl.org/rss/1.0/modules/content/"
# Picks go into the feed at 6:45am New York time on the day they were picked.
PICK_HOUR_UTC_OFFSET = -4  # EDT; good enough for ordering, not shown to anyone
PICK_HOUR = 6
PICK_MINUTE = 45


def log(msg):
    print(msg, flush=True)


def warn(msg):
    print("::warning::" + msg, flush=True)


def fetch(url, timeout=30, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def itunes_feed(pick):
    if pick.get("feed_url"):
        return pick["feed_url"], "feed_url"
    if pick.get("itunes_id"):
        url = "https://itunes.apple.com/lookup?entity=podcast&id=%d" % pick["itunes_id"]
    else:
        term = urllib.parse.quote_plus(pick.get("search") or pick["show"])
        url = "https://itunes.apple.com/search?media=podcast&entity=podcast&limit=5&term=" + term
    with fetch(url) as r:
        results = json.load(r).get("results", [])
    want = norm(pick["show"])
    best = None
    for res in results:
        name = norm(res.get("collectionName", ""))
        if res.get("feedUrl") and (want in name or name in want):
            best = res
            break
    if best is None:
        best = next((res for res in results if res.get("feedUrl")), None)
    if best is None:
        raise RuntimeError("no Apple result with a feed for %r" % pick["show"])
    return best["feedUrl"], "Apple: %s" % best.get("collectionName")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def parse_date(s):
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


_feed_cache = {}


def feed_items(feed_url):
    if feed_url not in _feed_cache:
        with fetch(feed_url, timeout=60) as r:
            root = ET.fromstring(r.read())
        ch = root.find("channel")
        art = ""
        if ch is not None:
            tag = ch.find("{%s}image" % ITUNES)
            art = (tag.get("href") if tag is not None else "") or (ch.findtext("image/url") or "")
        art = art.strip() if art.strip().startswith("https://") else ""
        home = ((ch.findtext("link") if ch is not None else "") or "").strip()
        home = home if home.startswith("https://") else ""
        items = []
        for it in root.iter("item"):
            enc = it.find("enclosure")
            items.append({
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip(),
                "guid": (it.findtext("guid") or "").strip(),
                "pubDate": parse_date(it.findtext("pubDate") or ""),
                "duration": (it.findtext("{%s}duration" % ITUNES) or "").strip(),
                "show_image": art,
                "show_link": home,
                "enclosure": None if enc is None else {
                    "url": enc.get("url"),
                    "type": enc.get("type") or "audio/mpeg",
                    "length": enc.get("length") or "0",
                },
            })
        _feed_cache[feed_url] = items
    return _feed_cache[feed_url]


def find_episode(pick, items):
    m = norm(pick["match"])
    hits = [it for it in items if m in norm(it["title"]) and it["enclosure"] and it["enclosure"]["url"]]
    if not hits:
        return None
    target = dt.datetime.fromisoformat(pick["published"]).replace(tzinfo=dt.timezone.utc)
    hits.sort(key=lambda it: abs((it["pubDate"] - target).total_seconds()) if it["pubDate"] else 1e12)
    return hits[0]


def check_audio(url):
    """Return (ok, detail). Tries HEAD, then a one-byte GET for hosts that refuse HEAD."""
    for method, headers in (("HEAD", None), ("GET", {"Range": "bytes=0-0"})):
        try:
            with fetch(url, timeout=30, method=method, headers=headers) as r:
                ctype = r.headers.get("Content-Type", "")
                ok = r.status < 400 and (ctype.startswith("audio/") or "octet-stream" in ctype or "mpeg" in ctype)
                detail = "%s %s %s" % (method, r.status, ctype)
                if ok:
                    return True, detail
        except Exception as e:  # noqa: BLE001
            detail = "%s failed: %s" % (method, e)
    return False, detail


def resolve(picks, offline):
    for p in picks:
        p["resolved"] = None
        if offline:
            continue
        try:
            feed_url, how = itunes_feed(p)
            ep = find_episode(p, feed_items(feed_url))
            if ep is None:
                warn("%s / %s: no episode matching %r in %s" % (p["show"], p["title"], p["match"], feed_url))
                continue
            ok, detail = check_audio(ep["enclosure"]["url"])
            if not ok:
                warn("%s / %s: audio check failed (%s)" % (p["show"], ep["title"], detail))
            p["resolved"] = {**ep, "feed_url": feed_url, "found_via": how, "audio_check": detail, "audio_ok": ok}
            log("OK  %s | %s | %s | %s | art %s" % (p["show"], ep["title"], ep["enclosure"]["url"], detail, ep["show_image"] or "none"))
        except Exception as e:  # noqa: BLE001
            warn("%s / %s: %s" % (p["show"], p["title"], e))


def pick_time(p):
    d = dt.date.fromisoformat(p["date"])
    tz = dt.timezone(dt.timedelta(hours=PICK_HOUR_UTC_OFFSET))
    # Top pick gets the latest timestamp so podcast apps list it first.
    return dt.datetime(d.year, d.month, d.day, PICK_HOUR, PICK_MINUTE, tzinfo=tz) - dt.timedelta(minutes=p.get("rank", 1))


def slug(s):
    return norm(s).replace(" ", "-")[:60]


def guid(p):
    return "podcast-picks:%s:%s:%s" % (p["date"], slug(p["show"]), slug(p["title"]))


def fmt_day(iso):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


def ep_title(p):
    r = p.get("resolved")
    return r["title"] if r and r["title"] else p["title"]


def ep_link(p):
    r = p.get("resolved")
    return (r["link"] if r and r["link"].startswith("https://") else "") or p["episode_url"]


def source_links(p):
    """Links back to the original episode and show, all taken from the show's own feed."""
    r = p.get("resolved") or {}
    links = [("Original episode", ep_link(p))]
    if r.get("show_link"):
        links.append(("%s website" % p["show"], r["show_link"]))
    if r.get("feed_url"):
        links.append(("%s feed (subscribe)" % p["show"], r["feed_url"]))
    return links


def build_feed(picks):
    ET.register_namespace("itunes", ITUNES)
    ET.register_namespace("atom", ATOM)
    ET.register_namespace("content", CONTENT)
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = TITLE
    ET.SubElement(ch, "link").text = SITE_URL
    ET.SubElement(ch, "description").text = DESCRIPTION
    ET.SubElement(ch, "language").text = "en-us"
    img = ET.SubElement(ch, "image")
    ET.SubElement(img, "url").text = COVER_URL
    ET.SubElement(img, "title").text = TITLE
    ET.SubElement(img, "link").text = SITE_URL
    ET.SubElement(ch, "{%s}image" % ITUNES, {"href": COVER_URL})
    ET.SubElement(ch, "{%s}link" % ATOM, {"href": FEED_URL, "rel": "self", "type": "application/rss+xml"})
    ET.SubElement(ch, "lastBuildDate").text = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    ET.SubElement(ch, "{%s}author" % ITUNES).text = TITLE
    ET.SubElement(ch, "{%s}summary" % ITUNES).text = DESCRIPTION
    ET.SubElement(ch, "{%s}explicit" % ITUNES).text = "false"
    ET.SubElement(ch, "{%s}category" % ITUNES, {"text": "Business"}).append(
        ET.Element("{%s}category" % ITUNES, {"text": "Investing"}))
    for p in picks:
        r = p.get("resolved")
        if not r:
            continue
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = "%s: %s" % (p["show"], ep_title(p))
        ET.SubElement(it, "link").text = ep_link(p)
        ET.SubElement(it, "guid", {"isPermaLink": "false"}).text = guid(p)
        ET.SubElement(it, "pubDate").text = email.utils.format_datetime(pick_time(p))
        published = fmt_day(p["published"])
        desc = "%s, published %s. %s%s" % (p["show"], published, "Timely, listen soon. " if p.get("timely") else "", p["why"])
        links = source_links(p)
        plain = desc + "\n\n" + "\n".join("%s: %s" % (label, url) for label, url in links)
        rich = "<p>%s</p>\n<p>%s</p>" % (
            html.escape(desc),
            " &middot; ".join('<a href="%s">%s</a>' % (html.escape(url, quote=True), html.escape(label)) for label, url in links))
        ET.SubElement(it, "description").text = plain
        ET.SubElement(it, "{%s}encoded" % CONTENT).text = rich
        ET.SubElement(it, "{%s}summary" % ITUNES).text = plain
        enc = r["enclosure"]
        ET.SubElement(it, "enclosure", {"url": enc["url"], "type": enc["type"], "length": str(enc["length"] or 0)})
        if r.get("duration"):
            ET.SubElement(it, "{%s}duration" % ITUNES).text = r["duration"]
        if r.get("show_image"):
            ET.SubElement(it, "{%s}image" % ITUNES, {"href": r["show_image"]})
    ET.indent(rss, "  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def build_page(picks, vids):
    e = html.escape
    days = {}
    for p in picks:
        days.setdefault(p["date"], []).append(p)
    for v in vids:
        days.setdefault(v["date"], [])
    sections = []
    for day in sorted(days, reverse=True):
        cards = []
        for p in sorted(days[day], key=lambda p: p.get("rank", 99)):
            tags = ['<span class="tag">Published %s</span>' % e(fmt_day(p["published"]))]
            if p.get("timely"):
                tags.append('<span class="tag timely">Timely</span>')
            r = p.get("resolved")
            audio = " &middot; ".join(
                ['<a href="%s">%s</a>' % (e(url, quote=True), "Show feed" if "feed" in label else "Show website")
                 for label, url in source_links(p)[1:]]
                + (['<a href="%s">Audio</a>' % e(r["enclosure"]["url"], quote=True)] if r else []))
            art = r.get("show_image") if r else ""
            img = ('<img class="art" src="%s" alt="%s cover" width="64" height="64" loading="lazy">'
                   % (e(art, quote=True), e(p["show"], quote=True))) if art else '<div class="art"></div>'
            cards.append(
                '<article class="pick">\n'
                '  %s\n'
                '  <div class="body">\n'
                '  <p class="show">%s</p>\n'
                '  <h3><a href="%s">%s</a></h3>\n'
                '  <p class="why">%s</p>\n'
                '  <p class="meta">%s%s</p>\n'
                '  </div>\n'
                "</article>" % (
                    img, e(p["show"]), e(ep_link(p), quote=True), e(ep_title(p)), e(p["why"]),
                    " ".join(tags), (" &middot; " + audio) if audio else ""))
        for v in sorted((v for v in vids if v["date"] == day and v.get("resolved")), key=lambda v: v.get("rank", 99)):
            cards.append(videos.card(v, fmt_day))
        sections.append('<section>\n<h2>%s</h2>\n%s\n</section>' % (e(fmt_day(day)), "\n".join(cards)))
    with open(os.path.join(os.path.dirname(__file__), "page.html"), encoding="utf-8") as f:
        tpl = f.read()
    return (tpl.replace("{{TITLE}}", e(TITLE))
               .replace("{{DESCRIPTION}}", e(DESCRIPTION))
               .replace("{{FEED_URL}}", e(FEED_URL))
               .replace("{{VIDEO_FEED_URL}}", e(videos.FEED_URL))
               .replace("{{REPO_URL}}", e(REPO_URL))
               .replace("{{PICKS}}", "\n".join(sections)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    ap.add_argument("--offline", action="store_true", help="skip network lookups (layout check only)")
    args = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "picks.json"), encoding="utf-8") as f:
        picks = json.load(f)["picks"]
    picks.sort(key=lambda p: (p["date"], -p.get("rank", 99)), reverse=True)
    resolve(picks, args.offline)
    vids = []
    if os.path.exists(os.path.join(root, "videos.json")):
        with open(os.path.join(root, "videos.json"), encoding="utf-8") as f:
            vids = json.load(f)["videos"]
    vids.sort(key=lambda p: (p["date"], -p.get("rank", 99)), reverse=True)
    videos.resolve(vids, args.offline, fetch, log, warn)
    os.makedirs(args.out, exist_ok=True)
    feed = build_feed(picks)
    ET.fromstring(feed)  # must be well-formed
    with open(os.path.join(args.out, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(feed)
    vfeed = videos.build_feed(vids, pick_time, slug, fmt_day)
    ET.fromstring(vfeed)  # must be well-formed
    with open(os.path.join(args.out, "videos.xml"), "w", encoding="utf-8") as f:
        f.write(vfeed)
    for name in ("cover.png", "video-cover.png"):
        shutil.copyfile(os.path.join(root, "assets", name), os.path.join(args.out, name))
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_page(picks, vids))
    with open(os.path.join(args.out, "resolved.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in p.items() if k != "why"} for p in picks], f, indent=2, default=str)
    ok = sum(1 for p in picks if p.get("resolved"))
    log("Resolved %d of %d picks into the feed." % (ok, len(picks)))
    log("Video feed: %d of %d videos." % (sum(1 for v in vids if v.get("resolved")), len(vids)))
    if not args.offline and ok == 0:
        sys.exit("No picks resolved; not publishing an empty feed.")


if __name__ == "__main__":
    main()
