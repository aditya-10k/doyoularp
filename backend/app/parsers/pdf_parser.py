import io
import re
from typing import Any, Dict, List, Optional, Set
import pypdf
from backend.app.parsers.url_extractor import (
    classify_url,
    extract_urls_from_text,
    normalize_url,
    parse_github_url,
)


class ParsedPDFResult:
    def __init__(
        self,
        raw_text: str,
        page_count: int,
        discovered_urls: List[Dict[str, Any]],
        candidate_info: Dict[str, Any],
    ):
        self.raw_text = raw_text
        self.page_count = page_count
        self.discovered_urls = discovered_urls
        self.candidate_info = candidate_info


def extract_candidate_fields(text: str) -> Dict[str, Optional[str]]:
    """Simple deterministic heuristic for name, email, and phone."""
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)

    # First non-empty line is often the candidate name
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidate_name = lines[0] if lines and len(lines[0]) < 50 else None

    return {
        "name": candidate_name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
    }


def parse_pdf_bytes(pdf_bytes: bytes) -> ParsedPDFResult:
    """
    Parses PDF bytes, inspecting both:
    1. Text layer
    2. Embedded PDF hyperlink annotations (/Annots -> /A -> /URI)
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)

    full_text_list: List[str] = []
    discovered_urls: Dict[str, Dict[str, Any]] = {}

    for page_idx, page in enumerate(reader.pages, start=1):
        # 1. Extract text
        page_text = page.extract_text() or ""
        full_text_list.append(page_text)

        # 2. Extract visible text URLs
        visible_urls = extract_urls_from_text(page_text)
        for url in visible_urls:
            if url not in discovered_urls:
                category = classify_url(url)
                gh_info = parse_github_url(url)
                discovered_urls[url] = {
                    "url": url,
                    "source": "text_layer",
                    "page_number": page_idx,
                    "category": category,
                    "github_info": gh_info,
                }

        # 3. Extract embedded PDF hyperlink annotations
        if "/Annots" in page:
            try:
                annots = page["/Annots"]
                if annots:
                    # In pypdf, annots can be an IndirectObject or Array
                    annot_list = annots.get_object() if hasattr(annots, "get_object") else annots
                    for annot in annot_list:
                        annot_obj = annot.get_object() if hasattr(annot, "get_object") else annot
                        if isinstance(annot_obj, dict) and "/A" in annot_obj:
                            action = annot_obj["/A"]
                            action_obj = action.get_object() if hasattr(action, "get_object") else action
                            if isinstance(action_obj, dict) and "/URI" in action_obj:
                                raw_uri = str(action_obj["/URI"])
                                norm_uri = normalize_url(raw_uri)
                                if norm_uri:
                                    category = classify_url(norm_uri)
                                    gh_info = parse_github_url(norm_uri)
                                    # Annotations take precedence or augment text discoveries
                                    discovered_urls[norm_uri] = {
                                        "url": norm_uri,
                                        "source": "embedded_annotation",
                                        "page_number": page_idx,
                                        "category": category,
                                        "github_info": gh_info,
                                    }
            except Exception:
                # Malformed annotations shouldn't crash the entire PDF extraction
                pass

    full_text = "\n\n".join(full_text_list)
    candidate_info = extract_candidate_fields(full_text)

    return ParsedPDFResult(
        raw_text=full_text,
        page_count=page_count,
        discovered_urls=list(discovered_urls.values()),
        candidate_info=candidate_info,
    )
