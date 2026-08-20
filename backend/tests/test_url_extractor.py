import pytest
from backend.app.parsers.url_extractor import (
    classify_url,
    extract_urls_from_text,
    normalize_url,
    parse_github_url,
)


def test_normalize_url():
    assert normalize_url("github.com/torvalds") == "https://github.com/torvalds"
    assert normalize_url("https://github.com/torvalds/") == "https://github.com/torvalds"
    assert normalize_url("https://www.github.com/torvalds") == "https://github.com/torvalds"
    assert normalize_url("http://example.com/foo/bar/") == "http://example.com/foo/bar"


def test_parse_github_url():
    # Profile
    prof = parse_github_url("https://github.com/octocat")
    assert prof is not None
    assert prof["type"] == "github_profile"
    assert prof["username"] == "octocat"

    # Repo
    repo = parse_github_url("https://github.com/octocat/Hello-World")
    assert repo is not None
    assert repo["type"] == "github_repo"
    assert repo["username"] == "octocat"
    assert repo["repo"] == "Hello-World"

    # Reserved keywords should not be considered user profiles
    assert parse_github_url("https://github.com/about") is None
    assert parse_github_url("https://github.com/features") is None
    assert parse_github_url("https://github.com/pricing") is None

    # Non-github
    assert parse_github_url("https://gitlab.com/octocat") is None


def test_classify_url():
    assert classify_url("https://github.com/octocat") == "github"
    assert classify_url("https://linkedin.com/in/octocat") == "linkedin"
    assert classify_url("https://apps.apple.com/app/id123456") == "app_store"
    assert classify_url("https://play.google.com/store/apps/details?id=com.app") == "play_store"
    assert classify_url("https://octocat.github.io") == "portfolio"
    assert classify_url("https://octocat.vercel.app") == "portfolio"
    assert classify_url("https://mycoolproject.com") == "project"


def test_extract_urls_from_text():
    sample_text = """
    Check out my portfolio at https://johndoe.dev or my code at github.com/johndoe.
    Connect on linkedin.com/in/johndoe.
    """
    urls = extract_urls_from_text(sample_text)
    assert "https://johndoe.dev" in urls
    assert "https://github.com/johndoe" in urls
    assert "https://linkedin.com/in/johndoe" in urls
