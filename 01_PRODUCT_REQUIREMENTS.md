# Product Requirements

## Primary User

A person who wants a brutally honest sanity check of a resume.

The app can also be useful to recruiters/hiring managers, but the public-facing personality is aimed at exposing resume larp.

## Input

Required:
- one PDF resume

No authentication.

Optional manual URLs may be supported later, but the first flow should discover links from the PDF automatically.

## Resume Link Discovery

Extract both:

1. visible URLs in extracted PDF text
2. embedded PDF hyperlink annotations

This is important because a resume may display:

GitHub

while the PDF internally links to:

https://github.com/username

Also detect links hidden behind:

- GitHub icons
- LinkedIn icons
- portfolio icons
- project titles

## URL Categories

Classify discovered URLs as:

- github
- linkedin
- portfolio
- project
- app_store
- play_store
- other

## MVP Sources

Strong priority:
- GitHub
- portfolio websites
- public project websites
- public app/project pages

LinkedIn is NOT an MVP scraping target.

Do not build the system around LinkedIn scraping.

## Claim Extraction

Convert resume statements into atomic claims.

Example:

"Built a Flutter travel application used by 10,000+ users."

Becomes:

1. Built a travel application.
2. Used Flutter.
3. Had 10,000+ users.

Each claim must retain the original resume text that produced it.

## Verdicts

SUPPORTED
- strong evidence directly supports the claim

PARTIALLY_SUPPORTED
- some parts are supported, but important details are not verified

UNVERIFIED
- insufficient public evidence

CONTRADICTED
- reliable public evidence directly conflicts with the claim

Important:
Lack of evidence ≠ contradiction.

## Evidence Priority

Prefer evidence in roughly this order:

1. primary project/repository
2. source-controlled code/configuration
3. official app/project page
4. official portfolio
5. public third-party references
6. weak/inferential signals

## LARP Score

Create an overall satirical "LARP Score" from evidence.

The score is not a factual probability that somebody is lying.

It is a product metric representing how much resume hype is unsupported by public evidence.

Use transparent sub-signals such as:

- unsupported claim ratio
- exaggerated metrics
- project ownership mismatch
- technology mismatch
- weak evidence for major claims
- timeline inconsistencies
- contribution mismatch

Do not claim the score is scientifically validated.

## Roast Generation

Every completed analysis should generate:

- short verdict
- overall roast
- strongest supported claim
- weakest/unverified claim
- funniest/most obvious mismatch when one exists

Example:

"Your GitHub has 14 repos and somehow none of them contain the 8 technologies you called yourself an expert in. Incredible."

## Roast Intensity

Use levels:

0 = factual only
1 = light sarcasm
2 = blunt
3 = brutal
4 = nuclear

Default:
3

Only go to 4 when evidence clearly supports a strong mismatch.

Do not roast protected traits, appearance, health, sexuality, religion, ethnicity, or other sensitive characteristics.

## Result Page

Show:

- candidate alias
- LARP score
- summary
- claim cards
- evidence
- roast
- source links
- leaderboard entry/status

## Leaderboard

There is no auth.

The leaderboard is accessible from a completed/generated result.

Do not expose full candidate names by default.

Use an anonymous generated alias.

Example:

#1 "Microservice Messiah"
LARP Score: 96.8

The leaderboard should not become an open candidate-search database.

## Errors

If a source cannot be accessed:
- mark it unavailable
- continue the analysis
- never fabricate content

If GitHub is missing:
- analyze other sources
- explain that GitHub evidence was unavailable

If no meaningful evidence exists:
- produce an unverified result rather than a fabricated roast.
