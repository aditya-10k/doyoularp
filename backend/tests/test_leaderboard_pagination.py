import pytest
import httpx
from backend.app.db.session import async_session_maker
from backend.app.models.models import LeaderboardEntry, Analysis, Candidate


@pytest.mark.asyncio
async def test_leaderboard_pagination_flow(client: httpx.AsyncClient):
    async with async_session_maker() as db_session:
        for i in range(5):
            cand = Candidate(anonymous_alias=f"Pagination Cand #{i+1}")
            db_session.add(cand)
            await db_session.flush()

            analysis = Analysis(candidate_id=cand.id, status="completed")
            db_session.add(analysis)
            await db_session.flush()

            entry = LeaderboardEntry(
                analysis_id=analysis.id,
                token=f"token_test_{i}_{cand.id}",
                anonymous_alias=f"Larp Candidate #{i+1}",
                larp_score=float(90 - i * 10),
                roast=f"Roast number {i+1}",
            )
            db_session.add(entry)
        await db_session.commit()

    # Page 1 (limit 2, offset 0)
    resp1 = await client.get("/api/v1/leaderboard?limit=2&offset=0")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["leaderboard"]) == 2
    assert data1["leaderboard"][0]["rank"] == 1
    assert data1["leaderboard"][1]["rank"] == 2
    assert data1["has_more"] is True
    assert data1["total"] >= 5

    # Page 2 (limit 2, offset 2)
    resp2 = await client.get("/api/v1/leaderboard?limit=2&offset=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["leaderboard"]) == 2
    assert data2["leaderboard"][0]["rank"] == 3
    assert data2["leaderboard"][1]["rank"] == 4
    assert data2["has_more"] is True
