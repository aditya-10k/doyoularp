from typing import Any, Dict, List, Optional


def calculate_larp_score(
    evaluations: List[Dict[str, Any]],
    repositories: Optional[List[Dict[str, Any]]] = None,
    has_github: bool = True,
) -> Dict[str, Any]:
    """
    Computes an aggressive, skeptical LARP Score between 0.0 and 100.0.
    - Heavily penalizes unverified and contradicted claims.
    - Gives higher weight to Project & Experience claims over simple skill mentions.
    - Single-match or incidental skills (PARTIALLY_SUPPORTED) incur real penalties.
    - Contradictions trigger severe flat penalties and high minimum floors.
    - Missing GitHub link triggers maximum phantom penalties and 92.5+ score floor.
    """
    if not evaluations:
        return {
            "larp_score": 50.0,
            "metrics": {
                "total_claims": 0,
                "supported": 0,
                "partially_supported": 0,
                "unverified": 0,
                "contradicted": 0,
            },
        }

    total = len(evaluations)
    supported = sum(1 for e in evaluations if e.get("verdict") == "SUPPORTED")
    partially_supported = sum(1 for e in evaluations if e.get("verdict") == "PARTIALLY_SUPPORTED")
    unverified = sum(1 for e in evaluations if e.get("verdict") == "UNVERIFIED")
    contradicted = sum(1 for e in evaluations if e.get("verdict") == "CONTRADICTED")

    # Weighted claim calculation: Project and Experience claims carry 1.8x stakes
    total_weight = 0.0
    contra_weight = 0.0
    unver_weight = 0.0
    part_weight = 0.0
    sup_weight = 0.0

    for e in evaluations:
        cat = (e.get("category") or "").lower()
        sec = (e.get("section") or "").lower()
        is_major = cat in ("project", "experience", "achievement") or sec in ("projects", "experience", "work_experience")
        w = 1.8 if is_major else 1.0

        total_weight += w
        v = e.get("verdict")
        if v == "CONTRADICTED":
            contra_weight += w
        elif v == "UNVERIFIED":
            unver_weight += w
        elif v == "PARTIALLY_SUPPORTED":
            part_weight += w
        elif v == "SUPPORTED":
            sup_weight += w

    if total_weight == 0:
        total_weight = 1.0

    contra_ratio = contra_weight / total_weight
    unver_ratio = unver_weight / total_weight
    part_ratio = part_weight / total_weight
    sup_ratio = sup_weight / total_weight

    # 1. Contradiction / Fraud Penalty (milded down: proportional rather than extreme flat hit)
    contra_penalty = 0.0
    if contradicted > 0:
        contra_penalty = 10.0 + min(15.0, (contradicted - 1) * 5.0)

    # 2. Unverified Ratio Escalation (based on ratio rather than arbitrary raw counts)
    unverified_penalty = 0.0
    if unver_ratio >= 0.7:
        unverified_penalty = 15.0
    elif unver_ratio >= 0.5:
        unverified_penalty = 10.0
    elif unver_ratio >= 0.35:
        unverified_penalty = 5.0

    # 3. Ownership Mismatch Penalty
    ownership_penalty = 0.0
    if repositories:
        zero_commit_repos = sum(
            1 for r in repositories
            if (r.get("total_commit_count", 0) > 5 and r.get("candidate_commit_count", 0) == 0)
        )
        if zero_commit_repos > 0:
            ownership_penalty = min(20.0, zero_commit_repos * 10.0)

    # 4. Zero Receipt Escalation
    zero_receipt_penalty = 0.0
    if total > 0 and supported == 0 and partially_supported == 0:
        zero_receipt_penalty = 25.0
    elif repositories is not None and len(repositories) == 0:
        zero_receipt_penalty = 15.0

    # 5. Missing GitHub Escalation (Phantom profile with zero repository provenance)
    missing_github_penalty = 0.0
    if not has_github:
        missing_github_penalty = 35.0

    # Base formula with milded coefficients
    base_score = (
        (contra_ratio * 80.0)
        + (unver_ratio * 50.0)
        + (part_ratio * 15.0)
        + contra_penalty
        + unverified_penalty
        + ownership_penalty
        + zero_receipt_penalty
        + missing_github_penalty
    )

    # Credibility Discount: rewards verified work proportionally
    verified_ratio = (sup_weight + (0.5 * part_weight)) / total_weight
    if contradicted > 1:
        credibility_discount = min(8.0, verified_ratio * 10.0)
    elif contradicted == 1:
        credibility_discount = min(15.0, verified_ratio * 18.0)
    else:
        credibility_discount = verified_ratio * 22.0

    raw_score = base_score - credibility_discount

    # Minimum Floors: Only applied when fraud or unverified claims dominate the resume
    if not has_github:
        raw_score = max(raw_score, 92.5)
    elif contra_ratio >= 0.35:
        raw_score = max(raw_score, 55.0)
    elif contra_ratio >= 0.2:
        raw_score = max(raw_score, 35.0)
    elif unver_ratio >= 0.8:
        raw_score = max(raw_score, 50.0)

    final_score = max(0.0, min(100.0, round(raw_score, 1)))

    return {
        "larp_score": final_score,
        "metrics": {
            "total_claims": total,
            "supported": supported,
            "partially_supported": partially_supported,
            "unverified": unverified,
            "contradicted": contradicted,
            "ownership_penalty": ownership_penalty,
            "zero_receipt_penalty": zero_receipt_penalty,
            "missing_github_penalty": missing_github_penalty,
            "contra_penalty": contra_penalty,
            "multi_unverified_penalty": unverified_penalty,
        },
    }
