# FI Podcast Picks

A few hand-picked podcast episodes a day on financial independence, retirement and investing, mostly from shows beyond the usual FI favorites, each with a short note on the argument and why it's worth a listen. Plus a few YouTube videos a day in a separate feed.

- **Page:** https://mylacc.github.io/podcast-picks/
- **Podcast feed:** https://mylacc.github.io/podcast-picks/feed.xml
- **Video feed:** https://mylacc.github.io/podcast-picks/videos.xml
- **Cover art:** `assets/cover.png` and `assets/video-cover.png` (3000x3000), drawn by `scripts/cover.py`

Add the podcast feed to any podcast app (AntennaPod: Add podcast, then "Add podcast by RSS address"). Each episode plays from the show's own audio file; nothing is re-hosted here.

Add the video feed to any RSS reader (Feeder, Inoreader, Feedly). Each item has the video's thumbnail, a summary, why it was picked, and a link that opens the video on YouTube.

## How it works

- `picks.json` is the only file edited by hand (or by the daily digest). Each pick names the show, the episode, a short `match` string found in the episode's title, the date it was picked, and a public note on why it's worth hearing.
- On every push to `picks.json`, the GitHub Actions workflow runs `scripts/build.py`, which finds each show's RSS feed through Apple's podcast directory (or `feed_url` / `itunes_id` if given), finds the episode by its `match` text, checks that the audio URL answers, takes the show's own cover art for that episode (linked, not copied), adds links back to the original episode page, the show's website and the show's own feed, and writes `feed.xml` and `index.html`. It then publishes them to GitHub Pages.
- The workflow also reruns daily at 6:55am New York time, so an episode whose audio reached its show's feed late still makes it in.
- A pick whose episode can't be found still shows on the page, but stays out of the feed until it resolves.

## Adding a pick

Append an object to `picks` in `picks.json`:

```json
{
  "date": "2026-10-30",
  "rank": 1,
  "show": "Rational Reminder",
  "search": "Rational Reminder",
  "title": "Episode title as published",
  "match": "distinctive words from the title",
  "published": "2026-10-29",
  "episode_url": "https://the-show's-own-episode-page",
  "timely": false,
  "why": "Two to four sentences on the argument and why it's worth a listen."
}
```

Optional: `itunes_id` (Apple Podcasts id, the number after `id` in the show's Apple URL) or `feed_url` to skip the directory search.

To check the build locally without network access: `python3 scripts/build.py --offline --out _site`.

## Video picks

- `youtube-channels.json` lists the channels the digest watches, with each channel's id (checked against the channel's own page), a role (`main` and `sometimes` mark video versions of podcasts the curator already follows; `outside` is the main pool) and a few search phrases for finding good videos from other channels.
- The **Video candidates** workflow runs twice each morning (and on changes to the channel list). It lists each channel's recent uploads with yt-dlp in flat mode (title, views, length, approximate upload date) and runs the searches, then force-pushes `candidates.json` to the `video-candidates` branch. yt-dlp runs in a read-only job; a separate job with no third-party code does the push. YouTube's own channel RSS feeds (`/feeds/videos.xml`) have been returning 404 since late 2025, so they aren't used. Video descriptions and captions aren't available this way: YouTube asks automated readers to sign in for those.
- `videos.json` holds the picks. The build checks each one through YouTube's public oEmbed endpoint (a removed or private video drops out), then writes `videos.xml` and adds the videos to the page under their day.

Append an object to `videos` in `videos.json`:

```json
{
  "date": "2026-10-30",
  "rank": 1,
  "channel": "Ben Felix",
  "channel_id": "UCDXTQ8nWmx_EhZ2v-kp7QxA",
  "video_id": "h3ajVyC5vJc",
  "title": "Video title as published",
  "published": "2026-10-19",
  "duration": "18:57",
  "timely": false,
  "summary": "Two or three sentences on what the video covers.",
  "why": "One or two sentences on why it's worth watching.",
  "audio_version": "Rational Reminder"
}
```

`audio_version` is optional: the podcast the same conversation is published in, when there is one.

To bump yt-dlp, change the pinned version in `.github/workflows/video-candidates.yml`.

Notes are summaries, not investment advice.
