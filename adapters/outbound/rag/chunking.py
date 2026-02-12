def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    if chunk_size <= 0:
        return [text]
    normalized_overlap = max(0, int(overlap))
    if normalized_overlap >= chunk_size:
        # Evita step=0 y asegura avance siempre.
        normalized_overlap = chunk_size - 1

    step = chunk_size - normalized_overlap
    chunks: list[str] = []
    for start in range(0, len(text), step):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
    return chunks
