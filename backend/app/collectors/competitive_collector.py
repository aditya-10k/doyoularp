import logging
from typing import Any, Dict, Optional
import httpx
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class CompetitiveCollector:
    """
    Collector for competitive programming profiles:
    - Codeforces: Official free REST API (zero authentication)
    - LeetCode: Frontend public GraphQL API (zero authentication)
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "LARP-Checker-Evidence-Collector/1.0 (https://doyoularp.com)",
            "Accept": "application/json",
        }
        self.lc_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://leetcode.com",
        }

    async def fetch_codeforces_evidence(self, handle: str) -> Optional[Dict[str, Any]]:
        """
        Fetches public profile, ratings, and rank from Codeforces REST API.
        Endpoint: https://codeforces.com/api/user.info?handles={handle}
        """
        clean_handle = handle.strip().lstrip("@")
        if not clean_handle:
            return None

        url = f"https://codeforces.com/api/user.info?handles={clean_handle}"
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code != 200:
                    logger.warning(f"Codeforces lookup for {clean_handle} returned {resp.status_code}")
                    return {
                        "platform": "Codeforces",
                        "handle": clean_handle,
                        "status": "not_found",
                        "url": f"https://codeforces.com/profile/{clean_handle}",
                    }

                data = resp.json()
                if data.get("status") != "OK" or not data.get("result"):
                    return {
                        "platform": "Codeforces",
                        "handle": clean_handle,
                        "status": "not_found",
                        "url": f"https://codeforces.com/profile/{clean_handle}",
                    }

                user = data["result"][0]
                rank = user.get("rank", "unrated")
                max_rank = user.get("maxRank", "unrated")
                current_rating = user.get("rating", 0)
                peak_rating = user.get("maxRating", 0)
                contribution = user.get("contribution", 0)

                summary = (
                    f"Verified Codeforces Profile for '{clean_handle}':\n"
                    f"- Current Rank: {rank.title()} ({current_rating} rating)\n"
                    f"- Peak Rank: {max_rank.title()} ({peak_rating} max rating)\n"
                    f"- Community Contribution: {contribution}\n"
                    f"- Profile URL: https://codeforces.com/profile/{clean_handle}"
                )

                return {
                    "platform": "Codeforces",
                    "handle": clean_handle,
                    "status": "collected",
                    "rank": rank,
                    "max_rank": max_rank,
                    "current_rating": current_rating,
                    "peak_rating": peak_rating,
                    "contribution": contribution,
                    "url": f"https://codeforces.com/profile/{clean_handle}",
                    "summary": summary,
                }
        except Exception as e:
            logger.warning(f"Failed to fetch Codeforces profile for {clean_handle}: {e}")
            return {
                "platform": "Codeforces",
                "handle": clean_handle,
                "status": "fetch_failed",
                "error": str(e),
                "url": f"https://codeforces.com/profile/{clean_handle}",
            }

    async def fetch_leetcode_evidence(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetches public problem solving statistics, contest rating, and badges from LeetCode GraphQL API.
        Endpoint: https://leetcode.com/graphql
        """
        clean_user = username.strip().lstrip("@")
        if not clean_user:
            return None

        query = """
        query getUserProfile($username: String!) {
          matchedUser(username: $username) {
            username
            submitStatsGlobal {
              acSubmissionNum {
                difficulty
                count
              }
            }
            profile {
              ranking
              reputation
            }
          }
          userContestRanking(username: $username) {
            rating
            topPercentage
            globalRanking
            badge {
              name
            }
          }
        }
        """

        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    "https://leetcode.com/graphql",
                    json={"query": query, "variables": {"username": clean_user}},
                    headers=self.lc_headers,
                )
                if resp.status_code != 200:
                    logger.warning(f"LeetCode lookup for {clean_user} returned {resp.status_code}")
                    return {
                        "platform": "LeetCode",
                        "username": clean_user,
                        "status": "not_found",
                        "url": f"https://leetcode.com/{clean_user}",
                    }

                body = resp.json()
                data = body.get("data", {})
                matched_user = data.get("matchedUser")
                if not matched_user:
                    return {
                        "platform": "LeetCode",
                        "username": clean_user,
                        "status": "not_found",
                        "url": f"https://leetcode.com/{clean_user}",
                    }

                # Extract solved difficulties
                ac_list = matched_user.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
                solved_map = {
                    item.get("difficulty", "").lower(): item.get("count", 0)
                    for item in ac_list
                }
                total_solved = solved_map.get("all", 0)
                easy_solved = solved_map.get("easy", 0)
                medium_solved = solved_map.get("medium", 0)
                hard_solved = solved_map.get("hard", 0)

                profile_info = matched_user.get("profile", {}) or {}
                global_ranking = profile_info.get("ranking")

                contest_info = data.get("userContestRanking") or {}
                contest_rating = round(contest_info.get("rating", 0.0), 1)
                contest_top_pct = contest_info.get("topPercentage")
                badge_info = contest_info.get("badge")
                badge_name = badge_info.get("name") if badge_info else None

                summary = (
                    f"Verified LeetCode Profile for '{clean_user}':\n"
                    f"- Total Problems Solved: {total_solved} (Easy: {easy_solved}, Medium: {medium_solved}, Hard: {hard_solved})\n"
                    f"- Global Ranking: #{global_ranking if global_ranking else 'Unranked'}\n"
                    f"- Contest Rating: {contest_rating if contest_rating > 0 else 'Unrated'}"
                    + (f" (Top {contest_top_pct}% globally)" if contest_top_pct else "")
                    + (f"\n- Badge: {badge_name}" if badge_name else "")
                    + f"\n- Profile URL: https://leetcode.com/{clean_user}"
                )

                return {
                    "platform": "LeetCode",
                    "username": clean_user,
                    "status": "collected",
                    "total_solved": total_solved,
                    "easy_solved": easy_solved,
                    "medium_solved": medium_solved,
                    "hard_solved": hard_solved,
                    "global_ranking": global_ranking,
                    "contest_rating": contest_rating,
                    "contest_top_pct": contest_top_pct,
                    "badge": badge_name,
                    "url": f"https://leetcode.com/{clean_user}",
                    "summary": summary,
                }
        except Exception as e:
            logger.warning(f"Failed to fetch LeetCode profile for {clean_user}: {e}")
            return {
                "platform": "LeetCode",
                "username": clean_user,
                "status": "fetch_failed",
                "error": str(e),
                "url": f"https://leetcode.com/{clean_user}",
            }
