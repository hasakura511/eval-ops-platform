# OOS Evidence Collection Prompt

Purpose: use a browsing-capable model to collect evidence for a single task so the
scoring pipeline can run offline.

## Workflow (human-in-the-loop)
1) You provide input tasks (query/result + links).
2) We collect evidence (tools.evidence only).
3) We extract features from cached evidence.
4) We score and produce predictions.
5) You provide ground-truth labels.
6) We join labels + features, refit thresholds, and repeat.

## How to use
1) Paste the task package (query/result + links).
2) Send the prompt below to the browsing model.
3) Save the returned "Answer Packet" as-is.

## Prompt template (fill in TASK_PACKAGE_JSON)

```
You are collecting evidence for a media-hint relevance evaluation.
Follow links and summarize only the fields below. Be concise and exact.

TASK_PACKAGE_JSON:
{PASTE_TASK_JSON_HERE}

Instructions:
- Use tools.evidence (BeautifulSoup-style parsing) only. Do not use Playwright.
- Keep output minimal; avoid full-page dumps or large excerpts.
- Open the Query IMDb link first. If blocked/consent/captcha, note `blocked`.
- From Query IMDb (preferred) OR Query Google fallback:
  - List top 5 candidates with name/title, type (movie/series/person/etc),
    year, IMDb URL if present, and votes/rating (or STARmeter for people).
- Open Result IMDb link next. If blocked, note `blocked` and try Result Google.
  - Extract official_title, content_type, imdb_rating, imdb_votes, year, imdb_url.
  - If the result is not an IMDb title/person (category/listing), note that.
- If you identify a best alternative (more likely than the result), call it out.
- Report any errors, blocks, or missing data explicitly.

Return exactly this structure:

A) Task Package
<echo the original JSON>

B) Evidence Summary
1. Result IMDb
   - official_title:
   - content_type:
   - imdb_rating:
   - imdb_votes:
   - year:
   - imdb_url:
2. Query Candidates (top 5)
   #: 1 ...
   #: 2 ...
   ...
3. Best Alternative (if any)
   - name:
   - imdb_url:
   - content_type:
   - imdb_rating:
   - imdb_votes:
   - starmeter:
4. Blocks/Errors
   - list any blocked/consent/captcha or missing data

C) Notes
- 1-3 sentences on relevance (if obvious) and any ambiguity.
```
