import json
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict
import torch
from sentence_transformers import SentenceTransformer
from typing import List
import faiss
import numpy as np
from rank_bm25 import BM25Okapi


class DocumentLoader:
    def __init__(self, json_path: str, chunk_size=300, overlap=50):
        self.json_path = json_path
        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def clean_html(text: str) -> str:
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(" ", strip=True)

    def chunk_text(self, text: str) -> List[str]:
        words = text.split()
        chunks = []

        for i in range(0, len(words), self.chunk_size - self.overlap):
            chunk = words[i:i + self.chunk_size]
            if len(chunk) > 50:
                chunks.append(" ".join(chunk))

        return chunks

    def load(self) -> List[Dict]:
        data = json.loads(Path(self.json_path).read_text())
        docs = []

        for product in data.get("products", []):
            base_meta = {
                "product": product.get("product-name"),
                "title": product.get("title"),
                "version": product.get("sub-title")
            }

            texts = [product.get("content", "")]
            for sec in product.get("sections", {}).values():
                texts.append(sec.get("content", ""))

            for text in texts:
                clean = self.clean_html(text)
                for chunk in self.chunk_text(clean):
                    docs.append({
                        "text": chunk,
                        "metadata": base_meta
                    })

        return docs
    
class EmbeddingModel:
    def __init__(self, model_name="BAAI/bge-base-en-v1.5"):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)

    def get_embedding_model(self):
        return self.model

    def embed(self, texts: List[str], batch_size=32) -> np.ndarray:
        return self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=True
        )


class FaissIndex:
    def __init__(self, embedding_model: EmbeddingModel):
        self.embedding_model = embedding_model
        self.index = None
        self.texts = []

    def build(self, docs: List[Dict]):
        self.texts = [d["text"] for d in docs]
        embeddings = self.embedding_model.embed(self.texts)

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

    def search(self, query: str, k=5):
        q_emb = self.embedding_model.embed([
            f"Represent this sentence for searching relevant passages: {query}"
        ])
        _, ids = self.index.search(q_emb, k)
        return ids[0]
    
class BM25Index:
    def __init__(self, texts: List[str]):
        tokenized = [t.lower().split() for t in texts]
        self.bm25 = BM25Okapi(tokenized)
        self.texts = texts

    def search(self, query: str):
        return self.bm25.get_scores(query.lower().split())
    


class HybridRetriever:
    def __init__(self, faiss_index: FaissIndex, bm25_index: BM25Index):
        self.faiss = faiss_index
        self.bm25 = bm25_index
        self.texts = faiss_index.texts

    def search(self, query: str, k=5):
        bm25_scores = self.bm25.search(query)
        faiss_ids = self.faiss.search(query, k)

        scores = {}

        # Semantic boost
        for idx in faiss_ids:
            scores[idx] = scores.get(idx, 0) + 1.0

        # Lexical contribution
        for i, score in enumerate(bm25_scores):
            scores[i] = scores.get(i, 0) + 0.3 * score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self.texts[i] for i, _ in ranked[:k]]
