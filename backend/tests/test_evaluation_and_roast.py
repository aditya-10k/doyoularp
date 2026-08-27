import pytest
from backend.app.agents.evaluation_agent import EvaluationAgent
from backend.app.agents.larp_calculator import calculate_larp_score
from backend.app.agents.roast_agent import RoastAgent
from backend.app.rag.evidence_retriever import RetrievedEvidenceChunk


@pytest.mark.asyncio
async def test_evaluation_verdicts():
    agent = EvaluationAgent()

    # 1. Missing evidence must be UNVERIFIED
    res_unverified = await agent.evaluate_claim(
        claim_text="Scaled Kafka cluster to 1M events per second",
        category="achievement",
        source_text="Scaled Kafka cluster to 1M events per second",
        retrieved_chunks=[],
    )
    assert res_unverified["verdict"] == "UNVERIFIED"
    assert res_unverified["evidence_ids"] == []

    # 2. Strong matching evidence with candidate authorship must be SUPPORTED
    supported_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_1",
        score=0.88,
        title="travel-app",
        content="Flutter travel booking app",
        url="https://github.com/user/travel-app",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 50, "total_commit_count": 55},
    )
    res_supported = await agent.evaluate_claim(
        claim_text="Built a mobile travel app using Flutter",
        category="project",
        source_text="Built a mobile travel app using Flutter",
        retrieved_chunks=[supported_chunk],
    )
    assert res_supported["verdict"] == "SUPPORTED"
    assert "ev_1" in res_supported["evidence_ids"]

    # 3. Claiming to have built a project with 0 candidate commits must be CONTRADICTED
    contradicted_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_2",
        score=0.85,
        title="popular-framework",
        content="Core creator of popular framework",
        url="https://github.com/bigorg/popular-framework",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 0, "total_commit_count": 500},
    )
    res_contra = await agent.evaluate_claim(
        claim_text="Built the popular-framework core engine",
        category="project",
        source_text="Built the popular-framework core engine",
        retrieved_chunks=[contradicted_chunk],
    )
    assert res_contra["verdict"] == "CONTRADICTED"
    assert "ev_2" in res_contra["evidence_ids"]

    # 4. Strict domain mismatch guard: CrickManager CANNOT verify an SQL editor claim
    crick_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_crick",
        score=0.55,
        title="Repository crickmanager",
        content="Repo: crickmanager. Description: Cricket tournament scoring and team management app in Flutter. Languages: ['Dart'].",
        url="https://github.com/user/crickmanager",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 5, "total_commit_count": 5},
    )
    res_sql = await agent.evaluate_claim(
        claim_text="Built a Flutter-based SQL editor and query tool",
        category="project",
        source_text="Built a Flutter-based SQL editor and query tool",
        retrieved_chunks=[crick_chunk],
    )
    assert res_sql["verdict"] == "UNVERIFIED"
    assert res_sql["evidence_ids"] == []

    # 5. Technical skill match: Flutter with substantial commits (>=10) is SUPPORTED
    manifest_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_manifest",
        score=0.90,
        title="crickmanager pubspec.yaml",
        content="Project: crickmanager\nManifest: pubspec.yaml\nVerification Summary: Flutter/Dart project 'crickmanager'. Dependencies: flutter, provider.",
        url="https://github.com/user/crickmanager",
        evidence_type="github_manifest",
        meta={"candidate_commit_count": 25, "total_commit_count": 30},
    )
    res_flutter_skill = await agent.evaluate_claim(
        claim_text="Proficient in Flutter",
        category="skill",
        source_text="Frameworks: Flutter, React",
        retrieved_chunks=[manifest_chunk],
    )
    assert res_flutter_skill["verdict"] == "SUPPORTED"
    assert "ev_manifest" in res_flutter_skill["evidence_ids"]

    # 5b. Technical skill with only 1 single match and low commits (<10) is PARTIALLY_SUPPORTED
    single_match_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_single",
        score=0.80,
        title="sample_repo package.json",
        content="Package: sample_repo\nDependencies: redis.",
        url="https://github.com/user/sample_repo",
        evidence_type="github_manifest",
        meta={"candidate_commit_count": 2, "total_commit_count": 5},
    )
    res_single = await agent.evaluate_claim(
        claim_text="Proficient in Redis",
        category="skill",
        source_text="Databases: Redis",
        retrieved_chunks=[single_match_chunk],
    )
    assert res_single["verdict"] == "PARTIALLY_SUPPORTED"

    # 6. Technical skill missing from receipts: SQL claimed with no SQL receipts must be UNVERIFIED
    res_sql_skill = await agent.evaluate_claim(
        claim_text="Proficient in SQL",
        category="skill",
        source_text="Databases: SQL, PostgreSQL",
        retrieved_chunks=[manifest_chunk],
    )
    assert res_sql_skill["verdict"] == "UNVERIFIED"
    assert res_sql_skill["evidence_ids"] == []


def test_larp_score_calculator():
    # Candidate with fully verified claims
    legit_evals = [
        {"verdict": "SUPPORTED"},
        {"verdict": "SUPPORTED"},
        {"verdict": "SUPPORTED"},
    ]
    legit_score = calculate_larp_score(legit_evals)["larp_score"]
    assert legit_score <= 20.0

    # Candidate with 0 receipts (100% unverified claims) must escalate to CRITICAL DELUSION (>= 85.0)
    unverified_evals = [
        {"verdict": "UNVERIFIED"},
        {"verdict": "UNVERIFIED"},
        {"verdict": "UNVERIFIED"},
    ]
    unverified_score = calculate_larp_score(unverified_evals)["larp_score"]
    assert unverified_score >= 85.0

    # Candidate with contradicted claims
    fraud_evals = [
        {"verdict": "CONTRADICTED"},
        {"verdict": "CONTRADICTED"},
        {"verdict": "UNVERIFIED"},
    ]
    fraud_score = calculate_larp_score(fraud_evals)["larp_score"]
    assert fraud_score >= 80.0

    # Candidate with mix of supported and unverified claims: must NOT drop to 0.0
    mixed_evals = [
        {"verdict": "SUPPORTED"},
        {"verdict": "SUPPORTED"},
        {"verdict": "UNVERIFIED"},
        {"verdict": "UNVERIFIED"},
        {"verdict": "UNVERIFIED"},
    ]
    mixed_score = calculate_larp_score(mixed_evals)["larp_score"]
    assert mixed_score >= 30.0
    assert mixed_score <= 75.0


@pytest.mark.asyncio
async def test_roast_agent_generation():
    roast_agent = RoastAgent()
    evals = [
        {"claim_text": "Built enterprise microservices", "verdict": "UNVERIFIED"},
        {"claim_text": "Expert in Rust and Go", "verdict": "UNVERIFIED"},
    ]
    roast = await roast_agent.generate_roast(larp_score=85.0, evaluations=evals)

    assert "overall_roast" in roast
    assert "verdict_summary" in roast
    assert len(roast["overall_roast"]) > 20


def test_evaluation_hierarchy_deterministic():
    agent = EvaluationAgent()

    # 1. Direct attached repo with 0 candidate commits -> CONTRADICTED
    stolen_repo = RetrievedEvidenceChunk(
        evidence_id="ev_stolen",
        score=0.95,
        title="Repository kafka",
        content="Apache Kafka distributed engine",
        url="https://github.com/apache/kafka",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 0, "total_commit_count": 10000},
    )
    res_stolen = agent._rule_based_fallback(
        claim_text="Built the high-throughput Kafka distributed streaming broker",
        retrieved_chunks=[stolen_repo],
        category="project",
        section="projects",
        claim_meta={"attached_url": "https://github.com/apache/kafka"},
    )
    assert res_stolen["verdict"] == "CONTRADICTED"

    # 2. Direct attached link that returned 404 / failed -> CONTRADICTED
    dead_link = RetrievedEvidenceChunk(
        evidence_id="ev_dead",
        score=0.90,
        title="Hackathon Certificate",
        content="404 Not Found - Page deleted",
        url="https://drive.google.com/invalid-doc",
        evidence_type="web_page",
        meta={"status": "failed"},
    )
    res_dead = agent._rule_based_fallback(
        claim_text="Winner of National Smart India Hackathon 2024",
        retrieved_chunks=[dead_link],
        category="achievement",
        section="experience",
        claim_meta={"attached_url": "https://drive.google.com/invalid-doc"},
    )
    assert res_dead["verdict"] == "CONTRADICTED"

    # 3. Direct attached repo with tech stack contradiction (claiming PyTorch backend on pure HTML) -> CONTRADICTED
    html_repo = RetrievedEvidenceChunk(
        evidence_id="ev_html",
        score=0.95,
        title="Repository MERN",
        content="Portfolio static HTML webpage. Languages: HTML 99%, CSS 1%. Pure static frontend files only.",
        url="https://github.com/user/mern",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 10, "total_commit_count": 10},
    )
    res_tech_contra = agent._rule_based_fallback(
        claim_text="Engineered deep learning recommendation system using PyTorch and FastAPI",
        retrieved_chunks=[html_repo],
        category="project",
        section="projects",
        claim_meta={"attached_url": "https://github.com/user/mern"},
    )
    assert res_tech_contra["verdict"] == "CONTRADICTED"

    # 4. Project stem match (ElderCare matching Elderly_AI) -> SUPPORTED
    elderly_repo = RetrievedEvidenceChunk(
        evidence_id="ev_elderly",
        score=0.85,
        title="Repository Elderly_AI",
        content="Elderly AI Healthcare platform with React and Spring Boot. Candidate authored 21 commits.",
        url="https://github.com/org/Elderly_AI",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 21, "total_commit_count": 45, "repo": "Elderly_AI"},
    )
    res_stem = agent._rule_based_fallback(
        claim_text="Developed ElderCare AI Platform for elderly healthcare management",
        retrieved_chunks=[elderly_repo],
        category="project",
        section="projects",
        claim_meta={"project_name": "ElderCare AI Platform"},
    )
    assert res_stem["verdict"] == "SUPPORTED"

    # 5. Work experience proprietary employer without link, corroborated by tech stack inventory -> PARTIALLY_SUPPORTED
    tech_stack_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_stack",
        score=0.75,
        title="Candidate Verified Tech Stack Inventory",
        content="Verified Languages: Python, Dart. Verified Packages: flutter, provider, django.",
        url="https://github.com/user",
        evidence_type="github_tech_stack",
        meta={"languages": ["Dart", "Python"], "packages": ["flutter", "provider"]},
    )
    res_work = agent._rule_based_fallback(
        claim_text="Developed DiamondRock stock market app using Flutter at Quickyearning Private Limited",
        retrieved_chunks=[tech_stack_chunk],
        category="experience",
        section="experience",
        claim_meta={"project_name": "Quickyearning Private Limited"},
    )
    assert res_work["verdict"] == "PARTIALLY_SUPPORTED"

    # 6. Work experience proprietary employer with zero receipts anywhere -> UNVERIFIED
    res_work_unverified = agent._rule_based_fallback(
        claim_text="Engineered autonomous robotics navigation software in C++ and ROS",
        retrieved_chunks=[tech_stack_chunk],
        category="experience",
        section="experience",
        claim_meta={"project_name": "RoboTech Inc"},
    )
    assert res_work_unverified["verdict"] == "UNVERIFIED"


@pytest.mark.asyncio
async def test_bullshit_tabular_dataset_projects():
    agent = EvaluationAgent()

    # 1. Direct claim: XGBoost on customer churn dataset -> CONTRADICTED
    res_churn = await agent.evaluate_claim(
        claim_text="Built predictive AI engine using XGBoost and LightGBM on customer churn dataset to forecast attrition",
        category="project",
        source_text="Built predictive AI engine using XGBoost and LightGBM on customer churn dataset to forecast attrition",
        retrieved_chunks=[],
    )
    assert res_churn["verdict"] == "CONTRADICTED"
    assert "tabular" in res_churn["reasoning"].lower() or "dataset" in res_churn["reasoning"].lower()

    # 2. Linear regression on pizza sales dataset -> CONTRADICTED
    res_sales = await agent.evaluate_claim(
        claim_text="Developed machine learning sales forecasting system using linear regression on pizza sales dataset",
        category="project",
        source_text="Developed machine learning sales forecasting system using linear regression on pizza sales dataset",
        retrieved_chunks=[],
    )
    assert res_sales["verdict"] == "CONTRADICTED"

    # 3. Project claiming AI platform, but repo is a CSV dataset with Random Forest -> CONTRADICTED
    csv_repo_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_csv_repo",
        score=0.88,
        title="titanic_survivor_model",
        content="Repo: titanic_survivor_model. Files: titanic.csv, train.ipynb. Code: RandomForestClassifier, train_test_split.",
        url="https://github.com/user/titanic_survivor_model",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 10, "total_commit_count": 10},
    )
    res_repo_csv = await agent.evaluate_claim(
        claim_text="Architected predictive intelligence pipeline for survivor probability modeling",
        category="project",
        source_text="Architected predictive intelligence pipeline for survivor probability modeling",
        retrieved_chunks=[csv_repo_chunk],
    )
    assert res_repo_csv["verdict"] == "CONTRADICTED"

    # 4. Software regression testing should NOT be misclassified as tabular ML regression
    qa_repo_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_qa",
        score=0.85,
        title="ecommerce-api",
        content="Automated regression test suite using pytest and selenium",
        url="https://github.com/user/ecommerce-api",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 15, "total_commit_count": 20},
    )
    res_qa = await agent.evaluate_claim(
        claim_text="Implemented automated regression testing pipeline for backend APIs",
        category="project",
        source_text="Implemented automated regression testing pipeline for backend APIs",
        retrieved_chunks=[qa_repo_chunk],
    )
    assert res_qa["verdict"] != "CONTRADICTED"


@pytest.mark.asyncio
async def test_overplayed_toy_apps():
    agent = EvaluationAgent()

    # 1. Overplayed To-Do app with enterprise buzzwords -> CONTRADICTED
    res_todo = await agent.evaluate_claim(
        claim_text="Architected high-throughput distributed To-Do application orchestrating microservices for task synchronization",
        category="project",
        source_text="Architected high-throughput distributed To-Do application orchestrating microservices for task synchronization",
        retrieved_chunks=[],
    )
    assert res_todo["verdict"] == "CONTRADICTED"
    assert "to-do" in res_todo["reasoning"].lower()

    # 2. Overplayed Calculator app with enterprise jargon -> CONTRADICTED
    res_calc = await agent.evaluate_claim(
        claim_text="Engineered enterprise-grade Calculator platform supporting fault-tolerant arithmetic operations at scale",
        category="project",
        source_text="Engineered enterprise-grade Calculator platform supporting fault-tolerant arithmetic operations at scale",
        retrieved_chunks=[],
    )
    assert res_calc["verdict"] == "CONTRADICTED"
    assert "calculator" in res_calc["reasoning"].lower()

    # 3. Normal To-Do app with modest description against valid repo -> NOT contradicted
    todo_chunk = RetrievedEvidenceChunk(
        evidence_id="ev_todo",
        score=0.90,
        title="react-todo-app",
        content="Simple todo list built with React and Tailwind CSS",
        url="https://github.com/user/react-todo-app",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 12, "total_commit_count": 15},
    )
    res_normal_todo = await agent.evaluate_claim(
        claim_text="Built a simple To-Do app with React and Tailwind CSS",
        category="project",
        source_text="Built a simple To-Do app with React and Tailwind CSS",
        retrieved_chunks=[todo_chunk],
    )
    assert res_normal_todo["verdict"] == "SUPPORTED"


@pytest.mark.asyncio
async def test_groq_rate_limit_error_propagation():
    from unittest.mock import AsyncMock
    from backend.app.agents.claim_extractor import ClaimExtractor
    from backend.app.agents.groq_client import GroqClient, GroqRateLimitError

    mock_groq = GroqClient(api_key="mock_key")
    mock_groq.chat_completion = AsyncMock(side_effect=GroqRateLimitError("Groq 429 rate limit reached"))

    # EvaluationAgent must re-raise GroqRateLimitError
    eval_agent = EvaluationAgent(groq_client=mock_groq)
    with pytest.raises(GroqRateLimitError):
        await eval_agent.evaluate_claim(
            claim_text="Built a distributed data cache in C++",
            category="project",
            source_text="Built a distributed data cache in C++",
            retrieved_chunks=[
                RetrievedEvidenceChunk(
                    evidence_id="ev1",
                    score=0.9,
                    title="cache",
                    content="cache",
                    url="https://github.com/u/c",
                    evidence_type="github_repo",
                    meta={"candidate_commit_count": 10, "total_commit_count": 10},
                )
            ],
        )

    # ClaimExtractor must re-raise GroqRateLimitError
    claim_agent = ClaimExtractor(groq_client=mock_groq)
    with pytest.raises(GroqRateLimitError):
        await claim_agent.extract_claims("Experienced software engineer who built distributed databases")

    # RoastAgent must re-raise GroqRateLimitError
    roast_agent = RoastAgent(groq_client=mock_groq)
    with pytest.raises(GroqRateLimitError):
        await roast_agent.generate_roast(larp_score=50.0, evaluations=[], repos=[], intensity=3)


