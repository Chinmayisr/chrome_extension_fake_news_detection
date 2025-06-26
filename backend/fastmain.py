from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from .rag_pipeline import run_rag_pipeline

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

stored_message = ""

@app.post("/analyze_news/")
async def analyze_news(msg: Message):
    global stored_message
    stored_message = msg.text
    # Run the RAG pipeline with the provided news text
    result = run_rag_pipeline(msg.text)
    return result

@app.get("/")
async def read_message():
    return {"stored_message": stored_message}


