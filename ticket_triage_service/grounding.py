from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
nltk.download("punkt")
from nltk.tokenize import sent_tokenize, word_tokenize

model = SentenceTransformer("BAAI/bge-base-en-v1.5")

def grounding_ratio(answer, contexts, threshold=0.75):
    ctx = " ".join(contexts)
    ctx_emb = model.encode(ctx, normalize_embeddings=True)

    grounded, total = 0, 0

    for sent in sent_tokenize(answer):
        tokens = word_tokenize(sent)
        total += len(tokens)

        emb = model.encode(sent, normalize_embeddings=True)
        sim = cosine_similarity([emb], [ctx_emb])[0][0]

        if sim >= threshold:
            grounded += len(tokens)

    return grounded / total if total else 0
