import json
from typing import Any, Dict, List, Optional
from backend.app.agents.groq_client import GroqClient, GroqRateLimitError
from backend.app.core.config import settings


ROAST_SYSTEM_PROMPT = """You are the Lead Roast & Slander Agent for doyoularp.
Your voice is internet-native, mercilessly sarcastic, technically devastating, and profoundly condescending toward resume hype, LinkedIn delusions, and CV fabrications.
You talk like a legendary senior engineer, cynical tech Twitter personality, and Reddit code reviewer shredding a CV that claims distributed AI microservices while having an empty GitHub profile with half-baked tutorial repos.

CRITICAL MANDATES:
1. MAXIMIZE SLANDER AND LENGTH: Write an extensive, multi-paragraph slanderous roast (at least 3 to 4 detailed paragraphs in "overall_roast"). Tear down their buzzword gymnastics ("spearheaded", "orchestrated", "architected"), their phantom scale, their non-existent metrics, and their empty commit logs.
2. GROUNDED IN EVIDENCE: Base your insults directly on the actual receipts provided (e.g. 0 commits in claimed repos, zero Kubernetes configs, missing production artifacts, unverified 10,000+ user claims).
3. NEVER make jokes about race, gender, religion, sexuality, health, physical appearance, or protected traits. Slander the code, the claims, the GitHub emptiness, and the resume fiction.
4. IN "verdict_summary": Provide a scathing, clinical post-mortem of their technical delusions and reality disconnect.
5. IN "funny_mismatch": Deliver a lethal, quotable one-liner contrasting their grandiose resume claim against the pitiful GitHub reality.
6. IF LEGIT: If (and only if) every single claim has matching receipts, write a grudging, sarcastic admission of competence (e.g., "Annoyingly, the receipts exist. Go touch grass.").

Return ONLY a JSON object:
{
  "overall_roast": "Multi-paragraph, merciless, extensive slanderous roast...",
  "verdict_summary": "Scathing clinical breakdown of their technical delusions...",
  "strongest_claim": "The one thing that barely held up, or 'None'...",
  "weakest_claim": "The most egregious fiction...",
  "funny_mismatch": "Lethal, memorable one-liner quote..."
}
"""


class RoastAgent:
    def __init__(self, groq_client: Optional[GroqClient] = None):
        self.groq = groq_client or GroqClient()

    def _fallback_roast(
        self,
        larp_score: float,
        evaluations: List[Dict[str, Any]],
        repos: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Deterministic extensive roast and slander generator for fallback or testing."""
        supported = [e for e in evaluations if e.get("verdict") == "SUPPORTED"]
        unverified = [e for e in evaluations if e.get("verdict") == "UNVERIFIED"]
        contradicted = [e for e in evaluations if e.get("verdict") == "CONTRADICTED"]

        strongest = supported[0].get("claim_text") if supported else "No fully verified claims found."
        weakest = contradicted[0].get("claim_text") if contradicted else (
            unverified[0].get("claim_text") if unverified else "All claims verified."
        )

        repo_count = len(repos) if repos else 0

        if larp_score >= 75.0:
            overall = (
                f"Behold the grand architect of digital mirages. Your resume reads like the sacred scriptures of a Fortune 500 CTO, "
                f"yet your public GitHub presence resembles an abandoned ghost town with {repo_count} desolate repositories and tumbleweeds blowing through your commit history. "
                f"You claimed '{weakest}' with the audacity of someone who believes hitting 'Deploy to Vercel' once makes them a distributed systems demigod.\n\n"
                f"Let us examine the sheer volume of cardiovascular exercise you put into those bullet points. You threw around buzzwords like microservices, high-throughput pipelines, and enterprise scalability, "
                f"yet not a single configuration file, Docker container, or Kubernetes manifest exists to prove you ever ran anything heavier than a local development server. "
                f"Calling this engineering is doing Olympic-level gymnastics with the English language.\n\n"
                f"In conclusion, your greatest technical achievement appears to be your ability to write fictional literature directly onto a PDF document. "
                f"If you spent half as much energy committing actual code as you do engineering LinkedIn buzzword fantasies, you might actually be half as good as your resume claims you are. "
                f"Re-calibrate your delusions before someone asks you to open a terminal in an interview."
            )
            verdict_sum = (
                "Catastrophic reality disconnect. High-tier resume fiction characterized by zero public provenance, "
                "phantom user metrics, and a total absence of the enterprise infrastructure claimed in the text."
            )
            funny = f"Bro claimed '{weakest}' with zero evidence in the commit logs and an empty git history."
        elif larp_score >= 40.0:
            overall = (
                "A textbook cocktail of 25% legitimate code and 75% unadulterated LinkedIn hype-farming. "
                "You have a couple of weekend projects and some tutorial code, which somehow got magnified into 'mission-critical cloud architectures' by the time it reached your resume printer.\n\n"
                "The scale you bragged about is currently hiding in stealth mode. The public evidence shows minor repositories and starter templates, "
                "yet you describe them with the solemn gravity of an engineer who personally prevented AWS from collapsing. "
                "We found the repos, but the enterprise traffic and millions of users must have taken an extended vacation.\n\n"
                "You have potential, but your resume is currently writing checks that your GitHub repositories cannot cash. Dial back the fiction before reality catches up with you."
            )
            verdict_sum = "Moderate fiction with noticeable exaggeration. Real code exists, but metrics and scale are severely inflated."
            funny = "The architecture sounds like Netflix; the actual repositories look like weekend Udemy tutorials."
        else:
            overall = (
                "Annoyingly, this resume actually has the receipts to back it up. We searched through the repositories, examined commit histories, "
                "and inspected package manifests hoping to find a fraud, but the code is genuinely there.\n\n"
                "You actually committed code, built what you said you built, and avoided drowning your bullet points in unbearable marketing jargon. "
                "There is virtually nothing to slander here, which is frankly a huge disappointment for our audit engine.\n\n"
                "Take the win, close your IDE, and go touch some grass."
            )
            verdict_sum = "Legitimate candidate. Low LARP detected with solid evidence provenance across public repositories."
            funny = "We crawled the entire internet looking for delusions and all we found was actual competent code. What a buzzkill."

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
    ) -> Dict[str, Any]:
        """Generates extended slanderous roast using Groq with deterministic fallback."""
        if not self.groq.is_configured or intensity == 0:
            return self._fallback_roast(larp_score, evaluations, repos)

        try:
            prompt_data = {
                "larp_score": larp_score,
                "intensity": intensity,
                "repositories_count": len(repos) if repos else 0,
                "repositories_summary": [
                    {
                        "name": r.get("name"),
                        "languages": list(r.get("languages", {}).keys()) if isinstance(r.get("languages"), dict) else [],
                        "candidate_commits": r.get("candidate_commit_count", 0),
                        "total_commits": r.get("total_commit_count", 0),
                    }
                    for r in (repos or [])[:5]
                ],
                "claim_evaluations": [
                    {
                        "claim": e.get("claim_text"),
                        "verdict": e.get("verdict"),
                        "reasoning": e.get("reasoning"),
                    }
                    for e in evaluations[:10]
                ],
            }

            response_text = await self.groq.chat_completion(
                system_prompt=ROAST_SYSTEM_PROMPT,
                user_prompt=json.dumps(prompt_data, indent=2),
                temperature=0.8,
                json_mode=True,
            )

            data = self.groq.extract_json(response_text)
            return {
                "overall_roast": data.get("overall_roast", "No roast available."),
                "verdict_summary": data.get("verdict_summary", "Evaluation complete."),
                "strongest_claim": data.get("strongest_claim"),
                "weakest_claim": data.get("weakest_claim"),
                "funny_mismatch": data.get("funny_mismatch"),
            }
        except GroqRateLimitError:
            raise
        except Exception:
            return self._fallback_roast(larp_score, evaluations, repos)
