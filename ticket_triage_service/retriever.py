import json
import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

ARTIFACTS = "../embedding_service/artifacts"

class HybridRetriever:
    def __init__(self):
        self.index = faiss.read_index(f"{ARTIFACTS}/faiss.index")
        self.texts = json.loads(open(f"{ARTIFACTS}/texts.json").read())

        self.bm25 = BM25Okapi([t.lower().split() for t in self.texts])
        self.model = SentenceTransformer("BAAI/bge-base-en-v1.5")

    def search(self, query, k=5):
        # Semantic
        q_emb = self.model.encode(
            f"Represent this sentence for searching relevant passages: {query}",
            normalize_embeddings=True
        ).astype("float32")

        _, ids = self.index.search(np.array([q_emb]), k)

        # Lexical
        bm25_scores = self.bm25.get_scores(query.lower().split())
        bm25_scores /= max(bm25_scores.max(), 1e-6)

        scores = {}
        for i in ids[0]:
            scores[i] = scores.get(i, 0) + 1.0
        for i, s in enumerate(bm25_scores):
            scores[i] = scores.get(i, 0) + 0.3 * s

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self.texts[i] for i, _ in ranked[:k]]
