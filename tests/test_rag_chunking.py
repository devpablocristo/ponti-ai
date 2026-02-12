from adapters.outbound.rag.chunking import chunk_text


def test_chunk_text_applies_overlap() -> None:
    text = "abcdefghij"
    chunks = chunk_text(text, chunk_size=5, overlap=2)
    assert chunks == ["abcde", "defgh", "ghij"]


def test_chunk_text_handles_overlap_greater_than_chunk_size() -> None:
    text = "abcdef"
    chunks = chunk_text(text, chunk_size=3, overlap=10)
    assert chunks == ["abc", "bcd", "cde", "def"]


def test_chunk_text_handles_negative_overlap() -> None:
    text = "abcdefgh"
    chunks = chunk_text(text, chunk_size=3, overlap=-5)
    assert chunks == ["abc", "def", "gh"]
