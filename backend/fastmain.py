from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from backend.rag_pipeline import run_rag_pipeline
from backend.bbcscrape import get_bbc_links
from backend.hinduscrape import get_hindu_links
from backend.etscrape import get_et_links
#from backend.test1 import get_cnbc_links_only
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    text: str

def extract_keywords(text):
    stopwords = {"the", "is", "in","headline", "at", "of", "on", "and", "a", "to", "after", "has", "with", "for", "by", "an", "as", "it", "from", "this", "that", "be", "are", "was", "were", "or", "but", "not", "which", "have", "had", "will", "would", "can", "could", "should", "may", "might", "do", "does", "did", "so", "such", "if", "then", "than", "also", "their", "its", "about", "into", "more", "other", "some", "any", "all", "no", "only", "over", "out", "up", "down", "off", "just", "now", "like", "because", "how", "when", "where", "who", "what", "why"}
    words = re.findall(r"\w+", text)
    keywords = [word for word in words if word.lower() not in stopwords]
    
    return " ".join(keywords[:10])

@app.post("/run_rag_pipeline/")
async def analyze_news(msg: Message):
    # Extract keywords from the news text
    keywords = extract_keywords(msg.text)
    # Only start scraping when the endpoint is called (i.e., when the extension button is clicked)
    et_links = get_et_links(keywords)  # ET scraping only runs now
    #cnbc_links=get_cnbc_links_only(keywords) 
    #bbc_links = get_bbc_links(keywords)
    #hindu_links = get_hindu_links(keywords)
    all_links =  et_links#bbc_links + hindu_links 
    # Run the RAG pipeline with the provided news text and links
    result = run_rag_pipeline(msg.text, all_links)
    return result

@app.get("/")
async def read_message():
    return {"status": "RAG backend is running"}


