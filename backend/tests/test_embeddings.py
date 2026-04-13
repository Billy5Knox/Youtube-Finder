import numpy as np
from app.embeddings import EmbeddingService


def test_embed_single_text():
    service = EmbeddingService()
    vector = service.embed("How to build a REST API with FastAPI")

    assert isinstance(vector, np.ndarray)
    assert vector.shape == (384,)  # all-MiniLM-L6-v2 output dimension
    assert not np.all(vector == 0)


def test_embed_batch():
    service = EmbeddingService()
    texts = [
        "Python tutorial for beginners",
        "Advanced CSS grid layouts",
        "Machine learning with PyTorch",
    ]
    vectors = service.embed_batch(texts)

    assert len(vectors) == 3
    assert all(v.shape == (384,) for v in vectors)


def test_cosine_similarity():
    service = EmbeddingService()
    v1 = service.embed("Python programming tutorial")
    v2 = service.embed("Learn Python coding")
    v3 = service.embed("Chocolate cake recipe")

    sim_related = service.cosine_similarity(v1, v2)
    sim_unrelated = service.cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
