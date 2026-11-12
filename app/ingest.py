import os
from pypdf import PdfReader

def load_document_text(filepath: str) -> str:
    if filepath.endswith(".pdf"):
        reader = PdfReader(filepath)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def load_all_documents(folder: str = "documents") -> list[dict]:
    all_chunks = []
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        text = load_document_text(filepath)
        chunks = chunk_text(text)
        for chunk in chunks:
            all_chunks.append({"text": chunk, "source": filename})
    return all_chunks