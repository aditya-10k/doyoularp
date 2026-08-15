# Frontend

## Stack

Next.js
React
TypeScript

## Visual Direction

Use the supplied home-screen reference image as the primary visual reference.

The design should feel:
- dark
- brutalist
- editorial
- cinematic
- satirical
- premium but hostile

Avoid:
- generic Tailwind SaaS templates
- excessive cards
- colorful startup gradients
- cheerful onboarding
- generic chatbot UI

## Home Page

Hero should communicate:

LARP CHECKER

"Upload a resume. Get brutal honesty."

Supporting copy can be crude.

Example:

"We crawl your links, stalk your GitHub, and check whether you're actually him or just another LinkedIn warrior."

Primary CTA:
Analyze this fraud

Secondary navigation:
- About
- How It Works
- Leaderboard

## Resume Upload

Large drag/drop area.

Accept PDF only.

Show:
- file name
- file size
- validation
- upload state

## Analysis Screen

Show progress stages:

Parsing the resume
Finding the links
Stalking GitHub
Checking project receipts
Extracting claims
Comparing the bullshit
Writing the roast

Use playful copy without hiding actual status.

## Result Screen

Top:

LARP SCORE
XX.X

Then:

ROAST

A large roast block.

Then:

CLAIM BREAKDOWN

Each claim shows:

- original claim
- verdict
- confidence
- evidence
- source
- explanation

## Verdict UI

SUPPORTED
PARTIALLY SUPPORTED
UNVERIFIED
CONTRADICTED

UNVERIFIED must not visually imply "false".

## Evidence

Evidence cards should include:

- source
- URL
- evidence type
- relevant excerpt
- why it matters

## Leaderboard

Leaderboard is NOT visible as a public searchable candidate database.

The public leaderboard is accessed from a completed/generated result.

No auth.

Each entry uses:
- anonymous generated alias
- LARP score
- short roast/claim
- date

Do not show:
- candidate email
- candidate phone
- raw resume
- private analysis data

Example:

#1
Microservice Messiah
97.4 LARP

"Built the future of distributed systems."
Evidence: one Express app.

## Result-to-Leaderboard Access

A completed result contains an opaque result/leaderboard token.

The leaderboard route should only be reachable through a completed analysis result/token.

Because there is no authentication, this is access control by obscurity, not strong security.

Never treat the token as a substitute for real authentication.

## Responsive

Desktop first, but usable on mobile.

## Animation

Use subtle:
- hover transitions
- progress animation
- score reveal
- roast reveal

Do not overanimate.

## Accessibility

Maintain:
- readable contrast
- keyboard navigation
- meaningful labels
- reduced-motion support
