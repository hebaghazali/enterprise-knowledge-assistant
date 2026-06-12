import io

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def extract_text(content: bytes, extension: str) -> str:
    ext = extension.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if ext in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace")
    return _extract_pdf_text(content)


def _extract_pdf_text(content: bytes) -> str:
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text.strip())
        return "\n\n".join(pages)
    except Exception as exc:
        raise ValueError(f"Failed to extract PDF text: {exc}") from exc
