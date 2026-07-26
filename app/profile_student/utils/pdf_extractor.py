import pymupdf4llm


def extract_pdf_markdown(file_bytes: bytes) -> str | None:
    try:
        md_text = pymupdf4llm.to_markdown(file_bytes)
        return md_text.strip() if md_text else None
    except Exception:
        return None
