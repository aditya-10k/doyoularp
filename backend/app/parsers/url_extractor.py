import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, urlunparse


GITHUB_RESERVED_NAMES = {
    "about", "features", "pricing", "login", "join", "enterprise",
    "topics", "explore", "trending", "collections", "events", "readme",
    "contact", "security", "customer-stories", "sponsors", "settings",
    "notifications", "pulls", "issues", "marketplace", "orgs"
}

# Regex to find visible URLs in text
URL_REGEX = re.compile(
    r'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?«»“”‘’]))'
)


def normalize_url(url: str) -> str:
    """
    Normalizes a URL:
    - Prepend https:// if protocol is missing
    - Lowercase hostname
    - Strip trailing slashes (except root)
    - Remove fragment and common tracking parameters
    """
    url = url.strip().strip("'\"()[]{}<>.,;")
    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Remove www. prefix if present
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Clean path: remove trailing slash if not root
        path = parsed.path
        if path.endswith("/") and len(path) > 1:
            path = path.rstrip("/")

        # Rebuild without fragments
        normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
        return normalized
    except Exception:
        return url


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parses a GitHub URL. Returns a dict with type ('profile' or 'repo'),
    username, and optional repo name. Returns None if not a valid GitHub user/repo.
    """
    normalized = normalize_url(url)
    parsed = urlparse(normalized)

    if "github.com" not in parsed.netloc:
        return None

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        return None

    first = path_parts[0].lower()
    if first in GITHUB_RESERVED_NAMES:
        return None

    if len(path_parts) == 1:
        return {
            "type": "github_profile",
            "username": path_parts[0],
            "url": f"https://github.com/{path_parts[0]}",
        }
    elif len(path_parts) >= 2:
        return {
            "type": "github_repo",
            "username": path_parts[0],
            "repo": path_parts[1],
            "url": f"https://github.com/{path_parts[0]}/{path_parts[1]}",
        }

    return None


def classify_url(url: str) -> str:
    """
    Classifies URL into categories:
    - github
    - linkedin
    - app_store
    - play_store
    - portfolio
    - project
    - other
    """
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    domain = parsed.netloc.lower()

    if "github.com" in domain:
        return "github"
    if "linkedin.com" in domain:
        return "linkedin"
    if "apps.apple.com" in domain:
        return "app_store"
    if "play.google.com" in domain:
        return "play_store"
    if any(p in domain for p in ["github.io", "vercel.app", "netlify.app", "pages.dev", "portfolio", "me", "dev"]):
        return "portfolio"
    if domain:
        return "project"
    return "other"


def extract_urls_from_text(text: str) -> List[str]:
    """Finds all URL candidates in raw text and normalizes them."""
    matches = URL_REGEX.findall(text)
    urls: List[str] = []
    seen: Set[str] = set()

    for match in matches:
        raw_url = match[0] if isinstance(match, tuple) else match
        norm = normalize_url(raw_url)
        if norm and norm not in seen:
            seen.add(norm)
            urls.append(norm)

    return urls
