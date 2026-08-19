import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
from backend.app.parsers.pdf_parser import parse_pdf_bytes, extract_candidate_fields


def create_test_pdf_with_annotations() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_uri(
        page_number=0,
        uri="https://github.com/hidden-annotation-user",
        rect=(100, 100, 200, 120),
    )

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_pdf_embedded_annotation_extraction():
    pdf_bytes = create_test_pdf_with_annotations()
    result = parse_pdf_bytes(pdf_bytes)

    assert result.page_count == 1
    urls = [u["url"] for u in result.discovered_urls]
    assert "https://github.com/hidden-annotation-user" in urls

    annot_item = next(u for u in result.discovered_urls if u["url"] == "https://github.com/hidden-annotation-user")
    assert annot_item["source"] == "embedded_annotation"
    assert annot_item["category"] == "github"
    assert annot_item["github_info"]["username"] == "hidden-annotation-user"


def test_candidate_fields_extraction():
    sample_text = """
    Alex Rivera
    alex.rivera@example.com
    (555) 234-5678
    Staff Software Engineer
    """
    fields = extract_candidate_fields(sample_text)
    assert fields["name"] == "Alex Rivera"
    assert fields["email"] == "alex.rivera@example.com"
    assert fields["phone"] == "(555) 234-5678"
