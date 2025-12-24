from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
nltk.download("punkt")
nltk.download('punkt_tab')
# from nltk.tokenize import sent_tokenize, word_tokenize

model = SentenceTransformer("BAAI/bge-base-en-v1.5")

import re

def split_sentences(text: str):
    """
    Lightweight sentence splitter.
    Handles ., ?, ! safely.
    """
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def tokenize_words(text: str):
    return re.findall(r"\b\w+\b", text)


def grounding_ratio(answer, contexts, threshold=0.75):
    try:
        context_texts = []
        for text, score in contexts['bm25_results']:
            context_texts.append(text)
        
        if len(context_texts)   == 0:
            return 0.0

        ctx = " ".join(context_texts)
        ctx_emb = model.encode(ctx, normalize_embeddings=True)

        grounded, total = 0, 0

        for sent in split_sentences(answer):
            tokens = tokenize_words(sent)
            total += len(tokens)

            emb = model.encode(sent, normalize_embeddings=True)
            sim = cosine_similarity([emb], [ctx_emb])[0][0]

            if sim >= threshold:
                grounded += len(tokens)

        return grounded / total if total else 0
    except Exception as e:
        print(f"Error in grounding_ratio: {e}")
        return 0.0
