# Resume Pipeline

## Goal

Turn a resume PDF into:

1. extracted text
2. discovered links
3. structured candidate information
4. atomic claims

## PDF Extraction

The parser must inspect both:

- PDF text layer
- PDF hyperlink annotations

A visible "GitHub" icon may have an embedded hyperlink even when "github.com" never appears in the text.

## URL Extraction

Extract from:
- hyperlink annotations
- visible text

Normalize:
- http/https
- trailing slashes
- www
- common URL formatting differences

Examples:

github.com/user
https://github.com/user/
https://www.github.com/user

→

https://github.com/user

## GitHub URL Validation

A URL is a GitHub profile only if it matches the expected GitHub URL structure.

Do not accidentally treat:
https://github.com/user/repo
as a profile URL.

Support repository links too, and infer the owner/repo when appropriate.

## Candidate Fields

Extract where available:

- name
- email
- phone
- education
- experience
- projects
- skills
- achievements

## Claim Extraction

Claims must be atomic.

Bad:
"Built a scalable Flutter RAG app with 10k users and reduced latency 80%."

Better:

1. Built a Flutter application.
2. Application used RAG.
3. Application had 10,000+ users.
4. Reduced latency by 80%.

## Claim Metadata

{
  "claim_text": "...",
  "category": "project",
  "section": "projects",
  "technologies": ["Flutter"],
  "related_project": "TravelApp",
  "source_text": "original resume sentence"
}

## Traceability

Every claim must point back to source text/page information.

This allows the result UI to show what the candidate actually claimed.

## No Hallucination

If the parser cannot determine a field, return null/unknown.

Never invent missing resume details.
