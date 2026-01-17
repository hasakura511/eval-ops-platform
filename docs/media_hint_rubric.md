# Media Hint Relevance -- Fuzzy Rubric (Human + LLM Friendly)

## 0) Output constraints (what evaluators must produce)
**Rating** (one of):
- Perfect
- Good
- Acceptable
- Unacceptable: Other
- Unacceptable: Spelling
- Unacceptable: Concerns
- Problem: Other

**Comment** (exactly 1 sentence):
- Must include **mode** (Prefix-mode or Intent-mode)
- Must include **match basis** (prefix / franchise / semantic)
- Must include **one** primary downgrade reason (incomplete / alternative exists / niche / irrelevant / evidence blocked / spelling)

Template:
> `<Mode>; <basis>; <reason>.`

---

## 1) Evidence-first principle (confidence)
You must use provided links to validate the suggestion.

**Preferred evidence order**
1) **Result IMDb** (official title/type + popularity proxy)
2) **Result Google** (fallback if IMDb unavailable)
3) **Query IMDb/Google** (to find better alternatives / dominant completion)

**Evidence Confidence**
- **High**: IMDb page loads and clearly identifies title/type + votes (or STARmeter for people)
- **Medium**: IMDb blocked but Google provides a strong canonical match
- **Low**: both blocked / broken / can't validate title/type

**Low confidence rule**
- If **Low**, return **Problem: Other** with:
  "Cannot validate result due to system/links; evaluation blocked."

---

## 2) Hard gates (first match wins)
### 2A) Policy/Concerns gate
If query/result indicates explicit adult content, extreme violence, hate, or disallowed content:
- **Rating**: Unacceptable: Concerns
- **Comment**: "Policy concern content; must be filtered."

### 2B) Validation failure gate
If result text is blank/placeholder OR links are broken/blocked such that title/type cannot be validated:
- **Rating**: Problem: Other
- **Comment**: "Cannot validate result due to system/links; evaluation blocked."

### 2C) Spelling/Format gate (strict, uses official title string)
Determine the **official** title spelling (IMDb preferred; Google fallback).
If suggestion has a genuine mismatch vs the official title:
- missing required punctuation/diacritics/hyphens/apostrophes
- misspelling
- clearly wrong casing that changes meaning (rare)
-> **Rating**: Unacceptable: Spelling
-> **Comment**: "Misspelled vs official title; punctuation/spelling incorrect."

**Special exception: Incomplete title is NOT spelling**
If suggestion truncates a title by omitting subtitle after colon/dash (but remaining text is correct):
- set `incomplete_title = true`
- continue (do not mark spelling)

**Format clarification (fuzzy but consistent)**
If the "hint" is not a title/name at all (e.g., a full natural-language question or instruction),
treat as **Unacceptable: Spelling** *only if your system uses Spelling as the "format/title-string" bucket*;
otherwise treat as **Unacceptable: Other** ("Not a valid hint/title string").

(Choose one convention and keep it consistent in gold labels.)

---

## 3) Mode detection (deterministic)
### Prefix-mode if ANY:
- query length <= 3 characters, OR
- query has <= 1 token, OR
- last token looks incomplete/fragment

Otherwise: **Intent-mode**

---

## 4) Fuzzy scoring (after gates)
This section is "fuzzy" (graded), but still algorithmizable.

### 4A) Compute comparable candidates (Alternatives)
From **Query IMDb/Google**, identify top candidate completions.
Select **Best Alternative** = strongest candidate **of the same entity type** when possible.

### 4B) Popularity proxy P(x)
For titles (movie/series):
- `P = log10(votes + 1)` (IMDb votes)
For people:
- use STARmeter-style proxy or Google prominence; treat as coarse.
For category/collection hints (e.g., "Disney+ animation"):
- use a **category_mainstream_score** (0-1) based on obviousness + platform relevance.

### 4C) Dominance D (Prefix-mode signal)
Let `P_res` = popularity of suggestion, `P_alt` = popularity of best alternative.
- `D = P_res / (P_res + P_alt)` in [0, 1]

**Alternative exists flag**
- `alternative_exists = (P_alt - P_res) >= alt_margin`

**Low-vote stability rule**
If both votes exist and `max(votes_res, votes_alt) < min_votes_for_dominance`:
- set `dominance_valid = false`
- do **not** use dominance/alternative_exists to downgrade
- log dominance as 0.5 for display only

---

## 5) Label mapping rules (fuzzy -> discrete)
### 5A) If `incomplete_title = true`
Default **Acceptable**
Upgrade only if the truncated form is still the single dominant reference users would interpret correctly:
- Upgrade to **Good** if it is the dominant completion and no strong competing title exists
- Upgrade to **Perfect** only if it is overwhelmingly canonical and unambiguous

Comment reason should be "incomplete title" unless upgraded.

---

### 5B) Prefix-mode mapping (primary question: "is this the obvious completion?")

Score dimensions (0-2 each; human-friendly):
1) **Prefix match strength**
- 2: exact/near-exact completion
- 1: plausible but loose
- 0: unrelated
2) **Dominance / alternatives** (only if dominance_valid)
- 2: dominant (no meaningful alternative)
- 1: mixed (alternatives exist but not clearly better)
- 0: clearly beaten by an alternative (alternative_exists)
3) **Mainstreamness**
- 2: mainstream/highly recognizable
- 1: moderately known
- 0: niche/obscure

Decision (rules override sums):
- If match strength = 0 -> **Unacceptable: Other**
- Else if dominance_valid and alternative_exists -> cap at **Good** (often **Acceptable** if also niche)
- Else:
  - **Perfect**: match strength=2 AND (dominance=2) AND mainstreamness>=1
  - **Good**: match strength>=1 AND mainstreamness>=1, but not top/dominant
  - **Acceptable**: match strength>=1 but weak/ambiguous/niche OR multiple better options

Comment downgrade reasons:
- "alternative exists" when alternative_exists=true and dominance_valid=true
- "niche" when mainstreamness=0
- "ambiguous" when many candidates compete and none dominates

---

### 5C) Intent-mode mapping (primary question: "does this satisfy the user's intent?")

Score dimensions (0-2 each):
1) **Semantic relevance**
- 2: directly matches intent
- 1: related but not best
- 0: unrelated
2) **Type/constraint fit** (movie vs series vs person, etc.)
- 2: fits constraints
- 1: minor mismatch
- 0: wrong type
3) **Expectedness / canonicality**
- 2: top expected answer
- 1: plausible but not top
- 0: surprising/niche

Decision:
- If semantic relevance=0 -> **Unacceptable: Other**
- **Perfect**: (2,2,2) or very strong (>=5 total)
- **Good**: strong but not best (4-5 total)
- **Acceptable**: weak/partial/niche (2-3 total)

Primary downgrade reasons:
- "constraint mismatch" (type)
- "better alternative exists" (canonicality)
- "niche/older" (expectedness low)

---

## 6) Standard edge cases (define once; keep consistent)
- **Type mismatch**: compare dominance within same type unless query cues type.
- **Sequels/spin-offs**: if result is a sequel but query lacks sequel marker, treat as less dominant.
- **Diacritics**: missing diacritics vs official title -> Spelling.
- **Blocked evidence**: if both IMDb and Google are unusable -> Problem: Other (don't guess).
- **Category hints**: evaluate as categories (mainstreamness + relevance), not as titles.

---

## 7) Threshold defaults (configurable)
Suggested starting values:
- `alt_margin = 0.35` (log-vote gap; ~= 2.2x votes)
- `min_votes_for_dominance = 2000`
- `dominant_cutoff_perfect = 0.70`
- `dominant_cutoff_good = 0.60`

---

## 8) Comment examples (1 sentence)
- "Prefix-mode; matches LEGO prefix but title is incomplete (missing subtitle)."
- "Prefix-mode; matches 'sn' prefix but a better canonical alternative exists."
- "Intent-mode; semantically relevant but constraint mismatch (series vs movie)."
- "Cannot validate result due to system/links; evaluation blocked."
- "Misspelled vs official title; punctuation/spelling incorrect."
