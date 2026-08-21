from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
import httpx
from backend.app.core.config import settings
from backend.app.core.security import validate_url_for_ssrf


class WebCollector:
    def __init__(self):
        self.headers = {
            "User-Agent": "LARP-Checker-Web-Evidence/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def fetch_page(self, url: str) -> Dict[str, Any]:
        """
        Fetches and extracts clean textual evidence from a public webpage.
        Applies SSRF validation before network call.
        """
        try:
            # 1. SSRF Safety Check
            safe_url = validate_url_for_ssrf(url)
        except ValueError as e:
            return {
                "url": url,
                "status": "ssrf_blocked",
                "error": str(e),
                "title": None,
                "content": None,
            }

        try:
            async with httpx.AsyncClient(follow_redirects=True, max_redirects=3) as client:
                resp = await client.get(
                    safe_url,
                    headers=self.headers,
                    timeout=5.0,
                )

                if resp.status_code != 200:
                    return {
                        "url": url,
                        "status": f"http_{resp.status_code}",
                        "error": f"HTTP status {resp.status_code}",
                        "title": None,
                        "content": None,
                    }

                # Ensure HTML content
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return {
                        "url": url,
                        "status": "unsupported_media_type",
                        "error": f"Content-Type not HTML: {content_type}",
                        "title": None,
                        "content": None,
                    }

                # Parse HTML
                soup = BeautifulSoup(resp.text[:500000], "html.parser")

                # Remove noise elements
                for element in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
                    element.decompose()

                title = soup.title.string.strip() if soup.title and soup.title.string else ""

                headings = []
                for h in soup.find_all(["h1", "h2", "h3"]):
                    h_text = h.get_text(strip=True)
                    if h_text and len(h_text) < 200:
                        headings.append(h_text)

                text = soup.get_text(separator=" ", strip=True)
                # Cap extracted text length
                clean_text = " ".join(text.split())[:8000]

                return {
                    "url": url,
                    "status": "collected",
                    "title": title[:200] if title else "Webpage",
                    "headings": headings[:15],
                    "content": clean_text,
                    "error": None,
                }
        except Exception as e:
            return {
                "url": url,
                "status": "fetch_failed",
                "error": str(e),
                "title": None,
                "content": None,
            }
