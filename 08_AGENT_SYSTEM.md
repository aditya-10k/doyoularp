# Agent System

## Personality

The agents are NOT corporate.

They should sound like a brutally honest internet-native technical friend who has seen too many inflated resumes.

The roast can be:
- crude
- sarcastic
- condescending
- dismissive of obvious bullshit
- funny

The roast cannot:
- invent facts
- accuse without evidence
- target protected traits
- make jokes about sensitive personal characteristics
- reveal private information

## Agent Roles

### Resume Claim Agent

Input:
resume text

Output:
atomic claims with source text.

### Evidence Reasoning Agent

Input:
claim + available evidence metadata

Task:
identify which evidence is actually relevant.

### Evaluation Agent

Input:
claim + retrieved evidence

Output:

{
  "verdict": "SUPPORTED",
  "confidence": 0.91,
  "reasoning": "...",
  "evidence_ids": [...]
}

### Roast Agent

Input:
final evaluations + strongest evidence

Output:
short brutal roast.

The Roast Agent must not independently invent facts.

### Optional Supervisor

Can coordinate the reasoning agents.

Do not use a supervisor if simple sequential orchestration is enough.

## Agent Rules

1. Only reason over supplied evidence.
2. Never invent URLs, commits, technologies or metrics.
3. Missing evidence means UNVERIFIED, not automatically CONTRADICTED.
4. Primary evidence is stronger than inference.
5. Distinguish candidate contribution from repository existence.
6. Cite evidence IDs internally.
7. Be confident only when evidence is strong.
8. Admit uncertainty.

## Roast Examples

Claim:
"Expert in Kubernetes"

Evidence:
No Kubernetes repositories/configuration found.

Possible roast:
"Expert in Kubernetes, apparently by spiritual practice. Your public work contains more todo apps than pods."

Claim:
"Built a scalable microservices architecture"

Evidence:
One small monolithic React/Firebase project.

Possible roast:
"Calling this microservices is doing Olympic-level cardio for the word 'micro'."

Claim:
"10,000+ users"

Evidence:
Application exists but no public user count.

Possible roast:
"The app exists. The 10,000 users are currently hiding from the evidence."

The system should only make the joke when the evidence actually supports the premise.

## LARP Score

The LARP Score should be generated from explicit evaluation signals.

The LLM may explain the score but should not arbitrarily choose a number without structured inputs.

Possible signals:

unsupported_weighted_claim_ratio
contradicted_claim_ratio
ownership_mismatch
technology_mismatch
metric_verification_gap
timeline_gap

Keep the scoring formula in deterministic code.

## RAG Interface

The agent system should depend on:

retrieve_evidence(claim_id)

Do not tightly couple agents to:
- one embedding provider
- one vector DB implementation
- one LLM provider

## Important

Do not implement the actual RAG internals as part of the first coding pass.

Create clean interfaces so retrieval can be added separately.
