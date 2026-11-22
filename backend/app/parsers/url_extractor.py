import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, urlunparse


GITHUB_RESERVED_NAMES = {
    "about", "features", "pricing", "login", "join", "enterprise",
    "topics", "explore", "trending", "collections", "events", "readme",
    "contact", "security", "customer-stories", "sponsors", "settings",
    "notifications", "pulls", "issues", "marketplace", "orgs"
}

LEETCODE_RESERVED = {
    "problems", "contest", "discuss", "explore", "subscribe", "developer",
    "assessment", "company", "tag", "problemset", "submissions", "leaderboard"
}

CODEFORCES_RESERVED = {
    "problemset", "contests", "gym", "groups", "ratings", "edu", "api",
    "calendar", "help", "register", "enter", "favourite", "spectator"
}

LINKEDIN_RESERVED = {
    "jobs", "feed", "learning", "messaging", "notifications", "company",
    "school", "pulse", "posts", "showcase", "help", "settings"
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


def parse_leetcode_url(url: str) -> Optional[Dict[str, str]]:
    """Parses a LeetCode URL, extracting the username handle."""
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    if "leetcode.com" not in parsed.netloc:
        return None

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        return None

    username = path_parts[1] if (path_parts[0] == "u" and len(path_parts) > 1) else path_parts[0]
    if username.lower() in LEETCODE_RESERVED:
        return None

    return {
        "type": "leetcode_profile",
        "username": username,
        "url": f"https://leetcode.com/{username}",
    }


def parse_codeforces_url(url: str) -> Optional[Dict[str, str]]:
    """Parses a Codeforces URL, extracting the handle."""
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    if "codeforces.com" not in parsed.netloc:
        return None

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        return None

    handle = path_parts[1] if (path_parts[0] == "profile" and len(path_parts) > 1) else path_parts[0]
    if handle.lower() in CODEFORCES_RESERVED:
        return None

    return {
        "type": "codeforces_profile",
        "handle": handle,
        "url": f"https://codeforces.com/profile/{handle}",
    }


def parse_linkedin_url(url: str) -> Optional[Dict[str, str]]:
    """Parses a LinkedIn URL, extracting the vanity handle."""
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    if "linkedin.com" not in parsed.netloc:
        return None

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if not path_parts:
        return None

    handle = path_parts[1] if (path_parts[0] == "in" and len(path_parts) > 1) else path_parts[0]
    if handle.lower() in LINKEDIN_RESERVED:
        return None

    return {
        "type": "linkedin_profile",
        "handle": handle,
        "url": f"https://linkedin.com/in/{handle}",
    }


def classify_url(url: str) -> str:
    """
    Classifies URL into categories:
    - github
    - leetcode
    - codeforces
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
    if "leetcode.com" in domain:
        return "leetcode"
    if "codeforces.com" in domain:
        return "codeforces"
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


def extract_profile_handles_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Detects profile handles in plain resume text (e.g., 'LeetCode: john_doe', 'Codeforces: @speedcoder')
    even when no explicit hyperlink was attached.
    """
    results: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()

    # LeetCode pattern
    lc_matches = re.finditer(r'(?i)\bleetcode(?:\.com)?\s*[:/@\-]\s*@?([a-zA-Z0-9_\-]{3,30})\b', text)
    for m in lc_matches:
        u = m.group(1)
        if u.lower() not in LEETCODE_RESERVED:
            full_url = f"https://leetcode.com/{u}"
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                results.append({
                    "url": full_url,
                    "category": "leetcode",
                    "source": "text_handle_match",
                    "leetcode_info": {"type": "leetcode_profile", "username": u, "url": full_url},
                })

    # Codeforces pattern
    cf_matches = re.finditer(r'(?i)\bcodeforces(?:\.com)?\s*[:/@\-]\s*@?([a-zA-Z0-9_\-]{3,30})\b', text)
    for m in cf_matches:
        h = m.group(1)
        if h.lower() not in CODEFORCES_RESERVED:
            full_url = f"https://codeforces.com/profile/{h}"
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                results.append({
                    "url": full_url,
                    "category": "codeforces",
                    "source": "text_handle_match",
                    "codeforces_info": {"type": "codeforces_profile", "handle": h, "url": full_url},
                })

    return results


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
