import json
import logging
import random
from typing import Any, Dict, List, Optional, Tuple
from backend.app.agents.groq_client import GroqClient, GroqRateLimitError
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


ROAST_ARCHETYPES = {
    "exhausted_principal": {
        "title": "The Exhausted Staff / Principal Engineer",
        "tagline": "Battle-scarred infrastructure veteran who has reviewed 10,000 PRs and survived 2am outages",
        "persona_prompt": (
            "You are an exhausted Staff/Principal Engineer who has been reviewing code for 15+ years. "
            "You have survived multi-datacenter cascading failures, on-call paging at 3 AM, and seen every architectural fad crash and burn. "
            "You are profoundly weary of buzzword inflation. When you see a basic tutorial or empty repo described as a 'scalable distributed AI engine', "
            "it causes you physical fatigue. Your tone is dry, sarcastic, weary, pedantic, and surgically dissecting. "
            "You reference post-mortems, missing alerting, broken CI/CD pipelines, unhandled race conditions, and lack of real-world production hygiene."
        ),
    },
    "gordon_ramsay": {
        "title": "The Gordon Ramsay of Code Reviews",
        "tagline": "Furious Michelin-star code reviewer who cannot believe what you served into production",
        "persona_prompt": (
            "You are the Gordon Ramsay of software engineering and code reviews. "
            "You treat codebases like a chaotic kitchen and candidates like delinquent cooks who tried to serve raw chicken. "
            "You are explosive, theatrical, utterly exasperated, and brutally direct. "
            "When you see zero tests, no commits, or copied boilerplate, you shout in disbelief. "
            "Use signature turns of phrase: 'Raw! This repository is completely raw!', 'Where is the error handling?!', 'You claimed a microservice and served me a burnt template!' "
            "Tear apart their half-baked projects with passionate, high-energy fury."
        ),
    },
    "cynical_vc": {
        "title": "The Cynical VC Due-Diligence Lead",
        "tagline": "Merciless cap-table auditor who sniffs out pitch-deck vaporware before seed funding",
        "persona_prompt": (
            "You are a cynical Silicon Valley venture capital partner and technical due diligence lead. "
            "You have listened to hundreds of founders pitch 'AI-driven scalable paradigms' that turned out to be two shell scripts and a prayer. "
            "You view this resume like a seed-round pitch deck full of inflated vanity metrics, phantom user counts, and fictitious valuations. "
            "You speak in terms of unit economics, churn, vaporware, cap tables, SEC subpoenas, and catastrophic ROI. "
            "Treat their exaggerated metrics as fraudulent investor updates that would get a founder kicked out of Sand Hill Road."
        ),
    },
    "oss_purist": {
        "title": "The Hardcore Open Source Purist",
        "tagline": "Dogmatic git provenance zealot who worships atomic commits and public changelogs",
        "persona_prompt": (
            "You are a dogmatic open-source purist and Linux kernel contributor. "
            "To you, talk is cheap and running code with clean git logs is the only truth in the universe. "
            "You despise developers who hide behind private repositories, push massive monolithic commits with messages like 'update', or fork popular libraries and pretend they wrote them. "
            "You evaluate candidates strictly on their commit provenance, pull request hygiene, licensing, and public traceability. "
            "If they have zero GitHub links or empty commit graphs, you treat them like a charlatan roleplaying as a programmer."
        ),
    },
    "hn_skeptic": {
        "title": "The Snarky Hacker News Skeptic",
        "tagline": "Top-comment contrarian who deconstructs tech hype into its trivial pip-install reality",
        "persona_prompt": (
            "You are the perennial top-commenter on Hacker News who ruthlessly deconstructs every Show HN post. "
            "You are hyper-analytical, condescendingly polite on the surface, and devastatingly pedantic underneath. "
            "Whatever revolutionary system the candidate claims to have built, you point out that it's just a bloated wrapper around an off-the-shelf library, "
            "could be replaced with a 20-line bash script, and fails to handle basic network timeouts. "
            "You dissect their buzzwords with clinical precision, mocking the gap between the grand narrative and the mundane, buggy implementation."
        ),
    },
}

# --- PROCEDURAL MODULAR FALLBACK BANKS ---

NO_GITHUB_INTROS = [
    "Submitting a technical software engineering resume without a GitHub link is the developer equivalent of applying to be an airline pilot by showing a picture of a bird.",
    "No GitHub repository, organization, or profile link was detected anywhere in this resume. You brought a beautifully typeset piece of fiction to a technical code audit.",
    "A software engineer without a public code footprint in 2026 is indistinguishable from an AI chatbot hallucinating a career into an ATS template.",
    "You had the audacity to submit an engineering resume packed with distributed microservices and architectural buzzwords, yet you could not produce a single verifiable commit receipt.",
    "Welcome to stealth-mode engineering taken to its absolute comedic extreme: an entire software career existing solely in PDF form.",
]

NO_GITHUB_BODIES = [
    "In an industry where the only real proof of competence is running code, you decided that your word alone was worth a six-figure engineering salary. There are no commit timestamps. There are no pull requests. There are no Docker containers. There is only a document constructed from LinkedIn buzzwords and pure optimism.",
    "You spent days fine-tuning margins, agonizing over bullet points, and crafting epic tales of architectural triumph, yet somehow omitted the single URL that proves you know what a terminal is. What was the master strategy? Hoping the interviewer has never heard of version control?",
    "Every bullet point describes heroic feats of backend optimization and cloud infrastructure, yet we found zero lines of public code to verify it. In a field defined strictly by what you build and ship, submitting zero receipts is an unequivocal declaration of vaporware.",
    "We crawled every public source looking for code provenance and found absolute silence. You claim mastery across entire technology stacks, yet your work apparently exists exclusively on confidential napkins or in alternate dimensions.",
    "Your claims of high-throughput pipelines and enterprise scalability read like a thrilling sci-fi novel. Unfortunately, without a single repository or public commit, it remains strictly fictional literature.",
]

NO_GITHUB_OUTROS = [
    "If your code is operating in stealth mode, your job search should probably remain in stealth mode as well. Publish your code or stick to PowerPoint presentations.",
    "Take this resume, close your IDE, and go learn how to run 'git init'. Until you have verifiable receipts, you are simply roleplaying in a developer costume.",
    "Cancel the upcoming technical screens, start an actual repository, and write real code before a senior engineer asks you to share your screen.",
    "Either publish verifiable code receipts or pivot to tech influencer content creation full-time. Real engineers ship code; they don't hide behind typography.",
    "Re-calibrate your expectations before someone asks you to open a terminal in an interview and the illusion evaporates in thirty seconds.",
]

NO_GITHUB_MISMATCHES = [
    "Claimed full-stack enterprise architectural prowess, but forgot to attach a single line of public code.",
    "The resume reads like a Silicon Valley CTO; the verifiable code footprint is indistinguishable from an empty text file.",
    "Architected mission-critical cloud pipelines in imagination, with 0 git commits discovered on earth.",
    "100% buzzword density paired with 0% public code provenance.",
    "Applied for software engineering with zero public repos—the ultimate vaporware audition.",
]

NO_GITHUB_VERDICTS = [
    "FATAL PROVENANCE FAILURE: Zero GitHub links found in resume. Unsubstantiated claims of technical wizardry without a single commit receipt.",
    "GHOST ENGINEER DETECTED: Technical resume completely devoid of public repositories. 100% unverified buzzword fiction.",
    "VAPORWARE AUDIT FAILED: Software engineering claims require code receipts. None were provided.",
    "STEALTH MODE COLLAPSE: No repositories found. Grandiose architectural narrative with zero backing artifacts.",
    "ZERO-RECEIPT DISASTER: Complete absence of verifiable code evidence for any listed skill or project.",
]

HIGH_LARP_INTROS = [
    "Behold the grand architect of digital mirages. Your resume reads like the sacred scriptures of a Fortune 500 CTO, yet your public GitHub presence resembles an abandoned ghost town with {repo_count} desolate repositories and tumbleweeds blowing through your commit history.",
    "We have audited some ambitious resumes in our time, but this one deserves its own category in the fiction section. You promised mission-critical enterprise systems and delivered a graveyard of abandoned tutorial clones.",
    "Your resume is writing astronomical checks that your GitHub repositories cannot even begin to cash. You claimed world-class scalability, but your public commit history looks like someone who opened VS Code three times during finals week.",
    "The audacity is genuinely breathtaking. You strutted into this audit claiming '{weakest}' with the unearned confidence of someone who thinks running 'npx create-react-app' makes them a principal systems architect.",
    "Welcome to the fantasy league of software development. Every single bullet point is an Olympic-level exercise in linguistic gymnastics designed to disguise entry-level tutorials as enterprise-grade platforms.",
]

HIGH_LARP_BODIES = [
    "Let us examine the cardiovascular effort you put into those bullet points. You threw around terms like microservices, event-driven architectures, and high-throughput streaming, yet not a single configuration file, Docker container, or Kubernetes manifest exists to prove you ever ran anything heavier than a local development server.",
    "The receipts tell a devastating story. You boasted about handling massive scale and orchestrating complex distributed workflows, but the actual code consists of fork-and-forget repos with single-digit commits and default README files.",
    "Your claimed architecture sounds like Netflix; your actual repositories look like a weekend Udemy course that was abandoned at chapter three. Calling this professional software engineering is doing severe violence to the English language.",
    "We scoured your public footprint looking for the legendary infrastructure you described. What we found instead were starter templates with untouched dependencies, broken build scripts, and commit messages that simply read 'first commit' or 'fix bug'.",
    "You described your projects with the solemn gravity of an engineer who personally prevented AWS from collapsing, yet the commit logs reveal you barely authored 10% of the codebase before declaring victory and updating your LinkedIn headline.",
]

HIGH_LARP_OUTROS = [
    "In conclusion, your greatest technical achievement appears to be your ability to manufacture fictional literature directly onto a PDF. Re-calibrate your delusions before someone asks you to debug in real time.",
    "Close the resume builder, delete the buzzwords, and actually write some software. A junior engineer who ships real code is infinitely more valuable than an imaginary CTO who ships PDFs.",
    "If you spent half as much energy committing actual code as you do engineering LinkedIn buzzword fantasies, you might actually be half as good as your resume claims you are.",
    "This isn't an engineering portfolio; it's a monument to wishful thinking. Either build the things you bragged about or scrub the fiction before an interviewer opens your GitHub.",
    "We recommend an immediate, emergency downgrade of your resume bullet points from 'Architected Enterprise Solutions' to 'Successfully Ran npm start Once Without Crashing'.",
]

HIGH_LARP_MISMATCHES = [
    "Bro claimed '{weakest}' with zero evidence in the commit logs and an empty git history.",
    "Claimed high-throughput distributed architectures; actually pushed 3 commits to a forked tutorial.",
    "Resume says 'Cloud Infrastructure Architect'; GitHub reveals an abandoned todo list app.",
    "Bragged about production scale while having fewer public commits than a weekend hackathon demo.",
    "Described a starter template as an 'AI-driven scalable engine' with a straight face.",
]

HIGH_LARP_VERDICTS = [
    "CATASTROPHIC REALITY DISCONNECT: Extreme resume inflation characterized by zero public provenance and phantom enterprise metrics.",
    "MASSIVE LARP DETECTED: Claims of high-scale architectural dominance completely contradicted by empty repositories and absent commits.",
    "FICTION LEVEL CRITICAL: Grandiose claims of enterprise infrastructure backed by entry-level starter templates and negligible author contribution.",
    "TERMINAL HYPE OVERFLOW: Severe gap between stated technical achievements and the barren reality of public code receipts.",
    "SPECULATIVE VAPORWARE: Resume is an ambitious investor deck; actual GitHub presence is an abandoned construction site.",
]

MODERATE_LARP_INTROS = [
    "A textbook cocktail of 25% legitimate code and 75% unadulterated LinkedIn hype-farming.",
    "You have the beginnings of a real developer profile, but somewhere between writing the code and exporting the PDF, your imagination went into hyperdrive.",
    "There is real software here, but it has been heavily seasoned with senior-level buzzwords and inflated production metrics.",
    "You built some perfectly respectable weekend projects, but described them like you personally saved NASDAQ from a flash crash.",
    "A classic case of developer embellishment: the foundation is genuine, but the penthouse you described on top is made entirely of cardboard.",
]

MODERATE_LARP_BODIES = [
    "The scale you bragged about is currently hiding in stealth mode. The public evidence shows minor repositories and tutorial starter code, yet you describe them with the solemn gravity of enterprise cloud architectures. We found the repos, but the thousands of concurrent users must have taken an extended vacation.",
    "You clearly know your way around an IDE, but claiming you 'engineered fault-tolerant pipelines' when the repository has three commits and zero test coverage is pushing your luck. Tone down the superlatives before a technical interviewer asks for latency benchmarks.",
    "Your repositories confirm you know how to build basic applications, but the enterprise claims—Kubernetes orchestration, distributed caching, multi-region failover—are nowhere to be found in the configuration files.",
    "You have real code receipts, which puts you ahead of the pure pretenders, but your bullet points describe an architecture that exists only in your dreams. The delta between your actual commit logs and your resume prose is visible from space.",
]

MODERATE_LARP_OUTROS = [
    "You have potential, but your resume is currently writing checks that your GitHub repositories cannot cash. Dial back the fiction before reality catches up with you.",
    "Keep the code, ditch the hyperbole. You would be a solid hire if you stopped pretending your side project is a Fortune 500 platform.",
    "A good developer doesn't need to lie about scale. Let your actual code speak for itself instead of drowning it in marketing fluff.",
    "Dial down the corporate mythology. You wrote good code—there's no need to pretend you saved the global economy with a CRUD app.",
]

MODERATE_LARP_MISMATCHES = [
    "The architecture sounds like Netflix; the actual repositories look like weekend Udemy tutorials.",
    "Claimed mission-critical enterprise scale; evidence shows a standard side project with 12 commits.",
    "Decent hobby projects marketed with Fortune 500 vocabulary.",
    "Solid developer foundation buried under layers of unnecessary LinkedIn buzzword gymnastics.",
]

MODERATE_LARP_VERDICTS = [
    "MODERATE FICTION DETECTED: Noticeable exaggeration of scale and throughput. Genuine code exists, but metrics are severely inflated.",
    "HYPE FARMING IN PROGRESS: Real developer capability masked by unverified claims of enterprise-level architecture.",
    "EMBELLISHMENT WARNING: Legitimate baseline skills inflated with unproven production metrics and phantom traffic.",
    "AMBITIOUS DEVIATION: Repositories exist and show competence, but claimed architectural roles exceed evidence provenance.",
]

LOW_LARP_INTROS = [
    "Annoyingly, this resume actually has the receipts to back it up.",
    "We searched through your repositories, examined commit histories, and inspected package manifests hoping to find a fraud, but the code is genuinely there.",
    "Much to our disappointment, you appear to be a real, competent software engineer.",
    "We booted up our audit engine ready to shred another LinkedIn hype-merchant, and you had the nerve to submit legitimate, verified software.",
]

LOW_LARP_BODIES = [
    "You actually committed code, built what you said you built, and avoided drowning your bullet points in unbearable marketing jargon. There are clear commit timestamps, sensible package dependencies, and actual implementation logic. There is virtually nothing to slander here, which is frankly a huge disappointment for our audit engine.",
    "Your commit logs match your claims, your tech stack is verified in package manifests, and you didn't claim to have single-handedly re-architected AWS as a sophomore. It is refreshing, albeit deeply unsatisfying for a roast generator, to see an engineer who lets their work speak for itself.",
    "The code provenance is solid, the repository attribution checks out, and your bullet points reflect actual work done rather than aspirational daydreaming.",
]

LOW_LARP_OUTROS = [
    "Take the win, close your IDE, and go touch some grass.",
    "You survived the audit unscathed. Now go write some documentation—nobody is that perfect.",
    "Congratulations on having actual integrity. You make our slander engine completely obsolete.",
    "Solid work. We have nothing to mock here. Go celebrate with a fresh cup of coffee.",
]

LOW_LARP_MISMATCHES = [
    "We crawled the entire internet looking for delusions and all we found was actual competent code. What a buzzkill.",
    "Claimed solid software engineering skills, and annoyingly, actually possessed solid software engineering skills.",
    "Zero vaporware detected. What kind of software engineer actually commits what they claim?",
    "Every bullet point had a corresponding commit. Absolutely disgusting level of competence.",
]

LOW_LARP_VERDICTS = [
    "LEGITIMATE CANDIDATE: Low LARP detected with solid evidence provenance across public repositories.",
    "VERIFIED COMPETENCE: High provenance score. Claims match repository artifacts and commit history.",
    "AUTHENTIC ENGINEER: Rare case of zero fiction. Code receipts thoroughly corroborate resume claims.",
    "AUDIT PASSED WITH DISTINCTION: Real projects, legitimate author contribution, minimal marketing fluff.",
]


def build_roast_system_prompt(archetype_key: Optional[str] = None) -> Tuple[str, str]:
    """Builds a dynamic system prompt embodying one of the roast archetypes."""
    if not archetype_key or archetype_key not in ROAST_ARCHETYPES:
        archetype_key = random.choice(list(ROAST_ARCHETYPES.keys()))

    arch = ROAST_ARCHETYPES[archetype_key]

    system_prompt = f"""You are the Lead Roast & Slander Agent for doyoularp, adopting the persona of {arch['title']}.
Persona & Tone:
{arch['persona_prompt']}

CRITICAL MANDATES:
1. MAXIMIZE SLANDER AND LENGTH: Write an extensive, multi-paragraph slanderous roast (at least 3 to 4 detailed paragraphs in "overall_roast"). Shred their buzzword gymnastics ("spearheaded", "orchestrated", "architected"), their phantom scale, their non-existent metrics, and their empty commit logs.
2. GROUNDED IN SPECIFIC EVIDENCE: Weaponize the provided ammunition directly. Quote their exact contradicted claims, cite their single-commit repositories, expose their toy dependencies, and point out discrepancies between claimed throughput and actual code receipts.
3. NEVER make jokes about race, gender, religion, sexuality, health, physical appearance, or protected traits. Slander the code, the claims, the git emptiness, and the resume fiction.
4. IN "verdict_summary": Provide a scathing, clinical post-mortem of their technical delusions and reality disconnect.
5. IN "funny_mismatch": Deliver a lethal, quotable one-liner contrasting their grandiose resume claim against their pitiful GitHub/evidence reality.
6. IF LEGIT: If (and only if) every single claim has matching receipts (low LARP), write a grudging, sarcastic admission of competence in your persona's voice (e.g., admitting with deep annoyance that the code actually runs).
7. IF NO GITHUB: If no GitHub repository or profile link was provided in the resume (has_github = false), mock them relentlessly for submitting a ghost-mode technical resume with zero code provenance. Treat them like an architect showing up with no blueprints or a chef claiming Michelin stars without cooking a dish. Do NOT use canned clichés—craft a fresh, lethal critique of their missing code receipts in your persona's voice.

Return ONLY a JSON object:
{{
  "overall_roast": "Multi-paragraph, merciless, extensive slanderous roast...",
  "verdict_summary": "Scathing clinical breakdown of their technical delusions...",
  "strongest_claim": "The one thing that barely held up, or 'None'...",
  "weakest_claim": "The most egregious fiction...",
  "funny_mismatch": "Lethal, memorable one-liner quote..."
}}
"""
    return system_prompt, archetype_key


class RoastAgent:
    def __init__(self, groq_client: Optional[GroqClient] = None):
        self.groq = groq_client or GroqClient()

    def _fallback_roast(
        self,
        larp_score: float,
        evaluations: List[Dict[str, Any]],
        repos: Optional[List[Dict[str, Any]]] = None,
        has_github: bool = True,
        candidate_alias: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Procedural modular roast generator assembling dynamic combinations for testing and fallback."""
        supported = [e for e in evaluations if e.get("verdict") == "SUPPORTED"]
        unverified = [e for e in evaluations if e.get("verdict") == "UNVERIFIED"]
        contradicted = [e for e in evaluations if e.get("verdict") == "CONTRADICTED"]

        strongest = supported[0].get("claim_text") if supported else "No fully verified claims found."
        weakest = contradicted[0].get("claim_text") if contradicted else (
            unverified[0].get("claim_text") if unverified else "All claims verified."
        )

        repo_count = len(repos) if repos else 0

        if not has_github:
            intro = random.choice(NO_GITHUB_INTROS)
            body = random.choice(NO_GITHUB_BODIES)
            outro = random.choice(NO_GITHUB_OUTROS)
            funny = random.choice(NO_GITHUB_MISMATCHES)
            verdict_sum = random.choice(NO_GITHUB_VERDICTS)
            overall = f"{intro}\n\n{body}\n\n{outro}"
            return {
                "overall_roast": overall,
                "verdict_summary": verdict_sum,
                "strongest_claim": "None",
                "weakest_claim": "Zero GitHub profile or repository links provided in resume",
                "funny_mismatch": funny,
            }

        if larp_score >= 70.0:
            intro_tmpl = random.choice(HIGH_LARP_INTROS)
            intro = intro_tmpl.format(repo_count=repo_count, weakest=weakest)
            body = random.choice(HIGH_LARP_BODIES)
            outro = random.choice(HIGH_LARP_OUTROS)
            funny_tmpl = random.choice(HIGH_LARP_MISMATCHES)
            funny = funny_tmpl.format(weakest=weakest)
            verdict_sum = random.choice(HIGH_LARP_VERDICTS)
        elif larp_score >= 35.0:
            intro = random.choice(MODERATE_LARP_INTROS)
            body = random.choice(MODERATE_LARP_BODIES)
            outro = random.choice(MODERATE_LARP_OUTROS)
            funny = random.choice(MODERATE_LARP_MISMATCHES)
            verdict_sum = random.choice(MODERATE_LARP_VERDICTS)
        else:
            intro = random.choice(LOW_LARP_INTROS)
            body = random.choice(LOW_LARP_BODIES)
            outro = random.choice(LOW_LARP_OUTROS)
            funny = random.choice(LOW_LARP_MISMATCHES)
            verdict_sum = random.choice(LOW_LARP_VERDICTS)

        overall = f"{intro}\n\n{body}\n\n{outro}"

        return {
            "overall_roast": overall,
            "verdict_summary": verdict_sum,
            "strongest_claim": strongest,
            "weakest_claim": weakest,
            "funny_mismatch": funny,
        }

    async def generate_roast(
        self,
        larp_score: float,
        evaluations: List[Dict[str, Any]],
        repos: Optional[List[Dict[str, Any]]] = None,
        intensity: int = 3,
        has_github: bool = True,
        candidate_alias: Optional[str] = None,
        competitive_stats: Optional[Dict[str, Any]] = None,
        suspicious_dependencies: Optional[List[str]] = None,
        archetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates dynamic extended slanderous roast using chosen archetype with procedural fallback."""
        if not self.groq.is_configured or intensity == 0:
            return self._fallback_roast(
                larp_score, evaluations, repos, has_github=has_github, candidate_alias=candidate_alias
            )

        try:
            system_prompt, chosen_archetype = build_roast_system_prompt(archetype)
            arch_meta = ROAST_ARCHETYPES.get(chosen_archetype, {})

            # 1. Granular fuel extraction: worst contradicted claim
            contradicted_evals = [e for e in evaluations if e.get("verdict") == "CONTRADICTED"]
            worst_contradiction = None
            if contradicted_evals:
                target_c = contradicted_evals[0]
                worst_contradiction = {
                    "claim": target_c.get("claim_text"),
                    "source_quote": target_c.get("source_text"),
                    "reasoning": target_c.get("reasoning"),
                }

            # 2. Granular fuel: commit activity breakdown
            commit_activity = [
                {
                    "name": r.get("name"),
                    "candidate_commits": r.get("candidate_commit_count", 0),
                    "total_commits": r.get("total_commit_count", 0),
                    "languages": list(r.get("languages", {}).keys()) if isinstance(r.get("languages"), dict) else [],
                }
                for r in (repos or [])[:6]
            ]

            # 3. Verified languages
            verified_languages = sorted(list({
                lang
                for r in (repos or [])
                if isinstance(r.get("languages"), dict)
                for lang in r.get("languages", {}).keys()
                if lang
            }))

            prompt_data = {
                "larp_score": larp_score,
                "has_github": has_github,
                "intensity": intensity,
                "candidate_alias": candidate_alias or "Anonymous Candidate",
                "roast_archetype": arch_meta.get("title", chosen_archetype),
                "repositories_count": len(repos) if repos else 0,
                "worst_contradiction": worst_contradiction,
                "suspicious_dependencies": (suspicious_dependencies or [])[:15],
                "commit_activity_breakdown": commit_activity,
                "competitive_programming_stats": competitive_stats or {},
                "verified_languages": verified_languages,
                "missing_github_alert": (
                    "CRITICAL CONTEXT: NO GITHUB LINK FOUND IN RESUME. "
                    "The candidate claims engineering competencies with zero verifiable public code receipts. "
                    "In your chosen persona's voice, thoroughly slander this total absence of code provenance. "
                    "Do NOT use canned repetitive clichés; construct an original, ruthless critique."
                ) if not has_github else None,
                "claim_evaluations": [
                    {
                        "claim": e.get("claim_text"),
                        "source_quote": e.get("source_text"),
                        "verdict": e.get("verdict"),
                        "reasoning": e.get("reasoning"),
                    }
                    for e in evaluations[:12]
                ],
            }

            response_text = await self.groq.chat_completion(
                system_prompt=system_prompt,
                user_prompt=json.dumps(prompt_data, indent=2),
                temperature=0.95,
                frequency_penalty=0.6,
                presence_penalty=0.5,
                json_mode=True,
            )

            data = self.groq.extract_json(response_text)

            overall_roast = (
                data.get("overall_roast")
                or data.get("roast")
                or data.get("critique")
                or data.get("overall")
            )
            if not overall_roast or overall_roast == "No roast available.":
                logger.warning("LLM response did not contain valid 'overall_roast'. Utilizing dynamic procedural roast engine.")
                return self._fallback_roast(
                    larp_score, evaluations, repos, has_github=has_github, candidate_alias=candidate_alias
                )

            verdict_summary = data.get("verdict_summary") or data.get("summary") or "Evaluation complete."
            funny_mismatch = data.get("funny_mismatch") or data.get("mismatch")
            weakest_claim = data.get("weakest_claim") or ("Zero GitHub links provided" if not has_github else None)
            strongest_claim = data.get("strongest_claim") if has_github else "None"

            return {
                "overall_roast": overall_roast,
                "verdict_summary": verdict_summary,
                "strongest_claim": strongest_claim,
                "weakest_claim": weakest_claim,
                "funny_mismatch": funny_mismatch,
                "roast_archetype": chosen_archetype,
            }
        except GroqRateLimitError:
            raise
        except Exception as e:
            logger.warning(f"Roast generation via LLM encountered ({e}). Utilizing dynamic procedural roast engine.")
            return self._fallback_roast(
                larp_score, evaluations, repos, has_github=has_github, candidate_alias=candidate_alias
            )
