import random


def embed_texts(texts: list[str], dim: int) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for text in texts:
        seed = sum(ord(c) for c in text)
        rng = random.Random(seed)
        embeddings.append([rng.random() for _ in range(dim)])
    return embeddings
