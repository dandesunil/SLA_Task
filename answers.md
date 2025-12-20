1. Python Concurrency Compare asyncio, native threads, and multiprocessing for I/O‑bound vs. CPU‑bound tasks in a FastAPI microservice. Provide code fragments or pseudocode

Answer : 
### asyncio (I/O-bound, FastAPI native)

from fastapi import FastAPI
import httpx

app = FastAPI()

@app.get("/data")
async def data(query: str):
    async with httpx.AsyncClient(timeout=5) as client:
        vect_resp = await client.post("external_url", json={"q": query})
        docs = vect_resp.json()
    return {"docs": docs}


### Native Threads (blocking libraries)

from concurrent.futures import ThreadPoolExecutor

def cpu_task(n):
    total = sum(i*i for i in range(n))
    return total

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(cpu_task, 100000))
print(results)

On CPU-bound workloads, this often won’t fully utilize multicore CPUs due to the GIL.

### Multiprocessing (CPU-bound)

## This is true parallellism because Utilizes multiple cores efficiently
from concurrent.futures import ProcessPoolExecutor

def cpu_task(n):
    total = sum(i*i for i in range(n))
    return total

with ProcessPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(cpu_task, 100000))
print(results)


2. LLM Cost Modeling
Build a simple cost equation for running your triage service (Scenario II) on AWS using an open‑source model hosted on GPU‑backed EC2. Include capex vs. opex components and break‑even analysis vs. an API‑based commercial LLM.

## Managed Service Option (Recommended for most workloads):
Cost: ~$1,800/month for 10,000 chats/day at 6K tokens per chat.
Pros: No setup or GPU management, fast time-to-market, scales automatically.
Billing: Based on token consumption as detailed above.
Cons: Slightly higher marginal cost at very high-scale usage.
## Self-Hosting Option:
Cost: ~$500–700/month for entry-level cloud GPU.
Pros: Full control over model inference, potentially lower long-term cost with static usage.
Cons: Requires DevOps expertise, scaling is manual, includes power and cooling costs.
Token Cost Reference (Azure Llama 3-8B):
Input: $0.0011 per 1,000 tokens
Output: $0.00037 per 1,000 tokens


3. RAG Pipeline Explain the RAG pipeline you designed on Scenario II. Provide your reasoning for designing it like that. What would you recommend as an improvement or next steps?

Ans : User Query -> Intent Classification -> Hybrid Search -> Reranking(for relvence chunks)->LLM Call


4. RAG Evaluation Propose a quantitative framework to measure hallucination in a RAG system without human labeling. Describe the metrics.

Ans : Faithfulness = cosine_similarity of answer embeddings and context embeddings if less hallucination. we can keep threshold 75%
Ground truth using common Sentence-level grounding via embedding model
Self Reflection with llm with different prompt

5. Prompt Injection Mitigation 
Outline a layered defense strategy (code, infra, and policy) against prompt‑injection attacks.

Ans: Separation of prompts like System Prompt, User Prompt
Rule based Guardrails to sanitize the user prompt 
EX: def sanitize(query):
    blacklist = ["ignore instructions", "system prompt"]
    for word in blacklist:
        if word in query.lower():
            raise ValueError("Injection detected")

Validate reponse with pydantic model