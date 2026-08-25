import pytest
from backend.app.agents.claim_extractor import (
    ClaimExtractor,
    is_excluded_claim,
    strip_name_number_and_education,
)


def test_is_excluded_claim_education():
    # Degrees and universities must be excluded
    assert is_excluded_claim("Bachelor of Science in Computer Science", "education", "education") is True
    assert is_excluded_claim("Master of Science in Artificial Intelligence", "project", "education") is True
    assert is_excluded_claim("Graduated with 3.8 GPA from University of California", "achievement", "education") is True
    assert is_excluded_claim("Coursework: Algorithms, Operating Systems, Database Systems", "education", "education") is True
    assert is_excluded_claim("B.Tech in Computer Engineering", "education", "education") is True
    assert is_excluded_claim("Dean's list honors graduate", "achievement", "education") is True


def test_is_excluded_claim_phone_and_name():
    # Phone numbers and contact info must be excluded
    assert is_excluded_claim("+1 (555) 234-5678", "general", "general") is True
    assert is_excluded_claim("Phone: 987-654-3210", "general", "general") is True
    assert is_excluded_claim("Mobile: +91 9876543210", "general", "general") is True
    assert is_excluded_claim("alex.dev@gmail.com", "general", "general") is True
    assert is_excluded_claim("Candidate Name: Alex Rivera", "general", "general") is True


def test_is_excluded_claim_work_dates_and_duration():
    # Work experience duration, tenure, and dates must be excluded
    assert is_excluded_claim("Jan 2022 - Present", "experience", "experience") is True
    assert is_excluded_claim("June 2020 to August 2022", "experience", "experience") is True
    assert is_excluded_claim("3+ years of experience in software development", "experience", "experience") is True
    assert is_excluded_claim("Employment period: 2 years", "experience", "experience") is True
    assert is_excluded_claim("Duration: 6 months", "experience", "experience") is True
    assert is_excluded_claim("Tenure: 18 months", "experience", "experience") is True
    assert is_excluded_claim("2021 - 2024", "experience", "experience") is True


def test_is_not_excluded_technical_substance():
    # Technical skills and projects must NOT be excluded
    assert is_excluded_claim("Proficient in Python", "skill", "skills") is False
    assert is_excluded_claim("Proficient in Docker", "skill", "skills") is False
    assert is_excluded_claim("Proficient in SQL", "skill", "skills") is False
    assert is_excluded_claim("Built a Flutter travel booking application", "project", "projects") is False
    assert is_excluded_claim("Architected high throughput Kafka microservices", "experience", "experience") is False


def test_strip_name_number_and_education():
    raw_resume = """Alex Rivera
alex.rivera@example.com
(555) 234-5678

EDUCATION
University of California, Berkeley
Bachelor of Science in Computer Science
GPA: 3.9 / 4.0 | Graduated May 2024
Relevant Coursework: Distributed Systems, Compilers

TECHNICAL SKILLS
Languages: Python, Dart, SQL, TypeScript
Frameworks: Flutter, FastAPI, React
Tools: Docker, Git, Linux

EXPERIENCE
Software Engineer at Acme Corp
Built high-performance payment processing pipeline using Python and Redis.
Reduced transaction latency by 45%.

PROJECTS
CricManager
Built Flutter mobile tournament management application used by 5,000 players.
"""
    cleaned = strip_name_number_and_education(raw_resume)

    # Verify education is completely gone
    assert "Berkeley" not in cleaned
    assert "Bachelor of Science" not in cleaned
    assert "GPA: 3.9" not in cleaned
    assert "Relevant Coursework" not in cleaned

    # Verify phone number is gone
    assert "(555) 234-5678" not in cleaned

    # Verify technical skills, experience, and projects remain intact
    assert "Languages: Python, Dart, SQL, TypeScript" in cleaned
    assert "Built high-performance payment processing pipeline" in cleaned
    assert "CricManager" in cleaned
    assert "Built Flutter mobile tournament management application" in cleaned


@pytest.mark.asyncio
async def test_claim_extractor_skips_education_and_contact():
    raw_resume = """Alex Rivera
alex.rivera@example.com
(555) 234-5678

EDUCATION
Stanford University
Bachelor of Science in Computer Science
GPA: 3.9 / 4.0

TECHNICAL SKILLS
Languages: Python, Go, SQL

PROJECTS
CloudMonitor
Built distributed metrics daemon in Go.
"""
    extractor = ClaimExtractor()
    claims = await extractor.extract_claims(raw_resume)

    claim_texts = [c["claim_text"].lower() for c in claims]

    # No education claims
    for txt in claim_texts:
        assert "stanford" not in txt
        assert "bachelor" not in txt
        assert "gpa" not in txt
        assert "555" not in txt

    # Technical skills and projects are present
    assert any("python" in txt for txt in claim_texts)
    assert any("go" in txt for txt in claim_texts)


def test_is_excluded_claim_locations_and_company_headers():
    # Locations, company names with dates, and job titles must be excluded
    assert is_excluded_claim("Borivali West , Mumbai, Maharashtra", "experience", "experience") is True
    assert is_excluded_claim("Quickyearning Private LimitedDecember 2024 - March 2025", "experience", "experience") is True
    assert is_excluded_claim("App Developer Intern Mumbai, Maharashtra", "experience", "experience") is True
    assert is_excluded_claim("San Francisco, CA", "experience", "experience") is True
    assert is_excluded_claim("Acme Corp December 2022 - Present", "experience", "experience") is True

    # Real engineering claims must NOT be excluded
    assert is_excluded_claim("Developed and launched the DiamondRock stock market application using Flutter and Node.js", "experience", "experience") is False
    assert is_excluded_claim("Engineered scalable real-time data pipelines using REST APIs", "experience", "experience") is False
    assert is_excluded_claim("Built a full-stack elderly care platform to close gaps in remote elder supervision", "project", "projects") is False

