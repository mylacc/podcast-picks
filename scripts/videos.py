"""Video picks: videos.json -> videos.xml and the video cards on the page.

Each pick links to the video on YouTube; nothing is re-hosted. The build checks
each video through YouTube's public oEmbed endpoint and takes the title and
channel name from it, so a removed or private video drops out of the feed.
Standard library only; imported by build.py.
"""

import datetime as dt
import email.utils
import html
import json
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET

SITE_URL = "https://mylacc.github.io/podcast-picks/"
FEED_URL = SITE_URL + "videos.xml"
COVER_URL = SITE_URL + "video-cover.png"
TITLE = "FI Video Picks"
DESCRIPTION = (
    "A few hand-picked YouTube videos a day on financial independence, retirement "
    "and investing, each with a short summary and a note on why it's worth watching."
)
ATOM = "http://www.w3.org/2005/Atom"
CONTENT = "http://purl.org/rss/1.0/modules/content/"
MEDIA = "http://search.yahoo.com/mrss/"
DC = "http://purl.org/dc/elements/1.1/"


def watch_url(p):
    return "https://www.youtube.com/watch?v=" + p["video_id"]


def thumb_url(p):
    return "https://i.ytimg.com/vi/%s/hqdefault.jpg" % p["video_id"]


def channel_url(p):
    return "https://www.youtube.com/channel/" + p["channel_id"] if p.get("channel_id") else ""


def resolve(picks, offline, fetch, log, warn):
    for p in picks:
        p["resolved"] = None
        if offline:
            p["resolved"] = {"title": p["title"], "channel": p["channel"], "checked": False}
            continue
        url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(watch_url(p), safe="")
        try:
            with fetch(url) as r:
                o = json.load(r)
            p["resolved"] = {"title": o.get("title") or p["title"], "channel": o.get("author_name") or p["channel"],
                             "checked": True}
            log("OK  video %s | %s | %s" % (p["video_id"], p["resolved"]["channel"], p["resolved"]["title"]))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                warn("video %s (%s): not found on YouTube (HTTP %d); left out of the feed" % (p["video_id"], p["title"], e.code))
            else:  # 401/403 = embedding turned off, 5xx = YouTube trouble; the video likely still exists
                warn("video %s (%s): oEmbed HTTP %d; kept with the title from videos.json" % (p["video_id"], p["title"], e.code))
                p["resolved"] = {"title": p["title"], "channel": p["channel"], "checked": False}
        except Exception as e:  # noqa: BLE001
            warn("video %s (%s): oEmbed failed (%s); kept with the title from videos.json" % (p["video_id"], p["title"], e))
            p["resolved"] = {"title": p["title"], "channel": p["channel"], "checked": False}


def v_title(p):
    return (p.get("resolved") or {}).get("title") or p["title"]


def v_channel(p):
    return (p.get("resolved") or {}).get("channel") or p["channel"]


def audio_note(p):
    if p.get("audio_version"):
        return "Also a %s episode, if you'd rather listen." % p["audio_version"]
    return ""


def links(p):
    out = [("Watch on YouTube", watch_url(p))]
    if channel_url(p):
        out.append(("%s channel" % v_channel(p), channel_url(p)))
    return out


def build_feed(picks, pick_time, guid_slug, fmt_day):
    ET.register_namespace("atom", ATOM)
    ET.register_namespace("content", CONTENT)
    ET.register_namespace("media", MEDIA)
    ET.register_namespace("dc", DC)
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
    ET.SubElement(ch, "{%s}link" % ATOM, {"href": FEED_URL, "rel": "self", "type": "application/rss+xml"})
    ET.SubElement(ch, "lastBuildDate").text = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    for p in picks:
        if not p.get("resolved"):
            continue
        e = html.escape
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = "%s: %s" % (v_channel(p), v_title(p))
        ET.SubElement(it, "link").text = watch_url(p)
        ET.SubElement(it, "guid", {"isPermaLink": "false"}).text = "video-picks:%s:%s" % (p["date"], p["video_id"])
        ET.SubElement(it, "pubDate").text = email.utils.format_datetime(pick_time(p))
        ET.SubElement(it, "{%s}creator" % DC).text = v_channel(p)
        head = "%s, published %s%s.%s" % (
            v_channel(p), fmt_day(p["published"]), (", " + p["duration"]) if p.get("duration") else "",
            " Timely, watch soon." if p.get("timely") else "")
        parts = [head, p["summary"], "Why watch: " + p["why"]]
        if audio_note(p):
            parts.append(audio_note(p))
        lk = links(p)
        ET.SubElement(it, "description").text = "\n\n".join(parts) + "\n\n" + "\n".join("%s: %s" % l for l in lk)
        rich = ['<p><a href="%s"><img src="%s" width="480" height="360" alt="%s"></a></p>'
                % (e(watch_url(p), quote=True), e(thumb_url(p), quote=True), e(v_title(p), quote=True))]
        rich += ["<p>%s</p>" % e(head), "<p>%s</p>" % e(p["summary"]),
                 "<p><strong>Why watch:</strong> %s</p>" % e(p["why"])]
        if audio_note(p):
            rich.append("<p><em>%s</em></p>" % e(audio_note(p)))
        rich.append("<p>%s</p>" % " &middot; ".join('<a href="%s">%s</a>' % (e(u, quote=True), e(l)) for l, u in lk))
        ET.SubElement(it, "{%s}encoded" % CONTENT).text = "\n".join(rich)
        ET.SubElement(it, "{%s}thumbnail" % MEDIA, {"url": thumb_url(p), "width": "480", "height": "360"})
    ET.indent(rss, "  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def card(p, fmt_day):
    e = html.escape
    tags = ['<span class="tag">YouTube</span>', '<span class="tag">Published %s</span>' % e(fmt_day(p["published"]))]
    if p.get("duration"):
        tags.append('<span class="tag">%s</span>' % e(p["duration"]))
    if p.get("timely"):
        tags.append('<span class="tag timely">Timely</span>')
    extra = ['<a href="%s">Channel</a>' % e(channel_url(p), quote=True)] if channel_url(p) else []
    note = ('\n  <p class="note">%s</p>' % e(audio_note(p))) if audio_note(p) else ""
    return (
        '<article class="pick video">\n'
        '  <a class="thumb" href="%s"><img src="%s" alt="" width="128" height="72" loading="lazy"></a>\n'
        '  <div class="body">\n'
        '  <p class="show">%s</p>\n'
        '  <h3><a href="%s">%s</a></h3>\n'
        '  <p class="why">%s</p>\n'
        '  <p class="why"><strong>Why watch:</strong> %s</p>%s\n'
        '  <p class="meta">%s%s</p>\n'
        '  </div>\n'
        "</article>" % (
            e(watch_url(p), quote=True), e(thumb_url(p), quote=True), e(v_channel(p)),
            e(watch_url(p), quote=True), e(v_title(p)), e(p["summary"]), e(p["why"]), note,
            " ".join(tags), (" &middot; " + " &middot; ".join(extra)) if extra else ""))
