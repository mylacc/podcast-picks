# FI Podcast Picks

A few hand-picked podcast episodes a day on financial independence, retirement and investing, mostly from shows beyond the usual FI favorites, each with a short note on the argument and why it's worth a listen.

- **Page:** https://mylacc.github.io/podcast-picks/
- **Podcast feed:** https://mylacc.github.io/podcast-picks/feed.xml
- **Cover art:** `assets/cover.png` (3000x3000), drawn by `scripts/cover.py`

Add the feed address to any podcast app (AntennaPod: Add podcast, then "Add podcast by RSS address"). Each episode plays from the show's own audio file; nothing is re-hosted here.

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

Notes are summaries, not investment advice.
