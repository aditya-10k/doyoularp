# Database Schema

Use PostgreSQL.

Use pgvector for embeddings.

## candidates

id
anonymous_alias
name
email
created_at

Do not expose name publicly on the leaderboard.

## analyses

id
candidate_id
status
stage
progress
created_at
completed_at
error

## resumes

id
candidate_id
analysis_id
filename
raw_text
page_count
created_at

## sources

id
candidate_id
analysis_id
type
url
status
metadata
created_at

Types:
github
linkedin
portfolio
project
app_store
play_store
other

## claims

id
analysis_id
resume_id
claim_text
category
section
source_text
page_number
metadata
created_at

## evidence

id
analysis_id
candidate_id
source_id
evidence_type
title
content
url
metadata
created_at

## repositories

id
analysis_id
candidate_id
github_source_id
name
owner
url
description
stars
forks
created_at
updated_at
pushed_at
metadata

## commits

id
repository_id
sha
author
message
committed_at
metadata

## repository_languages

id
repository_id
language
bytes

## contributors

id
repository_id
username
contributions

## embeddings

id
evidence_id
embedding vector

Use pgvector.

## evaluations

id
claim_id
verdict
confidence
reasoning
created_at

## evaluation_evidence

evaluation_id
evidence_id

## leaderboard_entries

id
analysis_id
anonymous_alias
larp_score
roast
created_at

Do not store public leaderboard entries until analysis is completed.

## Evidence Traceability

Every evaluation must reference evidence IDs.

No evidence IDs means:
- evaluation must be UNVERIFIED
- no confident positive claim

## Privacy

No auth means:
- use opaque analysis IDs
- do not use candidate names in public leaderboard entries
- do not expose raw resume text through public endpoints
- do not expose private database IDs unnecessarily
