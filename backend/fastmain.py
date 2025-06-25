from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Add import for the fake news detector
from fake_news_detector import analyze_news_with_phi_rag

app = FastAPI()

# ✅ Allow frontend JavaScript (content script) to send requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to ["http://localhost"] or specific sites
    allow_credentials=True,
    allow_methods=["*"],  # Allows POST, GET, OPTIONS, etc.
    allow_headers=["*"],
)

class Message(BaseModel):
    text: str

stored_message = ""

@app.post("/print/")
async def print_text(msg: Message):
    global stored_message
    stored_message = msg.text
    print("Received text:", msg.text)
    # Analyze the news using the fake news detector
    result = analyze_news_with_phi_rag(news_topic=msg.text, vector_db_path="financial_vector_db")
    print("Analysis result:", result)  # <-- Print the verdict/result
    return result

@app.get("/")
async def read_message():
    return {"stored_message": stored_message}


