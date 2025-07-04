import os
import re
import json
from backend.bbcscrape import get_bbc_links
from backend.hinduscrape import get_hindu_links
from backend.trusted_news_fallback import get_trusted_context
os.environ["USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

def run_rag_pipeline(news_text, links):
    # 1. Try trusted fallback first
    """trusted_context = get_trusted_context(news_text)
    if trusted_context:
        docs = [type('Doc', (), {'page_content': trusted_context})()]
    else:"""
    from langchain_community.document_loaders import WebBaseLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    loader = WebBaseLoader(links)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents(docs)
    docs = splits

    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = Chroma.from_documents(documents=docs, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
    from langchain_ollama import OllamaLLM
    llm = OllamaLLM(model="llama3")
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
1. Compare the news content to the trusted context only.Compare the meaning and intent of the news with the context.
2. Output a **trust score** between 0 and 1, indicating how well the news aligns with the context.
3. Based on the trust score, give a **verdict**:
   - If trust score > 0.8 → "Highly Trustworthy"
   - If 0.5 ≤ trust score ≤ 0.8 → "Likely Trustworthy"
   - If trust score < 0.5 → "Not Trustworthy"
4. Generate a trusted news content as output compulsorily for every response and include it in the JSON response and inculde it in the JSON response as "trusted_news" compulsorily for every response.
   The trusted news content should be a summary or paraphrase of the most relevant and trustworthy information from the context that supports your verdict.
5. If the news content has some promotional content or advertisements, ignore it.
6. If the news content is not related to the context, genearate the trusted news content as "No relevant information found in the trusted context" and conclude that it is not trusted news.
7.Your response must follow this exact JSON format:
```json
{{
  "trust_score": <score from 0 to 1>,
  "verdict": "<your verdict>",
  "trusted_news": "<trusted news content>"
}}
8.EACH OF YOUR RESPONSES MUST STRICTLY INCLUDE THE JSON FORMAT ABOVE.
"""
    )
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    response = rag_chain.invoke(news_text)
    print(response)
    #print("Response from RAG pipeline:", response)
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        json_str = json_match.group(0)
        try:
            response_json = json.loads(json_str)
            print(response_json)
            return response_json
            
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON."}
    else:
        return {"error": "No JSON found in response."}