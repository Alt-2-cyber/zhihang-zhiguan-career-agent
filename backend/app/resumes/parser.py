from pathlib import Path


def parse_resume(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        import fitz

        with fitz.open(path) as document:
            return "\n".join(page.get_text() for page in document).strip()
    if path.suffix.lower() == ".docx":
        from docx import Document

        document = Document(path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    raise ValueError("Unsupported resume format")

