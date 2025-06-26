import os
import re
import json
from news_topic import NEWS_TOPIC
os.environ["USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

# 1. Load and split documents
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

loader = WebBaseLoader(["https://economictimes.indiatimes.com/industry/banking/finance/rbi-guidelines-for-project-finance-cre-a-smaller-provisions-hikes-no-big-worry-for-banks-nbfcs/articleshow/121982012.cms"])
docs = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
splits = splitter.split_documents(docs)

# 2. Embed with sentence-transformers and store in Chroma
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 3. Setup Ollama LLM (llama3)
from langchain_ollama import OllamaLLM

llm = OllamaLLM(model="llama3")  # Make sure it's running via `ollama run llama3`

# 4. Build the RAG chain
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

prompt = ChatPromptTemplate.from_template(
    """
You are a fact verification assistant.

Your task is to determine whether the **news in the question** is trustworthy or fake by strictly comparing it with the **trusted information in the context**.

--------------------
Context (trusted source):
{context}

News to verify (question):
{question}
--------------------

Instructions:
1. Compare the news content to the trusted context only.
2. Output a **trust score** between 0 and 1, indicating how well the news aligns with the context.
3. Based on the trust score, give a **verdict**:
   - If trust score > 0.8 → "Highly Trustworthy"
   - If 0.5 ≤ trust score ≤ 0.8 → "Likely Trustworthy"
   - If trust score < 0.5 → "Not Trustworthy"
4. If trust score < 0.5, provide a **trusted version of the news** based only on the context.

Your response must follow this exact JSON format:
```json
{{
  "trust_score": <score from 0 to 1>,
  "verdict": "<your verdict>",
  "trusted_news": "<only if score < 0.5, else return null>"
}}
"""
)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 5. Ask a question
question = NEWS_TOPIC

response = rag_chain.invoke(question)
#print("🔍 Answer:\n", response)

# Extract JSON part from the response
json_match = re.search(r'\{[\s\S]*\}', response)
if json_match:
    json_str = json_match.group(0)
    try:
        response_json = json.loads(json_str)
        print("Extracted JSON:", response_json)
    except json.JSONDecodeError:
        print("Failed to parse JSON.")
else:
    print("No JSON found in response.")