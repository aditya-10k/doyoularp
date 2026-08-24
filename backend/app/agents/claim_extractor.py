import re
from typing import Any, Dict, List, Optional
from backend.app.agents.groq_client import GroqClient, GroqRateLimitError


CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are an expert resume analyzer for doyoularp.
Your task is to convert resume text into a list of atomic, testable claims.
Each claim must be broken down into individual propositions.

Example:
"Built a Flutter travel application used by 10,000+ users and reduced API latency by 80%."
Becomes 4 atomic claims:
1. Built a travel application
2. Used Flutter framework
3. Application had 10,000+ users
4. Reduced API latency by 80%

SKILLS SECTION RULES:
For the Skills or Technologies section:
- Break down each individual claimed technology, language, framework, database, and tool into an atomic skill claim.
- E.g. "Languages: Python, Dart, SQL, Java" -> 4 claims: "Proficient in Python", "Proficient in Dart", "Proficient in SQL", "Proficient in Java".
- E.g. "Tools: Docker, Kubernetes, AWS" -> 3 claims: "Experienced with Docker", "Experienced with Kubernetes", "Experienced with AWS".
- Set category="skill", section="skills", technologies=[skill_name].
- Do NOT bundle multiple distinct skills into one claim.

CRITICAL EXCLUSION RULES (STRICT):
1. DO NOT EXTRACT ANY CLAIMS FROM THE EDUCATION SECTION. Completely ignore all degrees, universities, colleges, schools, GPA, courses, and graduation dates.
2. DO NOT EXTRACT CANDIDATE NAMES, PHONE NUMBERS, EMAIL ADDRESSES, OR CONTACT INFORMATION.
3. DO NOT EXTRACT DATES, TIMELINES, EMPLOYMENT PERIODS, OR DURATIONS OF WORK EXPERIENCE (e.g. "Worked from Jan 2022 - Present", "3 years of experience", "Duration: 6 months", "2020 - 2023", "tenure: 2 years"). Ignore all job dates and durations!
4. DO NOT EXTRACT COMPANY NAMES, EMPLOYER HEADERS, OR JOB TITLES (e.g. "Quickyearning Private Limited", "App Developer Intern", "Software Engineer"). Only extract the actual technical deliverables, engineering work, and software built.
5. DO NOT EXTRACT LOCATIONS OR ADDRESSES (e.g. "Borivali West , Mumbai, Maharashtra", "San Francisco, CA", "Remote").
6. ONLY extract substantive technical skills, software projects, system architecture, and technical engineering deliverables.
7. For technical skills, strip category headers like "Languages & Databases:" or "Frameworks & Libraries:". E.g., for "Languages & Databases: C, Java", extract "Proficient in C", "Proficient in Java". Never include "Languages & Databases:" in claim_text.

Return ONLY a JSON object with this exact structure:
{
  "claims": [
    {
      "claim_text": "Built a full-stack elder care platform with React, Spring Boot, and PostgreSQL",
      "category": "project",
      "section": "projects",
      "project_name": "ElderCare AI Platform",
      "attached_url": "https://github.com/Akshat0801chauhan/Elderly_AI.git",
      "technologies": ["React", "Spring Boot", "PostgreSQL"],
      "source_text": "Built a full-stack elderly care platform..."
    }
  ]
}

Categories must be one of: "project", "skill", "achievement", "experience". (NEVER use "education").
If a project or work experience item corresponds to an attached link (GitHub repo, Play Store app, live demo, Drive certificate), populate "attached_url". If none, set null.
Populate "project_name" with the project or employer name (e.g. "ElderCare AI Platform", "Nexport", "DiamondRock"), or null if general.
Do NOT invent claims. Every claim must have its exact original resume sentence in "source_text".
"""

LOCATION_WORDS = {
    "mumbai", "maharashtra", "borivali", "delhi", "bangalore", "bengaluru",
    "pune", "hyderabad", "chennai", "noida", "gurgaon", "gurugram", "kolkata",
    "india", "usa", "california", "new york", "san francisco", "remote",
    "hybrid", "on-site", "onsite", "west", "east", "north", "south", "central"
}

ROLE_TITLES = [
    "developer", "engineer", "intern", "trainee", "architect", "consultant",
    "specialist", "analyst", "manager", "lead", "associate", "founder", "co-founder"
]

COMPANY_SUFFIXES = [
    "private limited", "pvt ltd", "pvt. ltd.", "ltd", "llc", "inc",
    "corp", "corporation", "technologies pvt", "solutions ltd", "company", "quickyearning"
]

ACTION_VERBS = [
    "built", "developed", "engineered", "architected", "implemented", "designed",
    "created", "deployed", "optimized", "integrated", "reduced", "achieved",
    "scaled", "spearheaded", "led", "maintained", "refactored", "automated",
    "launched", "published", "trained", "analyzed", "delivered", "authored",
    "leveraged", "programmed", "orchestrated", "constructed", "configured",
    "tested", "debugged", "monitored", "migrated"
]


def is_excluded_claim(claim_text: str, category: str = "", section: str = "") -> bool:
    """Checks if a claim pertains to name, phone/contact number, education, work dates/duration, locations, or role headers."""
    c_lower = (claim_text or "").lower().strip()
    cat_lower = (category or "").lower()
    sec_lower = (section or "").lower()

    # 1. Education exclusions
    if cat_lower == "education" or sec_lower in ("education", "academics", "qualifications"):
        return True
    education_keywords = [
        "bachelor", "b.s.", "b.tech", "b.e.", "b.a.", "master", "m.s.", "m.tech", "ph.d", "phd",
        "degree", "university", "college", "gpa", "cgpa", "graduated", "graduation",
        "coursework", "curriculum", "high school", "diploma", "institute of technology",
        "academic", "dean's list", "honors", "cum laude", "secondary education"
    ]
    if any(re.search(r'\b' + re.escape(k) + r'\b', c_lower) for k in education_keywords):
        return True

    # 2. Phone number / contact number / email exclusions
    if re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', claim_text):
        return True
    if re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', claim_text):
        return True
    if any(k in c_lower for k in ["candidate name", "my name is", "address:", "location:", "phone:", "mobile:"]):
        return True

    # 3. Work experience dates, tenure, timeline, and duration exclusions (handling glued month names)
    c_unglued = re.sub(r'([a-z0-9])(january|february|march|april|may|june|july|august|september|october|november|december)', r'\1 \2', c_lower)
    c_unglued = re.sub(r'([a-z0-9])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', r'\1 \2', c_unglued)

    duration_pattern = r'\b\d+\+?\s*(?:years?|yrs?|months?|mos?)\s*(?:of)?\s*(?:experience|tenure|duration|work|background)?\b'
    if re.search(duration_pattern, c_unglued):
        return True

    if any(k in c_unglued for k in [
        "employment period", "tenure:", "duration:", "dates of employment",
        "internship period", "worked from", "employed from", "timeframe:",
        "period of employment", "months of experience", "years of experience"
    ]):
        return True

    date_range_pattern = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}\s*[-–—to]+\s*(?:present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4})'
    year_range_pattern = r'\b\d{4}\s*[-–—to]+\s*(?:\d{4}|present|current|now)\b'

    if re.search(date_range_pattern, c_unglued) or re.search(year_range_pattern, c_unglued):
        substance = re.sub(date_range_pattern, '', c_unglued)
        substance = re.sub(year_range_pattern, '', substance)
        substance_chars = re.sub(r'[^a-z0-9]', '', substance)
        if len(substance_chars) < 25 or any(s in substance for s in COMPANY_SUFFIXES) or not any(v in substance for v in ACTION_VERBS):
            return True

    # 4. Pure company names / employer headers
    if any(re.search(r'\b' + re.escape(s) + r'\b', c_lower) for s in COMPANY_SUFFIXES):
        if not any(re.search(r'\b' + re.escape(v) + r'\b', c_lower) for v in ACTION_VERBS):
            return True

    # 5. Pure location strings (e.g. "Borivali West , Mumbai, Maharashtra")
    words = re.findall(r'[a-z]+', c_lower)
    if words and all(w in LOCATION_WORDS or w in ["west", "east", "north", "south", "central"] for w in words):
        return True
    if any(re.search(r'\b' + re.escape(loc) + r'\b', c_lower) for loc in LOCATION_WORDS):
        tech_guards = ["react", "flutter", "python", "node", "api", "database", "spring", "docker", "postgres"]
        if not any(re.search(r'\b' + re.escape(v) + r'\b', c_lower) for v in ACTION_VERBS) and not any(re.search(r'\b' + re.escape(kw) + r'\b', c_lower) for kw in tech_guards):
            return True

    # 6. Pure job titles / role designations (e.g. "App Developer Intern Mumbai, Maharashtra")
    if any(re.search(r'\b' + re.escape(title) + r'\b', c_lower) for title in ROLE_TITLES):
        tech_guards = ["react", "flutter", "python", "node", "api", "sql", "spring", "docker", "postgres"]
        if not any(re.search(r'\b' + re.escape(v) + r'\b', c_lower) for v in ACTION_VERBS) and not any(re.search(r'\b' + re.escape(kw) + r'\b', c_lower) for kw in tech_guards):
            return True

    return False


def strip_name_number_and_education(resume_text: str) -> str:
    """Strips candidate name, phone numbers, education section, and isolated date/duration/location headers."""
    # Un-glue months and dates
    resume_text = re.sub(r'([a-z0-9])(January|February|March|April|May|June|July|August|September|October|November|December)', r'\1 \2', resume_text)
    resume_text = re.sub(r'([a-z0-9])(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', r'\1 \2', resume_text)

    lines = resume_text.splitlines()
    cleaned_lines: List[str] = []
    in_education = False

    date_range_pattern = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}\s*[-–—to]+\s*(?:present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4})'
    year_range_pattern = r'\b\d{4}\s*[-–—to]+\s*(?:\d{4}|present|current|now)\b'
    duration_tag_pattern = r'\(\s*\d+\s*(?:yrs?|years?)\s*(?:\d+\s*(?:mos?|months?))?\s*\)'

    for idx, line in enumerate(lines):
        line_strip = line.strip()
        lower = line_strip.lower()

        # Check for start of education section
        if re.match(r'^(education|academic background|academics|qualifications)\b', lower):
            in_education = True
            continue

        # Check for start of a new section that ends education
        if in_education and any(lower.startswith(k) for k in [
            "experience", "work experience", "projects", "technical projects",
            "skills", "technical skills", "technologies", "certifications",
            "achievements", "publications"
        ]):
            in_education = False

        if in_education:
            continue

        # Strip phone numbers from text
        line_clean = re.sub(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', line_strip)

        # Strip isolated duration tags like '(2 yrs 3 mos)'
        line_clean = re.sub(duration_tag_pattern, '', line_clean, flags=re.IGNORECASE)

        # Skip lines matching exclusions (locations, dates, company headers, role titles)
        if is_excluded_claim(line_clean, "experience", "experience"):
            continue

        # Skip top 3 lines if they are candidate name or contact lines (never skip section headers or skills)
        if idx < 3:
            if re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', line_strip) or (
                len(line_strip) < 35
                and not any(kw in lower for kw in ["developer", "engineer", "software"])
                and not any(sec in lower for sec in ["skill", "project", "experience", "language", "framework", "tool", "database", "work", "technical"])
            ):
                continue

        line_final = line_clean.strip()
        if not line_final:
            continue

        # Merge wrapped lines if line starts with lowercase or continuation punctuation
        if cleaned_lines and (line_final[0].islower() or line_final.startswith((',', '.', ';', ')', ']'))):
            cleaned_lines[-1] = cleaned_lines[-1] + " " + line_final
        else:
            cleaned_lines.append(line_final)

    return "\n".join(cleaned_lines)


class ClaimExtractor:
    def __init__(self, groq_client: Optional[GroqClient] = None):
        self.groq = groq_client or GroqClient()

    def _rule_based_fallback(self, resume_text: str, discovered_urls: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Deterministic claim extractor for testing/offline use, enforcing action verbs and project context."""
        claims = []
        clean_text = strip_name_number_and_education(resume_text)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

        current_section = "general"
        current_project_name: Optional[str] = None
        current_attached_url: Optional[str] = None
        urls_pool = list(discovered_urls or [])

        for line in lines:
            line_clean = line.strip("•-*• \t")
            lower = line_clean.lower()

            # Detect sections
            if any(h in lower for h in ["experience", "employment", "work history"]):
                current_section = "experience"
                current_project_name = None
                current_attached_url = None
                continue
            elif any(h in lower for h in ["projects", "personal projects"]):
                current_section = "project"
                current_project_name = None
                current_attached_url = None
                continue
            elif any(h in lower for h in ["skills", "technical skills", "technologies"]):
                current_section = "skill"
                current_project_name = None
                current_attached_url = None
                continue
            elif any(h in lower for h in ["education", "academic", "academics", "qualifications"]):
                current_section = "education"
                continue

            # SKIP EDUCATION SECTION ENTIRELY
            if current_section == "education":
                continue

            # Skip lines matching personal or education exclusions
            if is_excluded_claim(line_clean, current_section, current_section):
                continue

            # Detect project or company title headers
            if ("|" in line_clean or " - " in line_clean or len(line_clean) < 45) and not any(v in lower for v in ACTION_VERBS):
                header_title = line_clean.split("|")[0].split(" - ")[0].strip()
                if len(header_title) >= 3:
                    current_project_name = header_title
                    # Match any discovered URL with project name
                    current_attached_url = None
                    for u in urls_pool:
                        u_lower = u.lower()
                        stem = header_title.lower().split()[0]
                        if len(stem) >= 4 and stem in u_lower:
                            current_attached_url = u
                            break

            # Check if this line is in skills section or contains a skills prefix
            is_skill_line = current_section == "skill" or any(lower.startswith(k) for k in [
                "languages:", "frameworks:", "technologies:", "databases:", "tools:", "skills:",
                "languages & databases:", "frameworks & libraries:", "technical skills:"
            ]) or (":" in line_clean and any(k in lower.split(":")[0] for k in ["language", "framework", "database", "library", "tool", "skill"]))
            if is_skill_line:
                raw_skills = re.split(r'[,|•;]', line_clean)
                for s in raw_skills:
                    s_clean = s.strip()
                    s_clean = re.sub(r'^[\w\s&/\\-]+:\s*', '', s_clean, flags=re.IGNORECASE).strip()
                    if 1 <= len(s_clean) <= 30 and not any(kw in s_clean.lower() for kw in ["technical", "skills", "proficient", "framework", "languages"]):
                        if not is_excluded_claim(s_clean, "skill", "skill"):
                            claims.append({
                                "claim_text": f"Proficient in {s_clean}",
                                "category": "skill",
                                "section": "skill",
                                "project_name": None,
                                "attached_url": None,
                                "technologies": [s_clean],
                                "source_text": line_clean,
                            })
                continue

            # Substantive project/experience line requirement:
            # Must be at least 20 chars AND contain a technical/engineering action verb
            if len(line_clean) >= 20 and any(v in lower for v in ACTION_VERBS):
                category = "project" if current_section == "project" else "experience"
                claims.append({
                    "claim_text": line_clean,
                    "category": category,
                    "section": current_section,
                    "project_name": current_project_name,
                    "attached_url": current_attached_url,
                    "technologies": [],
                    "source_text": line_clean,
                })

        return claims[:25]

    async def extract_claims(self, resume_text: str, discovered_urls: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Extracts atomic claims using Groq LLM with fallback, filtering out name, phone, education, dates, and locations."""
        clean_text = strip_name_number_and_education(resume_text)

        if not self.groq.is_configured:
            return self._rule_based_fallback(clean_text, discovered_urls)

        try:
            # Truncate clean resume text if excessively long
            truncated_text = clean_text[:8000]
            urls_section = ""
            if discovered_urls:
                clean_urls = [u for u in discovered_urls if not u.startswith("mailto:")]
                if clean_urls:
                    urls_json = json.dumps(clean_urls[:15], indent=2)
                    urls_section = f"Discovered Resume Links:\n{urls_json}\n\n"

            user_prompt = f"{urls_section}Resume text:\n\n{truncated_text}"

            response_text = await self.groq.chat_completion(
                system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                json_mode=True,
                max_tokens=3000,
            )

            data = self.groq.extract_json(response_text)
            claims = data.get("claims", [])
            if isinstance(claims, list) and claims:
                # Strictly filter out any education, name, phone, date, location, or company claims
                filtered = [
                    c for c in claims
                    if not is_excluded_claim(
                        c.get("claim_text", ""),
                        c.get("category", ""),
                        c.get("section", "")
                    )
                ]
                if filtered:
                    return filtered[:25]

            return self._rule_based_fallback(clean_text, discovered_urls)
        except GroqRateLimitError:
            raise
        except Exception:
            return self._rule_based_fallback(clean_text, discovered_urls)
