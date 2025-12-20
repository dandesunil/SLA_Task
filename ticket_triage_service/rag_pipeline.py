"""
Complete RAG Pipeline Implementation
Uses existing embeddings system and integrates with LLM for response generation
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from typing import List, Dict, Optional
import json
from pathlib import Path

# Import existing embeddings system
from ticket_triage_service.embeddings import (
    EmbeddingModel, 
    DocumentLoader, 
    FaissIndex, 
    BM25Index, 
    HybridRetriever
)
from app.config import settings

from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class PromptIntentClassifier:
    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli"
    ):
        
        try:
            # Use zero-shot classification pipeline
            self.classifier = pipeline(
                task="zero-shot-classification",
                model=model_name,
                token=settings.HUGGINGFACE_API_KEY if settings.HUGGINGFACE_API_KEY else None
            )
        except Exception as e:
            print(f"Error loading model {model_name}: {e}")
            # Fallback to a simpler model
            fallback_model = "valhalla/distilbart-mnli-12-1"
            self.classifier = pipeline(
                task="zero-shot-classification",
                model=fallback_model,
                token=settings.HUGGINGFACE_API_KEY if settings.HUGGINGFACE_API_KEY else None
            )

    def classify(self, query: str, intents: list[str]):
        """
        Returns best intent and confidence
        """
        try:
            result = self.classifier(
                query,
                candidate_labels=intents,
                multi_label=False
            )

            return {
                "intent": result["labels"][0],
                "confidence": round(result["scores"][0], 4),
                "all_scores": dict(zip(result["labels"], result["scores"]))
            }
        except Exception as e:
            # Return a default response if classification fails
            return {
                "intent": intents[0] if intents else "general help",
                "confidence": 0.0,
                "all_scores": {intent: 0.0 for intent in intents},
                "error": str(e)
            }

class RAGPipeline:
    """Complete RAG Pipeline with document loading, embedding, retrieval, and LLM generation"""
    
    def __init__(self, llm_pipeline, retriever: HybridRetriever, documents: List[Dict]):
        self.llm_pipeline = llm_pipeline
        self.retriever = retriever
        self.documents = documents
        
    def query(self, question: str, max_context_docs: int = 3) -> Dict:
        """
        Process a query through the complete RAG pipeline
        
        Args:
            question: User question
            max_context_docs: Number of documents to use as context
            
        Returns:
            Dictionary with answer and source documents
        """
        try:
            # Step 1: Retrieve relevant documents
            retrieved_docs = self.retriever.search(question, k=max_context_docs)
            
            # Step 2: Create context from retrieved documents
            context = self._create_context(retrieved_docs)
            
            # Step 3: Generate prompt
            prompt = self._create_prompt(question, context)
            
            # Step 4: Generate response
            response = self.llm_pipeline(
                prompt, 
                max_new_tokens=512, 
                temperature=0.7,
                do_sample=True,
                pad_token_id=50256  # Common pad token for many models
            )
            
            # Extract generated text
            if hasattr(response, '__getitem__') and len(response) > 0:
                generated_text = response[0]['generated_text']
                # Remove the prompt from the generated text
                answer = generated_text[len(prompt):].strip()
            else:
                answer = "I apologize, but I couldn't generate a response."
            
            # Step 5: Prepare result
            result = {
                "question": question,
                "answer": answer,
                "context_documents": retrieved_docs,
                "source_metadata": self._get_source_metadata(retrieved_docs)
            }
            
            return result
            
        except Exception as e:
            return {
                "question": question,
                "answer": f"I encountered an error while processing your question: {str(e)}",
                "context_documents": [],
                "source_metadata": []
            }
    
    def _create_context(self, retrieved_docs: List[str]) -> str:
        """Create context string from retrieved documents"""
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            # Clean and truncate document if too long
            clean_doc = doc.strip()
            if len(clean_doc) > 800:  # Limit context length
                clean_doc = clean_doc[:800] + "..."
            context_parts.append(f"[Document {i}] {clean_doc}")
        
        return "\n\n".join(context_parts)
    
    def _create_prompt(self, question: str, context: str) -> str:
        """Create the prompt for the LLM"""
        prompt = f"""Based on the following documents, please answer the question:

{context}

Question: {question}

Answer:"""
        return prompt
    
    def _get_source_metadata(self, retrieved_docs: List[str]) -> List[Dict]:
        """Get metadata for the source documents"""
        metadata = []
        for doc in retrieved_docs:
            # Find matching document in original documents to get metadata
            for orig_doc in self.documents:
                if orig_doc["text"] == doc and "metadata" in orig_doc:
                    metadata.append(orig_doc["metadata"])
                    break
        return metadata


def get_hf_llm(model_name: str = 'LiquidAI/LFM2-1.2B-RAG') -> pipeline:
    """
    Load and configure HuggingFace LLM for text generation
    
    Args:
        model_name: HuggingFace model name
        
    Returns:
        Configured text generation pipeline
    """
    try:
        print(f"Loading LLM model: {model_name}")
        
        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # Set pad token if not available
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        # Load model with device mapping
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",  # Use GPU if available, CPU otherwise
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            low_cpu_mem_usage=True
        )
        
        # Create pipeline
        llm_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id
        )
        
        print("LLM model loaded successfully!")
        return llm_pipeline
        
    except Exception as e:
        print(f"Error loading LLM model: {e}")
        print("Falling back to a smaller model...")
        
        # Fallback to a smaller, more reliable model
        fallback_model = "microsoft/DialoGPT-medium"
        tokenizer = AutoTokenizer.from_pretrained(fallback_model, padding_side="left")
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(fallback_model)
        llm_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)
        return llm_pipeline


def build_embeddings():
    """
    Build complete embeddings and vector store system
    Returns:
        HybridRetriever instance
    """
    try:
        # 1. Load documents
        print("Loading documents...")
        loader = DocumentLoader("documents/posts.json")
        docs = loader.load()
        print(f"Loaded {len(docs)} document chunks")

        # 2. Create embedding model and index
        print("Creating embeddings...")
        embedder = EmbeddingModel()
        faiss_index = FaissIndex(embedder)
        faiss_index.build(docs)
        print("FAISS index built successfully")

        # 3. Create BM25 index
        print("Creating BM25 index...")
        bm25_index = BM25Index(faiss_index.texts)
        print("BM25 index built successfully")

        # 4. Create hybrid retriever
        retriever = HybridRetriever(faiss_index, bm25_index)
        print("Hybrid retriever created successfully")
        
        return retriever, docs
        
    except Exception as e:
        print(f"Error building embeddings: {e}")
        return None, None


def rag_pipeline(query: str) -> Dict:
    """
    Complete RAG pipeline for answering questions
    
    Args:
        query: User question
        
    Returns:
        Dictionary with answer and source information
    """
    try:
        # 1. Build embeddings and retrieval system
        print("Building retrieval system...")
        retriever, documents = build_embeddings()
        
        if retriever is None:
            return {"error": "Failed to build retrieval system"}
        
        # 2. Load LLM
        print("Loading LLM...")
        llm = get_hf_llm()
        
        # 3. Create RAG pipeline
        print("Creating RAG pipeline...")
        rag = RAGPipeline(llm, retriever, documents)
        
        # 4. Process query
        print(f"Processing query: {query}")
        result = rag.query(query)
        
        print("Query processed successfully!")
        return result
        
    except Exception as e:
        error_msg = f"Error in RAG pipeline: {str(e)}"
        print(error_msg)
        return {
            "error": error_msg,
            "question": query,
            "answer": "I apologize, but I encountered an error while processing your question.",
            "context_documents": [],
            "source_metadata": []
        }


def run_rag(question: str) -> Dict:
    """
    Wrapper function for the main.py to call RAG pipeline
    
    Args:
        question: User question
        
    Returns:
        Dictionary with answer and source information
    """
    result = rag_pipeline(question)
    
    # Convert to the expected format for main.py
    if "error" in result:
        return result
    
    return {
        "answer": result.get("answer", "No answer generated"),
        "sources": result.get("context_documents", [])
    }


def interactive_demo():
    """Interactive demo of the RAG pipeline"""
    print("=" * 60)
    print("🎯 Netskope RAG Pipeline Demo")
    print("=" * 60)
    print("Ask questions about Netskope products and features!")
    print("Type 'quit' to exit")
    print("-" * 60)
    
    # Build system once
    print("Initializing system...")
    retriever, documents = build_embeddings()
    
    if retriever is None:
        print("❌ Failed to initialize system")
        return
    
    print("Loading LLM...")
    llm = get_hf_llm()
    
    rag = RAGPipeline(llm, retriever, documents)
    
    while True:
        try:
            query = input("\n❓ Your question: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not query:
                continue
                
            result = rag.query(query)
            
            print("\n" + "=" * 40)
            print("📝 ANSWER:")
            print("=" * 40)
            print(result['answer'])
            
            if result['source_metadata']:
                print("\n" + "=" * 40)
                print("📚 SOURCES:")
                print("=" * 40)
                for i, metadata in enumerate(result['source_metadata'][:3], 1):
                    print(f"{i}. {metadata.get('product', 'Unknown Product')} - {metadata.get('title', 'No title')}")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Run interactive demo
    interactive_demo()
