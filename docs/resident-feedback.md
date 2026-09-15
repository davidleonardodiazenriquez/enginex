# Resident feedback and NPS

The local Feedback module contains 50 fictional English-language resident
interviews for each of the six map properties (300 total). They are generated
from varied positive, neutral and negative property-service scenarios and linked
to occupied generated lease records where available. Existing leases, contracts,
extracted evidence and financial values are preserved. Source metadata identifies
the generated dataset even though presentation screens use ordinary portfolio
language, as requested by the user.

## Calculations and analysis

Each interview stores a separate, explicit 0–10 recommendation response. NPS is
`100 * (promoters - detractors) / scored responses`, where 9–10 are promoters,
7–8 passives and 0–6 detractors. Passives count in the denominator; missing scores
do not. An empty population has no score. Global NPS uses all individual scored
responses, not the unweighted average of property scores. This follows the
[Net Promoter System methodology](https://www.netpromotersystem.com/about/measuring-your-net-promoter-score/).

The user explicitly chose **fast local analysis**, not 300 model calls. The
English-language [VADER analyzer](https://github.com/cjhutto/vaderSentiment)
uses a small documented property vocabulary and contextual phrase handling.
Agent speech and the numeric recommendation response are excluded. Known
property-experience sentences receive sentiment scores; their mean determines
the transcript's label (positive >= 0.05, negative <= -0.05, otherwise neutral).
Unrecognized free-form topics fall back to the resident's full comments.

Maintenance, communication, parking, facilities, cleanliness, renewals, noise,
security and landscaping use a shared phrase catalog. Theme evidence retains
the exact original sentence. Keywords are matched phrases, not unrestricted
semantic topic discovery. Counts are distinct transcripts mentioning a phrase
or a theme/sentiment pair, so a transcript can contribute to multiple themes.
The excerpt is extractive, not an invented model summary. These are heuristic
classifications: sarcasm and complex context can require review.

## App and AI access

- `/assets/<property>/`: NPS KPI and a resident-experience summary linking to the
  property's filtered report.
- `/feedback/`: property comparison, NPS distribution, positive/neutral/negative
  sentiment, positive/negative themes, keywords, date/property/score filters and
  paginated transcripts.
- `/feedback/<id>/`: original interview, explicit recommendation score,
  local-analysis results, supporting quotations and its lease-record link.
- EnginexAI: `feedback_insights` computes summaries/charts over all matching
  records; `query_feedback` returns bounded transcript pages with source links.
  The existing PostgreSQL data layer provides this access without a vector
  database or embeddings. Asking EnginexAI a question still uses its configured
  Azure endpoint, and can supply the requested transcripts to that model.

Example prompt: “Compare NPS across all properties in a bar chart, explain
Gate's main complaints, and link to two supporting transcripts.”

## Populate, analyze and release

These changes are local only. On the next authorized release, install the pinned
requirements, including `vaderSentiment==3.3.2`, and run against the explicitly
selected destination database:

```sh
python manage.py migrate
python manage.py populate_feedback
python manage.py analyze_feedback
```

`core.0004_resident_feedback` only adds the feedback table. The six assets must
already exist. Population is additive and preserves existing references and
edited interviews. Analysis is repeatable: it skips completed, unchanged
transcripts with the same analysis version and recalculates when their text or
the analyzer version changes. `--retry-failed` retries failed analyses.

Administrators can add or edit feedback in Django admin. Transcript edits mark
their analysis pending; run `analyze_feedback` afterward. Analysis currently runs
through that command, not a scheduled daemon or a model-powered pipeline.
Do not rerun the destructive legacy `seed_demo` command as a deployment step.
Do not copy the local database over Azure to deliver this module.

Initial recommendation results: Al Rayyana +44, Gate +6, Arc +30, The Bridges II
+22, Sas Al Nakhl +36, Eastern Mangroves +52; global +31.7 (159 promoters,
77 passives, 64 detractors). These describe the generated responses, not observed
resident satisfaction. NPS is independent of the local sentiment labels.
