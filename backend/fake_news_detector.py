import os
import numpy as np
import logging
import json
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from trusted_news_fallback import trusted_news

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PhiRAGFakeNewsDetector:
    def __init__(self, 
                 vector_db_path: str = "financial_vector_db",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 phi_model_id: str = "microsoft/phi-1_5"):
        self.vector_db_path = vector_db_path
        self.embedding_model = SentenceTransformer(embedding_model)
        self.phi_model_id = phi_model_id
        self._load_vector_db()
        self._load_phi_model()
        # Load fallback trusted news from external file
        self.fallback_trusted_news = trusted_news
        self.fallback_embeddings = self.embedding_model.encode(
            [item["content"] for item in self.fallback_trusted_news]
        )

    def _load_vector_db(self):
        # Load your CSVs and build a simple in-memory index
        import glob
        import pandas as pd
        self.docs = []
        self.doc_embeddings = []
        csv_files = glob.glob(os.path.join(self.vector_db_path, "*.csv"))
        for csv in csv_files:
            df = pd.read_csv(csv)
            for _, row in df.iterrows():
                content = str(row.get("content", ""))[:2000]
                if content.strip():
                    self.docs.append(content)
        if self.docs:
            self.doc_embeddings = self.embedding_model.encode(self.docs, show_progress_bar=True)
        else:
            self.doc_embeddings = np.array([])

    def _load_phi_model(self):
        self.tokenizer = AutoTokenizer.from_pretrained(self.phi_model_id)
        self.model = AutoModelForCausalLM.from_pretrained(self.phi_model_id)
        self.generator = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer)

    def retrieve(self, query: str, top_k: int = 5) -> List[str]:
        if not self.docs or self.doc_embeddings is None or len(self.doc_embeddings) == 0:
            return []
        query_emb = self.embedding_model.encode([query])
        sims = cosine_similarity(query_emb, self.doc_embeddings)[0]
        top_idx = np.argsort(sims)[::-1][:top_k]
        return [self.docs[i] for i in top_idx]

    def generate_answer(self, query: str, context_docs: List[str]) -> str:
        context = "\n\n".join(context_docs)
        prompt = (
            f"You are a financial fact-checker. Given the following trusted documents:\n"
            f"{context}\n\n"
            f"Assess the following news for authenticity and explain your reasoning:\n"
            f"{query}\n"
            f"Respond with a JSON object: "
            f'{{"is_fake": boolean, "trust_score": float, "reasoning": "string"}}'
        )
        output = self.generator(prompt, max_new_tokens=256, do_sample=True, temperature=0.3)
        return output[0]["generated_text"]

    def fallback_similarity_check(self, news_topic: str) -> Dict:
        """Check similarity of news_topic with all fallback trusted news data and use the highest similarity"""
        topic_emb = self.embedding_model.encode([news_topic])[0]
        sims = cosine_similarity([topic_emb], self.fallback_embeddings)[0]
        max_idx = int(np.argmax(sims))
        max_sim = float(sims[max_idx])
        trusted_info = self.fallback_trusted_news[max_idx]["content"]
        trusted_title = self.fallback_trusted_news[max_idx]["title"]
        if max_sim >= 0.8:
            verdict = "highly trustworthy"
            is_fake = False
            reasoning = "The news closely matches trusted official information."
            correct_info = None
            trusted_news_item = None
        elif max_sim >= 0.5:
            verdict = "likely trustworthy"
            is_fake = False
            reasoning = "The news is similar to trusted information but not an exact match."
            correct_info = None
            trusted_news_item = None
        else:
            verdict = "fake"
            is_fake = True
            reasoning = "The news does not match any trusted official information."
            # Only show the first line of the fallback trusted info
            first_line = trusted_info.strip().split("\n")[0]
            correct_info = first_line
            trusted_news_item = None
        return {
            "is_fake": is_fake,
            "trust_score": max_sim,
            "reasoning": reasoning,
            "similarity": max_sim,
            "verdict": verdict,
            "correct_information": correct_info,
            "trusted_news": trusted_news_item
        }

    def analyze_news(self, news_topic: str) -> Dict:
        # Try normal retrieval from vector DB
        context_docs = self.retrieve(news_topic, top_k=5)
        if context_docs:
            answer = self.generate_answer(news_topic, context_docs)
            # Try to extract JSON from the output
            try:
                json_start = answer.find('{')
                json_end = answer.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    result = json.loads(answer[json_start:json_end])
                    result["retrieved_documents"] = len(context_docs)
                    return result
            except Exception as e:
                logger.warning(f"Could not parse model output as JSON: {e}")
            return {
                "is_fake": None,
                "trust_score": 0.0,
                "reasoning": answer,
                "retrieved_documents": len(context_docs)
            }
        # If no docs found, use fallback trusted news similarity
        fallback_result = self.fallback_similarity_check(news_topic)
        return fallback_result

def analyze_news_with_phi_rag(news_topic: str, vector_db_path: str = "financial_vector_db") -> Dict:
    detector = PhiRAGFakeNewsDetector(vector_db_path=vector_db_path)
    return detector.analyze_news(news_topic)