import json
import logging
import re
from typing import Any, Dict, List, Optional
from backend.app.agents.groq_client import GroqClient, GroqRateLimitError
from backend.app.rag.evidence_retriever import RetrievedEvidenceChunk

logger = logging.getLogger(__name__)

EVALUATION_SYSTEM_PROMPT = """You are the Evidence Evaluation Agent for doyoularp.
Your responsibility is to strictly, objectively, and skeptically judge whether a resume claim is substantiated by public receipts.

STRICT VALIDATION HIERARCHY:

FOR PROJECT CLAIMS:
MANDATORY BULLSHIT & OVERPLAYED PROJECT CONTRADICTIONS:
- Tabular Dataset Regression / Boosting (Automatic CONTRADICTED):
  If a project is merely running regression (linear/logistic), decision trees, random forest, or boosting (XGBoost, LightGBM, CatBoost) on a static tabular dataset or CSV (e.g. churn, sales, housing prices, titanic, iris, spam, credit risk, fraud, diabetes):
  ALWAYS assign CONTRADICTED! Whatever enterprise or predictive claims are made about it, it is a LARP.
  Reasoning: "Bullshit project detected: applying basic regression or boosting to a static tabular dataset does not constitute production AI or scalable engineering architecture; routine tabular notebook scripting overplayed as an engineering deliverable."

- Overplayed Toy / Tutorial Projects (Automatic CONTRADICTED):
  If the project is fundamentally a basic toy, utility, or tutorial app (e.g. To-Do list, Notes app, Calculator, Weather app, Rock-Paper-Scissors, Tic-Tac-Toe, Counter, URL shortener, Flashcard/Quiz app) BUT the resume claim uses excessive enterprise buzzwords (e.g. 'high-throughput', 'scalable distributed architecture', 'enterprise-grade', 'orchestrated', 'fault-tolerant microservices', 'cutting-edge system', 'production-scale'):
  ALWAYS assign CONTRADICTED!
  Reasoning: "Overplayed toy project: basic [app type] application excessively inflated with enterprise architecture buzzwords; routine tutorial code overplayed as production distributed infrastructure."

1. Direct GitHub Repo Link Validation:
   - If a GitHub repo link is attached to the claim, validate directly against THAT specific repository's README, manifests, files, and commit history.
   - CONTRADICTED:
     * Candidate authored 0 commits in the attached repository (someone else's repo, stolen attribution).
     * The claimed tech stack is completely absent or refuted by the repository (e.g. pure static HTML when claiming PyTorch/FastAPI backend).
     * The attached repo link is broken / 404 / dead.
     * Toy mock repo claiming massive production scale.
   - SUPPORTED: Repo README, manifests, code, and candidate commits substantiate the claimed deliverable and stack.
   - PARTIALLY_SUPPORTED: Core project and stack are confirmed in the repo, but unprovable runtime metrics (e.g. 10,000+ users, 80% faster, saved $50k) cannot be proven from code alone.

2. Project Name Matching (When No Direct Repo Link is Attached):
   - Search candidate repos by project name similarity or domain stem (e.g. 'ElderCare' matches 'Elderly_AI', 'Trade Reconciliation' matches 'trades_recon', 'Nexport' matches 'GitHappens' or 'NexPort', 'Anvaya AI' matches 'ANVAYA').
   - If a matching repository is found: validate against its README, manifests, code, and commit history. Check for 0-commit contradictions.

3. Checking Other Repositories for Tech Stack Corroboration:
   - If no repository exists for this specific project name:
     Check the candidate's other repositories and global tech stack inventory.
     * If candidate actively demonstrates the claimed technologies across other personal repositories:
       Assign PARTIALLY_SUPPORTED (skills verified in other repos, specific project instance closed-source).
     * If candidate has ZERO repositories demonstrating any of the claimed stack:
       Assign UNVERIFIED (reasoning: "No repository or manifest demonstrates usage of [technologies]").

FOR TECHNICAL SKILL CLAIMS (Single match != Proficient):
- A single repository mention or incidental manifest package is NOT proof of proficiency!
- If a technology appears in only ONE repository or as an incidental manifest package with minimal candidate commits (< 10 commits):
  Assign "PARTIALLY_SUPPORTED" with reasoning: "Single-repository match in [Repo] (matched: [tech]). Demonstrates introductory exposure, but lacks multi-project depth or substantial commit volume to corroborate full proficiency."
- If a technology appears across MULTIPLE candidate repositories (>= 2 repos) or in a project where candidate authored substantial commits (>= 10 commits):
  Assign "SUPPORTED" with reasoning citing the multi-repository usage or commit volume.
- If a technology appears nowhere in public receipts:
  Assign "UNVERIFIED" with reasoning: "No public repository or manifest demonstrates usage of [tech]."

FOR WORK EXPERIENCE CLAIMS:
1. Proof of Work / Link Attached:
   - If a link (Play Store, live app, web demo, certificate, Drive proof, GitHub repo) is attached:
     * Valid live proof confirming the work -> SUPPORTED.
     * Broken / 404 / unrelated / disproven -> CONTRADICTED.
2. No Link Attached:
   - For proprietary internal employer/internship experience where no link is attached:
     * If candidate demonstrates underlying technical skills in personal repos -> PARTIALLY_SUPPORTED.
     * If candidate demonstrates no receipts for claimed stack -> UNVERIFIED.

Confidence MUST be a valid JSON float number between 0.1 and 1.0 (e.g. 0.85). Do NOT write numbers as words.
NO EMOJIS anywhere in the output.

Return ONLY a JSON object:
{
  "verdict": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNVERIFIED" | "CONTRADICTED",
  "confidence": 0.85,
  "reasoning": "Direct citation of repository/manifest or explanation of missing receipts or contradiction.",
  "evidence_ids": ["ev_1"]
}
"""


BATCH_EVALUATION_SYSTEM_PROMPT = """You are the Evidence Evaluation Agent for doyoularp.
Evaluate the provided list of resume claims against the candidate's public repository and webpage evidence.
Strictly apply this validation hierarchy to each claim:

STRICT VALIDATION HIERARCHY:

FOR PROJECT CLAIMS:
MANDATORY BULLSHIT & OVERPLAYED PROJECT CONTRADICTIONS:
- Tabular Dataset Regression / Boosting (Automatic CONTRADICTED):
  If a project is merely running regression (linear/logistic), decision trees, random forest, or boosting (XGBoost, LightGBM, CatBoost) on a static tabular dataset or CSV (e.g. churn, sales, housing prices, titanic, iris, spam, credit risk, fraud, diabetes):
  ALWAYS assign CONTRADICTED! Whatever enterprise or high-scale claims are made about it, it is a LARP.
  Reasoning: "Bullshit project detected: applying basic regression or boosting to a static tabular dataset does not constitute production AI or scalable engineering architecture; routine tabular notebook scripting overplayed as an engineering deliverable."

- Overplayed Toy / Tutorial Projects (Automatic CONTRADICTED):
  If the project is fundamentally a basic toy, utility, or tutorial app (e.g. To-Do list, Notes app, Calculator, Weather app, Rock-Paper-Scissors, Tic-Tac-Toe, Counter, URL shortener, Flashcard/Quiz app) BUT the resume claim uses excessive enterprise buzzwords (e.g. 'high-throughput', 'scalable distributed architecture', 'enterprise-grade', 'orchestrated', 'fault-tolerant microservices', 'cutting-edge system', 'production-scale'):
  ALWAYS assign CONTRADICTED!
  Reasoning: "Overplayed toy project: basic [app type] application excessively inflated with enterprise architecture buzzwords; routine tutorial code overplayed as production distributed infrastructure."

1. Direct GitHub Repo Link Validation:
   - If an attached GitHub repo URL is provided, validate directly against THAT specific repository's README, manifests, files, and commit history.
   - CONTRADICTED:
     * Candidate authored 0 commits in the attached repository (candidate_commits: 0, someone else's repo, attribution theft).
     * Claimed tech stack is completely refuted/absent in the repo (e.g. pure static HTML when claiming PyTorch/FastAPI backend).
     * Attached repo link is broken / 404 / dead.
   - SUPPORTED: Repo README, manifests, code, and candidate commits substantiate the deliverable and stack.
   - PARTIALLY_SUPPORTED: Core project and stack confirmed in repo, but unprovable private metrics (e.g. 10,000+ users, 80% faster, <5s latency) cannot be verified from code alone.

2. Project Name Matching (When No Direct Repo Link is Attached):
   - Match repositories by project name similarity or domain stem (e.g. 'ElderCare AI Platform' matches 'Elderly_AI', 'Trade Reconciliation' matches 'trades_recon', 'Nexport' matches 'GitHappens' or 'NexPort', 'Anvaya AI' matches 'ANVAYA').
   - If a matching repository exists: validate against its code, manifests, and commit history. Check for contradictions.

3. Checking Other Repositories for Tech Stack Corroboration:
   - If no repository exists for this specific project name:
     Check candidate's other repositories and global tech stack inventory.
     * If candidate demonstrates the claimed technologies across other personal repositories:
       Assign PARTIALLY_SUPPORTED (skills verified in other repos, specific project instance closed-source).
     * If candidate has ZERO repositories demonstrating the claimed stack:
       Assign UNVERIFIED (reasoning: "No public repository or manifest demonstrates usage of [technologies]").

FOR TECHNICAL SKILL CLAIMS (Single match != Proficient):
- A single repository mention or incidental manifest package is NOT proof of proficiency!
- If a technology appears in only ONE repository or as an incidental manifest package with minimal candidate commits (< 10 commits):
  Assign "PARTIALLY_SUPPORTED" with reasoning: "Single-repository match in [Repo] (matched: [tech]). Demonstrates introductory exposure, but lacks multi-project depth or substantial commit volume to corroborate full proficiency."
- If a technology appears across MULTIPLE candidate repositories (>= 2 repos) or in a project where candidate authored substantial commits (>= 10 commits):
  Assign "SUPPORTED" with reasoning citing the multi-repository usage or commit volume.
- If a technology appears nowhere in public receipts:
  Assign "UNVERIFIED" with reasoning: "No public repository or manifest demonstrates usage of [tech]."

FOR WORK EXPERIENCE CLAIMS:
1. Proof of Work / Link Attached:
   - If a link (Play Store, live app, web demo, certificate, Drive proof, GitHub repo) is attached:
     * Valid live proof confirming the work -> SUPPORTED.
     * Broken / 404 / unrelated / disproven -> CONTRADICTED.
2. No Link Attached:
   - For proprietary internal employer/internship experience where no link is attached:
     * If candidate demonstrates underlying technical skills in personal repos -> PARTIALLY_SUPPORTED ("Proprietary company project; candidate demonstrates core stack in public receipts.").
     * If candidate demonstrates no receipts for claimed stack -> UNVERIFIED.

Confidence MUST be a valid JSON float number between 0.1 and 1.0 (e.g. 0.85). Do NOT write numbers as words.
NO EMOJIS anywhere in the output.

Return ONLY a JSON object with this exact structure:
{
  "evaluations": [
    {
      "claim_id": "0",
      "verdict": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNVERIFIED" | "CONTRADICTED",
      "confidence": 0.85,
      "reasoning": "Detailed justification citing receipts, commit authorship, corporate context, or contradiction.",
      "evidence_ids": ["ev_id"]
    }
  ]
}
"""


TABULAR_DATASET_PATTERNS = [
    r'\b(?:churn|customer\s+churn|attrition)\b',
    r'\btitanic\b',
    r'\biris\b',
    r'\b(?:pizza\s+sales|sales\s+(?:data|forecast|prediction|records?))\b',
    r'\b(?:housing|house\s+price|boston\s+housing)\b',
    r'\b(?:spam|sms\s+spam)\b',
    r'\b(?:credit\s+risk|credit\s+card\s+fraud|loan\s+prediction|fraud\s+detection)\b',
    r'\b(?:diabetes|heart\s+disease)\b',
    r'\b(?:dataset|datasets|tabular|\.csv|csv\s+file|kaggle)\b',
]

BOOSTING_REGRESSION_PATTERNS = [
    r'\bxgboost\b',
    r'\blightgbm\b',
    r'\bcatboost\b',
    r'\badaboost\b',
    r'\bgradient\s*boost\w*\b',
    r'\blinear\s*regression\b',
    r'\blogistic\s*regression\b',
    r'\brandom\s*forest\w*\b',
    r'\bdecision\s*tree\w*\b',
    r'\bsvm\b|\bsupport\s*vector\b',
    r'\bnaive\s*bayes\b',
    r'\bscikit[-_]?learn\b|\bsklearn\b',
    r'\b(?:gradient\s*)?boosting\b',
    r'\bregression\b(?!\s+test)',
]

TOY_APP_PATTERNS = [
    (r'\bto-?do(?:\s+list|\s+app)?\b', "To-Do"),
    (r'\bnotes?(?:\s+app|\s+taking|\s+manager)?\b|\bnotepad\b', "Notes"),
    (r'\bcalculator(?:\s+app)?\b', "Calculator"),
    (r'\bweather(?:\s+app|\s+forecast)?\b', "Weather"),
    (r'\brock[- ]paper[- ]scissors?\b|\brps\b', "Rock-Paper-Scissors"),
    (r'\btic[- ]tac[- ]toe\b', "Tic-Tac-Toe"),
    (r'\bcounter(?:\s+app)?\b|\bstopwatch\b|\btimer\b', "Counter/Stopwatch"),
    (r'\burl\s+shortener\b', "URL Shortener"),
    (r'\bcurrency\s+converter\b', "Currency Converter"),
    (r'\bquiz(?:\s+app)?\b|\bflashcards?\b', "Quiz"),
]

OVERPLAYED_HYPE_PATTERNS = [
    r'high[- ]throughput',
    r'\bdistributed\b',
    r'\borchestrat(?:ed|ing|ion)\b',
    r'enterprise[- ]grade|\benterprise\b',
    r'mission[- ]critical',
    r'fault[- ]tolerant|fault[- ]tolerance',
    r'scalable\s+microservices?|\bmicroservices?\b',
    r'production[- ]grade|production[- ]scale',
    r'massive\s+scale|hyper[- ]scale',
    r'cutting[- ]edge',
    r'state[- ]of[- ]the[- ]art',
    r'stream\s+processing',
    r'event[- ]driven\s+architecture',
]

KNOWN_TECH_KEYWORDS = {
    "python", "javascript", "typescript", "dart", "java", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "html", "css",
    "react", "nextjs", "next.js", "vue", "angular", "svelte", "flutter",
    "django", "flask", "fastapi", "express", "node", "nodejs", "spring", "spring boot",
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "firebase", "postgresql",
    "postgres", "mysql", "mongodb", "redis", "sqlite", "elasticsearch", "kafka",
    "rabbitmq", "graphql", "tailwind", "bootstrap", "pytorch", "tensorflow", "keras",
    "scikit-learn", "sklearn", "pandas", "numpy", "opencv"
}


def check_bullshit_project_contradiction(
    claim_text: str,
    retrieved_chunks: Optional[List[RetrievedEvidenceChunk]] = None,
    category: str = "project",
    claim_meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Detects bullshit/overplayed projects:
    1. Tabular dataset regression or boosting projects (e.g. XGBoost/regression on churn, sales, housing, titanic, iris, spam, CSV).
       Whatever is claimed about it, it is a LARP -> CONTRADICTED.
    2. Overplayed toy / tutorial apps (To-Do, Notes, Calculator, Weather, Rock-Paper-Scissors, etc.)
       inflated with enterprise architecture buzzwords -> CONTRADICTED.
    """
    if category == "skill":
        return None

    retrieved_chunks = retrieved_chunks or []
    claim_lower = claim_text.lower()
    claim_lower_no_qa = re.sub(r'\bregression\s+test\w*\b', '', claim_lower)

    claim_meta = claim_meta or {}
    project_name = (claim_meta.get("project_name") or "").lower()
    attached_url = (claim_meta.get("attached_url") or "").lower()

    repo_chunks = [c for c in retrieved_chunks if c.evidence_type != "github_tech_stack"]

    # 1. TABULAR DATASET BOOSTING/REGRESSION CHECK
    algo_in_claim = any(re.search(p, claim_lower_no_qa) for p in BOOSTING_REGRESSION_PATTERNS)
    dataset_in_claim = any(re.search(p, claim_lower_no_qa) for p in TABULAR_DATASET_PATTERNS)

    is_tabular_bullshit = False
    matching_ev_id = None

    # A) Direct claim pairs boosting/regression with tabular dataset (e.g. XGBoost on customer churn)
    if algo_in_claim and dataset_in_claim:
        is_tabular_bullshit = True
    else:
        # B) Claim claims an ML/AI/Predictive project, AND the repo evidence for it is a static CSV + basic algo
        ml_patterns = [r'\b(?:ai|ml|machine\s+learning|predictive|intelligence|deep\s+learning|neural|classifier|classification|forecast\w*|trained|training|model)\b']
        claims_ml = any(re.search(p, claim_lower_no_qa) for p in ml_patterns) or algo_in_claim
        if claims_ml:
            for chunk in repo_chunks:
                c_text = f"{chunk.title} {chunk.content}".lower()
                c_text_no_qa = re.sub(r'\bregression\s+test\w*\b', '', c_text)
                chunk_algo = any(re.search(p, c_text_no_qa) for p in BOOSTING_REGRESSION_PATTERNS)
                chunk_dataset = any(re.search(p, c_text_no_qa) for p in TABULAR_DATASET_PATTERNS)
                if chunk_algo and chunk_dataset:
                    claim_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', re.sub(r'[_\\-]', ' ', claim_lower_no_qa)))
                    chunk_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', re.sub(r'[_\\-]', ' ', c_text_no_qa)))
                    fluff = {'with', 'from', 'using', 'based', 'data', 'built', 'developed', 'pipeline', 'system', 'learning'}
                    meaningful_claim_words = claim_words - fluff
                    if meaningful_claim_words & chunk_words:
                        is_tabular_bullshit = True
                        matching_ev_id = chunk.evidence_id
                        break

    if is_tabular_bullshit:
        ev_ids = [matching_ev_id] if matching_ev_id else ([repo_chunks[0].evidence_id] if repo_chunks else [])
        return {
            "verdict": "CONTRADICTED",
            "confidence": 0.95,
            "reasoning": (
                "Bullshit project detected: applying basic regression, decision trees, or boosting algorithms "
                "to a static tabular dataset (e.g. churn/sales/titanic/iris/CSV) does not constitute production AI or scalable engineering architecture; "
                "routine tabular notebook scripting overplayed as an engineering deliverable."
            ),
            "evidence_ids": ev_ids,
        }

    # 2. OVERPLAYED TOY / TUTORIAL APP CHECK
    matched_toy = None
    for pattern, name in TOY_APP_PATTERNS:
        # Match only on claim, project name, or attached repo url
        if (
            re.search(pattern, claim_lower)
            or re.search(pattern, project_name)
            or (attached_url and re.search(pattern, attached_url))
        ):
            matched_toy = name
            break

    if matched_toy:
        matched_hype = [
            p for p in OVERPLAYED_HYPE_PATTERNS
            if re.search(p, claim_lower)
        ]
        if matched_hype:
            ev_ids = [repo_chunks[0].evidence_id] if repo_chunks else []
            clean_hype = [re.sub(r'\\b|[?]|(?:\(\?:.*?\))', '', h).strip() for h in matched_hype[:2]]
            return {
                "verdict": "CONTRADICTED",
                "confidence": 0.94,
                "reasoning": (
                    f"Overplayed toy project: basic {matched_toy} application excessively inflated with enterprise "
                    f"architecture buzzwords ({', '.join(clean_hype)}); routine tutorial code overplayed as production distributed infrastructure."
                ),
                "evidence_ids": ev_ids,
            }

    return None


class EvaluationAgent:
    def __init__(self, groq_client: Optional[GroqClient] = None):
        self.groq = groq_client or GroqClient()

    def _rule_based_fallback(
        self,
        claim_text: str,
        retrieved_chunks: List[RetrievedEvidenceChunk],
        category: str = "project",
        section: str = "project",
        claim_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Strict deterministic fallback following the 4-step validation hierarchy."""
        # Check for bullshit / overplayed project contradiction FIRST
        bullshit_check = check_bullshit_project_contradiction(
            claim_text=claim_text,
            retrieved_chunks=retrieved_chunks,
            category=category,
            claim_meta=claim_meta,
        )
        if bullshit_check:
            return bullshit_check

        if not retrieved_chunks:
            return {
                "verdict": "UNVERIFIED",
                "confidence": 0.8,
                "reasoning": "No public repositories or proof of work links were found to substantiate this claim.",
                "evidence_ids": [],
            }

        claim_meta = claim_meta or {}
        attached_url = claim_meta.get("attached_url")
        project_name = claim_meta.get("project_name")
        claim_lower = claim_text.lower()

        fluff_words = {
            "developed", "built", "created", "implemented", "used", "using", "with",
            "based", "application", "app", "project", "system", "service", "via",
            "from", "and", "the", "for", "across", "enabled", "faster", "scalable",
            "worked", "employment", "period", "present", "bachelor", "technology",
            "proficient", "skills", "skill", "technologies", "experienced", "knowledge",
            "engineered", "architected", "platform", "solution", "high", "performance",
            "in", "at", "to", "on", "of", "by", "as", "an", "a", "or", "is", "are",
            "was", "were", "into", "over", "under", "software", "code", "tools", "data"
        }
        tokens = re.findall(r'\b[a-zA-Z0-9_\-\.+#]{2,}\b', claim_lower)
        substantive_tokens = [t for t in tokens if t not in fluff_words]

        # STEP 0: Contradiction Checks Across Chunks
        # A. Check for 0-commit attribution theft in attached or matched repos
        for chunk in retrieved_chunks:
            ev_meta = chunk.meta or {}
            cand_commits = ev_meta.get("candidate_commit_count")
            total_commits = ev_meta.get("total_commit_count", 0)
            if cand_commits is not None and total_commits > 5 and cand_commits == 0 and any(
                w in claim_lower for w in ["built", "created", "architected", "developed", "engineered", "implemented", "authored"]
            ):
                return {
                    "verdict": "CONTRADICTED",
                    "confidence": 0.95,
                    "reasoning": f"Repository '{chunk.title}' has {total_commits} commits, but candidate authored 0 of them.",
                    "evidence_ids": [chunk.evidence_id],
                }

        # B. Check for broken/404 proof links
        for chunk in retrieved_chunks:
            ev_meta = chunk.meta or {}
            c_text = f"{chunk.title} {chunk.content}".lower()
            if "404 not found" in c_text or ev_meta.get("status") == "failed" or "failed to fetch" in c_text:
                if attached_url and (attached_url in (chunk.url or "") or (chunk.url and chunk.url in attached_url)):
                    return {
                        "verdict": "CONTRADICTED",
                        "confidence": 0.92,
                        "reasoning": f"Attached proof link '{attached_url}' is inaccessible or returned 404 Not Found.",
                        "evidence_ids": [chunk.evidence_id],
                    }

        # C. Domain mismatch guard (e.g. SQL editor vs cricket tournament app)
        combined_all = " ".join(f"{c.title} {c.content}".lower() for c in retrieved_chunks)
        if "sql" in substantive_tokens and not re.search(r'\bsql\b', combined_all):
            return {
                "verdict": "UNVERIFIED",
                "confidence": 0.85,
                "reasoning": "No SQL implementation discovered in repository evidence. Evidence does not substantiate an SQL tool.",
                "evidence_ids": [],
            }

        # STEP 1: For Technical Skill Claims (Single match != Proficient)
        if category == "skill":
            clean_substantive = [
                t for t in substantive_tokens
                if t not in ("languages", "frameworks", "databases", "libraries", "tools", "skills", "proficient")
            ]
            if not clean_substantive:
                clean_substantive = substantive_tokens

            matching_chunks = []
            matching_repo_names = set()
            total_candidate_commits = 0
            tech_repo_counts = {}
            tech_commits = {}

            # Read occurrence counts from tech stack inventory metadata if present
            for chunk in retrieved_chunks:
                if chunk.evidence_type == "github_tech_stack" and isinstance(chunk.meta, dict):
                    tech_repo_counts = chunk.meta.get("tech_repo_counts", {})
                    tech_commits = chunk.meta.get("tech_commits", {})

            for chunk in retrieved_chunks:
                c_meta = chunk.meta if isinstance(chunk.meta, dict) else {}
                c_text = f"{chunk.title} {chunk.content}".lower()
                c_matched = []
                for t in clean_substantive:
                    # Single-letter safety (e.g. 'c'):
                    if len(t) == 1:
                        langs_dict = c_meta.get("languages", {}) if isinstance(c_meta.get("languages"), dict) else {}
                        langs_list = [str(k).lower() for k in langs_dict.keys()]
                        if t in langs_list or re.search(r'\b(?:language|languages|lang)\b[^\n]*\b' + re.escape(t) + r'\b', c_text):
                            c_matched.append(t)
                    else:
                        if re.search(r'(?<![a-zA-Z0-9])' + re.escape(t) + r'(?![a-zA-Z0-9])', c_text):
                            c_matched.append(t)

                if c_matched:
                    matching_chunks.append(chunk)
                    r_name = c_meta.get("repo") or chunk.title
                    if chunk.evidence_type != "github_tech_stack":
                        matching_repo_names.add(r_name)
                    cand_c = c_meta.get("candidate_commit_count", 0)
                    total_candidate_commits += cand_c

            if not matching_chunks:
                return {
                    "verdict": "UNVERIFIED",
                    "confidence": 0.85,
                    "reasoning": f"No public repository or manifest demonstrates usage of {', '.join(clean_substantive) if clean_substantive else claim_text}.",
                    "evidence_ids": [],
                }

            # Check occurrences across tech stack inventory metadata
            effective_repo_count = len(matching_repo_names)
            effective_commits = total_candidate_commits
            for t in clean_substantive:
                t_low = t.lower()
                if t_low in tech_repo_counts:
                    effective_repo_count = max(effective_repo_count, tech_repo_counts[t_low])
                if t_low in tech_commits:
                    effective_commits = max(effective_commits, tech_commits[t_low])

            # PROFICIENCY LOGIC:
            # Single match in only 1 repository with minimal commits (< 10) is PARTIALLY_SUPPORTED!
            # Full SUPPORTED requires multi-project track record (>= 2 repos) OR substantial candidate commits (>= 10 commits).
            if effective_repo_count >= 2 or effective_commits >= 10:
                matched_label = ', '.join(clean_substantive[:3])
                repos_str = f" across {effective_repo_count} repositories" if effective_repo_count >= 2 else f" with {effective_commits} candidate commits"
                return {
                    "verdict": "SUPPORTED",
                    "confidence": 0.85,
                    "reasoning": f"Proficiency substantiated{repos_str} in public receipts (matched: {matched_label}).",
                    "evidence_ids": [c.evidence_id for c in matching_chunks[:2]],
                }
            else:
                matched_label = ', '.join(clean_substantive[:3])
                first_title = matching_chunks[0].title
                return {
                    "verdict": "PARTIALLY_SUPPORTED",
                    "confidence": 0.80,
                    "reasoning": f"Single-repository match in '{first_title}' (matched: {matched_label}). Demonstrates introductory exposure, but lacks multi-project track record or substantial commit volume (>=10 commits) to corroborate full proficiency.",
                    "evidence_ids": [matching_chunks[0].evidence_id],
                }

        # Private metric indicator
        has_private_metrics = any(
            re.search(pat, claim_text, re.IGNORECASE)
            for pat in [r'\b\d+%\b', r'\b\d+\+\s*users\b', r'\breduced\b', r'\bimproved\b', r'\bteam of\b', r'<\s*\d+']
        )

        # STEP 2: Projects / Work Experience with Direct Attached URL
        if attached_url:
            for chunk in retrieved_chunks:
                if chunk.url and (attached_url in chunk.url or chunk.url in attached_url):
                    # Check tech stack contradiction on attached repo
                    c_text = f"{chunk.title} {chunk.content}".lower()
                    # Only check recognized tech frameworks and languages, never general English words
                    claimed_techs = [
                        t for t in substantive_tokens
                        if t.lower() in KNOWN_TECH_KEYWORDS
                    ]
                    if len(claimed_techs) >= 2:
                        matched_stack = [
                            t for t in claimed_techs
                            if re.search(r'(?<![a-zA-Z0-9])' + re.escape(t) + r'(?![a-zA-Z0-9])', c_text)
                        ]
                        if not matched_stack:
                            return {
                                "verdict": "CONTRADICTED",
                                "confidence": 0.90,
                                "reasoning": f"Attached repository '{chunk.title}' contains none of the claimed technical stack ({', '.join(claimed_techs[:3])}).",
                                "evidence_ids": [chunk.evidence_id],
                            }
                    verdict = "PARTIALLY_SUPPORTED" if has_private_metrics else "SUPPORTED"
                    return {
                        "verdict": verdict,
                        "confidence": 0.88,
                        "reasoning": f"Directly validated by attached resource '{chunk.title}'.",
                        "evidence_ids": [chunk.evidence_id],
                    }

        # STEP 3: Project Name Stem Matching (Only for project-specific evidence)
        best_chunk = None
        best_matched: List[str] = []
        has_project_stem = False

        if section not in ("experience", "work_experience") or attached_url:
            for chunk in retrieved_chunks:
                if chunk.evidence_type == "github_tech_stack":
                    continue
                chunk_text = f"{chunk.title} {chunk.content}".lower()
                matched = [
                    t for t in substantive_tokens
                    if re.search(r'(?<![a-zA-Z0-9])' + re.escape(t) + r'(?![a-zA-Z0-9])', chunk_text)
                ]
                stem_matched = False
                for t in substantive_tokens:
                    if len(t) >= 4:
                        stem = t[:4]
                        repo_hint = (chunk.meta.get("repo") or "").lower() if isinstance(chunk.meta, dict) else ""
                        if stem in chunk.title.lower() or stem in repo_hint:
                            stem_matched = True
                            if t not in matched:
                                matched.append(t)

                if len(matched) > len(best_matched) or (stem_matched and not has_project_stem):
                    best_matched = matched
                    best_chunk = chunk
                    if stem_matched:
                        has_project_stem = True

            # Require actual project stem match to avoid false support on unrelated repos (e.g. spam_detector)
            if best_chunk and has_project_stem:
                verdict = "PARTIALLY_SUPPORTED" if has_private_metrics else "SUPPORTED"
                return {
                    "verdict": verdict,
                    "confidence": 0.80,
                    "reasoning": f"Corroborated by verified technical receipt in '{best_chunk.title}' (matched: {', '.join(best_matched[:3])}).",
                    "evidence_ids": [best_chunk.evidence_id],
                }

        # STEP 4: Check Other Repositories / Candidate Tech Stack Inventory
        tech_inventory_chunk = next((c for c in retrieved_chunks if c.evidence_type == "github_tech_stack"), None)
        if not tech_inventory_chunk and retrieved_chunks:
            tech_inventory_chunk = retrieved_chunks[0]

        if tech_inventory_chunk:
            inv_text = f"{tech_inventory_chunk.title} {tech_inventory_chunk.content}".lower()
            stack_matches = [
                t for t in substantive_tokens
                if re.search(r'(?<![a-zA-Z0-9])' + re.escape(t) + r'(?![a-zA-Z0-9])', inv_text)
            ]
            if stack_matches:
                if section in ("experience", "work_experience"):
                    return {
                        "verdict": "PARTIALLY_SUPPORTED",
                        "confidence": 0.75,
                        "reasoning": f"Proprietary company project completed during employment; candidate demonstrates core stack ({', '.join(stack_matches[:3])}) in public receipts.",
                        "evidence_ids": [tech_inventory_chunk.evidence_id],
                    }
                else:
                    return {
                        "verdict": "PARTIALLY_SUPPORTED",
                        "confidence": 0.70,
                        "reasoning": f"No public repository named '{project_name or 'project'}' exists, but candidate demonstrates proficiency in the claimed stack ({', '.join(stack_matches[:3])}) across other repositories.",
                        "evidence_ids": [tech_inventory_chunk.evidence_id],
                    }

        # Default UNVERIFIED
        return {
            "verdict": "UNVERIFIED",
            "confidence": 0.80,
            "reasoning": f"Public receipts do not contain sufficient evidence to substantiate '{claim_text[:60]}'.",
            "evidence_ids": [],
        }

    async def evaluate_claim(
        self,
        claim_text: str,
        category: str,
        source_text: str,
        retrieved_chunks: List[RetrievedEvidenceChunk],
        section: str = "project",
        claim_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluates a single claim using Groq with retrieved RAG context and strict guardrails."""
        if category == "skill":
            return self._rule_based_fallback(
                claim_text, retrieved_chunks, category="skill", section=section, claim_meta=claim_meta
            )

        bullshit_check = check_bullshit_project_contradiction(
            claim_text=claim_text,
            retrieved_chunks=retrieved_chunks,
            category=category,
            claim_meta=claim_meta,
        )
        if bullshit_check:
            return bullshit_check

        if not self.groq.is_configured:
            return self._rule_based_fallback(
                claim_text, retrieved_chunks, category=category, section=section, claim_meta=claim_meta
            )

        try:
            evidence_summary = []
            for chunk in retrieved_chunks[:3]:
                ev_meta = chunk.meta if isinstance(chunk.meta, dict) else {}
                evidence_summary.append({
                    "evidence_id": chunk.evidence_id,
                    "source_type": chunk.evidence_type,
                    "title": chunk.title,
                    "url": chunk.url,
                    "excerpt": chunk.content[:400],
                    "candidate_commits": ev_meta.get("candidate_commit_count"),
                    "total_commits": ev_meta.get("total_commit_count"),
                })

            user_payload = {
                "claim_text": claim_text,
                "category": category,
                "section": section,
                "project_name": (claim_meta or {}).get("project_name"),
                "attached_url": (claim_meta or {}).get("attached_url"),
                "original_resume_sentence": source_text,
                "available_evidence": evidence_summary,
            }

            response_text = await self.groq.chat_completion(
                system_prompt=EVALUATION_SYSTEM_PROMPT,
                user_prompt=json.dumps(user_payload, indent=2),
                temperature=0.1,
                json_mode=True,
                max_tokens=1500,
            )

            data = self.groq.extract_json(response_text)
            verdict = data.get("verdict", "UNVERIFIED")
            if verdict not in ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNVERIFIED", "CONTRADICTED"):
                verdict = "UNVERIFIED"

            evidence_ids = data.get("evidence_ids", [])
            if verdict == "UNVERIFIED":
                evidence_ids = []

            reasoning = data.get("reasoning", "Evidence evaluated.")

            # Guardrail 0: Bullshit / overplayed project check
            bullshit_check = check_bullshit_project_contradiction(
                claim_text=claim_text,
                retrieved_chunks=retrieved_chunks,
                category=category,
                claim_meta=claim_meta,
            )
            if bullshit_check:
                verdict = bullshit_check["verdict"]
                reasoning = bullshit_check["reasoning"]
                evidence_ids = bullshit_check["evidence_ids"]

            # Guardrail 1: 0-commit contradiction guard
            for chunk in retrieved_chunks:
                ev_meta = chunk.meta if isinstance(chunk.meta, dict) else {}
                cand_c = ev_meta.get("candidate_commit_count")
                tot_c = ev_meta.get("total_commit_count", 0)
                if cand_c is not None and tot_c > 5 and cand_c == 0:
                    if any(w in claim_text.lower() for w in ["built", "created", "architected", "developed", "engineered"]):
                        verdict = "CONTRADICTED"
                        reasoning = f"Repository '{chunk.title}' has {tot_c} commits, but candidate authored 0 of them."
                        evidence_ids = [chunk.evidence_id]
                        break

            # Guardrail 2: SQL domain mismatch guard
            tokens = [tok for tok in re.findall(r'\b[a-zA-Z0-9_\-\.+#]{2,}\b', claim_text.lower())]
            combined_evidence = " ".join(f"{c.title} {c.content}".lower() for c in retrieved_chunks)
            if "sql" in tokens and "sql" not in combined_evidence and verdict in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
                verdict = "UNVERIFIED"
                evidence_ids = []
                reasoning = "Evidence does not substantiate any SQL or relational database usage."

            return {
                "verdict": verdict,
                "confidence": float(data.get("confidence", 0.8)),
                "reasoning": reasoning,
                "evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [],
            }
        except GroqRateLimitError:
            raise
        except Exception as e:
            logger.warning(f"Groq evaluation exception for '{claim_text}': {e}. Using deterministic fallback.")
            return self._rule_based_fallback(
                claim_text, retrieved_chunks, category=category, section=section, claim_meta=claim_meta
            )

    async def evaluate_claims_batch(
        self,
        claims_with_chunks: List[Any],
    ) -> List[Any]:
        """
        Evaluates a list of (claim_obj, retrieved_chunks) tuples.
        Skills are evaluated deterministically in 0ms (0 API calls).
        Non-skill claims are batched into mini-batches of 4.
        """
        results = []
        skills = []
        projects = []

        for claim, chunks in claims_with_chunks:
            if claim.category == "skill":
                skills.append((claim, chunks))
            else:
                projects.append((claim, chunks))

        # 1. Evaluate all skills deterministically in 0ms (0 API calls)
        for claim, chunks in skills:
            claim_meta = getattr(claim, "meta", {}) or {}
            eval_res = self._rule_based_fallback(
                claim.claim_text,
                chunks,
                category="skill",
                section=getattr(claim, "section", "skills"),
                claim_meta=claim_meta,
            )
            results.append((claim, eval_res))

        # 2. Fast path: evaluate bullshit/overplayed projects deterministically in 0ms (0 API calls)
        remaining_projects = []
        for claim, chunks in projects:
            claim_meta = getattr(claim, "meta", {}) or {}
            bullshit_check = check_bullshit_project_contradiction(
                claim_text=claim.claim_text,
                retrieved_chunks=chunks,
                category=claim.category,
                claim_meta=claim_meta,
            )
            if bullshit_check:
                results.append((claim, bullshit_check))
            else:
                remaining_projects.append((claim, chunks))
        projects = remaining_projects

        # 3. If no project/experience claims remain, return immediately
        if not projects:
            return results

        # 4. If Groq is not configured, evaluate deterministically
        if not self.groq.is_configured:
            for claim, chunks in projects:
                claim_meta = getattr(claim, "meta", {}) or {}
                eval_res = self._rule_based_fallback(
                    claim.claim_text,
                    chunks,
                    category=claim.category,
                    section=getattr(claim, "section", "project"),
                    claim_meta=claim_meta,
                )
                results.append((claim, eval_res))
            return results

        # 5. Batch claims: evaluate remaining project claims in consolidated high-density batches (up to 15 claims per batch)
        batch_size = 15
        mini_batches = [projects[i:i + batch_size] for i in range(0, len(projects), batch_size)]
        evals_map: Dict[str, Any] = {}

        async def eval_mini_batch(batch_offset: int, batch_items: List[Any]):
            items_payload = []
            for idx_in_batch, (claim, chunks) in enumerate(batch_items):
                global_idx = batch_offset + idx_in_batch
                claim_meta = getattr(claim, "meta", {}) or {}
                evidence_brief = []
                for c in chunks[:3]:
                    c_meta = c.meta if isinstance(c.meta, dict) else {}
                    evidence_brief.append({
                        "evidence_id": c.evidence_id,
                        "title": c.title,
                        "url": c.url,
                        "summary": c.content[:250],
                        "candidate_commits": c_meta.get("candidate_commit_count"),
                        "total_commits": c_meta.get("total_commit_count"),
                    })
                items_payload.append({
                    "claim_id": str(global_idx),
                    "claim_text": claim.claim_text,
                    "section": getattr(claim, "section", "experience"),
                    "project_name": claim_meta.get("project_name"),
                    "attached_url": claim_meta.get("attached_url"),
                    "evidence": evidence_brief,
                })

            user_prompt = json.dumps({"claims_to_evaluate": items_payload}, indent=2)
            try:
                response_text = await self.groq.chat_completion(
                    system_prompt=BATCH_EVALUATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.1,
                    json_mode=True,
                    max_tokens=2500,
                )
                data = self.groq.extract_json(response_text)
                for item in data.get("evaluations", []):
                    c_id = str(item.get("claim_id", ""))
                    evals_map[c_id] = item
            except GroqRateLimitError:
                raise
            except Exception as e:
                logger.warning(f"Mini-batch evaluation fallback for batch {batch_offset}: {e}")

        # Run batches sequentially to maximize token capacity and prevent concurrent TPM/RPM spikes
        import asyncio
        for offset, b in zip(range(0, len(projects), batch_size), mini_batches):
            await eval_mini_batch(offset, b)
            if len(mini_batches) > 1:
                await asyncio.sleep(0.5)

        for idx, (claim, chunks) in enumerate(projects):
            matched = evals_map.get(str(idx))
            claim_meta = getattr(claim, "meta", {}) or {}
            if matched and matched.get("verdict") in ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNVERIFIED", "CONTRADICTED"):
                verdict = matched["verdict"]
                reasoning = matched.get("reasoning", "Evidence evaluated from repository receipts.")

                # Guard 0: Bullshit / overplayed project check
                bullshit_check = check_bullshit_project_contradiction(
                    claim_text=claim.claim_text,
                    retrieved_chunks=chunks,
                    category=claim.category,
                    claim_meta=claim_meta,
                )
                if bullshit_check:
                    verdict = bullshit_check["verdict"]
                    reasoning = bullshit_check["reasoning"]

                # Guard 1: 0-commit contradiction guard
                for c in chunks:
                    cm = c.meta if isinstance(c.meta, dict) else {}
                    cand_c = cm.get("candidate_commit_count")
                    tot_c = cm.get("total_commit_count", 0)
                    if cand_c is not None and tot_c > 5 and cand_c == 0:
                        if any(w in claim.claim_text.lower() for w in ["built", "created", "architected", "developed", "engineered"]):
                            verdict = "CONTRADICTED"
                            reasoning = f"Repository '{c.title}' has {tot_c} commits, but candidate authored 0 of them."
                            break

                # Guard 2: SQL guardrail
                if "sql" in claim.claim_text.lower():
                    combined = " ".join(f"{c.title} {c.content}".lower() for c in chunks)
                    if "sql" not in combined and verdict in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
                        verdict = "UNVERIFIED"
                        reasoning = "Evidence does not substantiate any SQL or relational database usage."

                evidence_ids = matched.get("evidence_ids", [])
                if verdict == "UNVERIFIED":
                    evidence_ids = []
                elif not evidence_ids and chunks:
                    evidence_ids = [chunks[0].evidence_id]

                try:
                    conf = float(matched.get("confidence", 0.8))
                except (ValueError, TypeError):
                    conf = 0.8

                results.append((claim, {
                    "verdict": verdict,
                    "confidence": conf,
                    "reasoning": reasoning,
                    "evidence_ids": evidence_ids,
                }))
            else:
                results.append((
                    claim,
                    self._rule_based_fallback(
                        claim.claim_text,
                        chunks,
                        category=claim.category,
                        section=getattr(claim, "section", "project"),
                        claim_meta=claim_meta,
                    )
                ))

        return results

