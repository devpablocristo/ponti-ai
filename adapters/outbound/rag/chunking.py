def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    if chunk_size <= 0:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = max(end - overlap, end)
    return chunks
