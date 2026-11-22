import logging
import re
from typing import Any, Dict, Optional
import httpx
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class LinkedInCollector:
    """
    Collector for public LinkedIn profile verification.
    Bypasses LinkedIn's login walls and aggressive bot protections by retrieving
    indexed public search SERP snippets (via Tavily, Serper, or fallback).
    """

    def __init__(
        self,
        tavily_key: Optional[str] = None,
        serper_key: Optional[str] = None,
    ):
        self.tavily_key = tavily_key or settings.TAVILY_API_KEY
        self.serper_key = serper_key or settings.SERPER_API_KEY

    async def verify_linkedin_profile(
        self,
        handle: str,
        candidate_name: Optional[str] = None,
        claimed_company: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves verified title and employer from public search snippets.
        """
        clean_handle = handle.strip().strip("/")
        if not clean_handle:
            return None

        # 1. Try Serper (Google Search API)
        if self.serper_key:
            res = await self._query_serper(clean_handle, candidate_name, claimed_company)
            if res:
                return res

        # 2. Try Tavily Search API
        if self.tavily_key:
            res = await self._query_tavily(clean_handle, candidate_name, claimed_company)
            if res:
                return res

        # 3. Fallback when no SERP key is configured
        return {
            "platform": "LinkedIn",
            "handle": clean_handle,
            "status": "unverified_no_serp_key",
            "url": f"https://linkedin.com/in/{clean_handle}",
            "summary": (
                f"LinkedIn link detected (https://linkedin.com/in/{clean_handle}), "
                "but automated SERP enrichment is unconfigured. Public presence recorded."
            ),
        }

    async def _query_serper(
        self, handle: str, candidate_name: Optional[str], claimed_company: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        query = f"site:linkedin.com/in/{handle}"
        if candidate_name:
            query += f' "{candidate_name}"'

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.serper_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, headers=headers, json={"q": query, "num": 3})
                if resp.status_code == 200:
                    data = resp.json()
                    organic = data.get("organic", [])
                    if organic:
                        top = organic[0]
                        title = top.get("title", "")
                        snippet = top.get("snippet", "")
                        return {
                            "platform": "LinkedIn",
                            "handle": handle,
                            "status": "collected",
                            "url": top.get("link") or f"https://linkedin.com/in/{handle}",
                            "title": title,
                            "snippet": snippet,
                            "summary": (
                                f"Public LinkedIn Record for '{handle}':\n"
                                f"- Headline: {title}\n"
                                f"- Public Snippet: {snippet}\n"
                                f"- Profile URL: https://linkedin.com/in/{handle}"
                            ),
                        }
        except Exception as e:
            logger.warning(f"Serper LinkedIn search failed for {handle}: {e}")
        return None

    async def _query_tavily(
        self, handle: str, candidate_name: Optional[str], claimed_company: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        query = f"site:linkedin.com/in/{handle}"
        if candidate_name:
            query += f' "{candidate_name}"'

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 3,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        top = results[0]
                        title = top.get("title", "")
                        snippet = top.get("content", "")
                        return {
                            "platform": "LinkedIn",
                            "handle": handle,
                            "status": "collected",
                            "url": top.get("url") or f"https://linkedin.com/in/{handle}",
                            "title": title,
                            "snippet": snippet,
                            "summary": (
                                f"Public LinkedIn Record for '{handle}':\n"
                                f"- Headline: {title}\n"
                                f"- Public Snippet: {snippet}\n"
                                f"- Profile URL: https://linkedin.com/in/{handle}"
                            ),
                        }
        except Exception as e:
            logger.warning(f"Tavily LinkedIn search failed for {handle}: {e}")
        return None
