import time
import uuid
from typing import Optional

import structlog
import ollama
from fastapi import FastAPI, Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.vectorstore import search_similar_chunks
from app.history import get_history, save_history

app = FastAPI(title="RAG Chatbot")

OLLAMA_MODEL = "llama3.2"

# ── Structured logging ───────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()

# ── Metrics ───────────────────────────────────────────────────────
CHAT_REQUEST_COUNT = Counter(
    "chat_requests_total",
    "Total /chat requests",
    ["status"],
)
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_duration_seconds",
    "Time spent embedding the question and searching the vector DB",
)
GENERATION_LATENCY = Histogram(
    "rag_generation_duration_seconds",
    "Time spent waiting for the LLM to generate an answer",
)
TOTAL_LATENCY = Histogram(
    "rag_chat_total_duration_seconds",
    "Total /chat request duration, retrieval + generation combined",
)


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


def rewrite_query_with_history(question: str, history: list[dict]) -> str:
    if not history:
        return question

    turns = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in history)

    rewrite_prompt = f"""Given this conversation history and a follow-up question,
rewrite the follow-up question as a standalone question that includes all
necessary context. Output ONLY the rewritten question, nothing else.

Conversation history:
{turns}

Follow-up question: {question}

Standalone question:"""

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": rewrite_prompt}],
        options={"temperature": 0},
    )
    rewritten = response["message"]["content"].strip()

    if not rewritten or len(rewritten) > 300:
        return question

    return rewritten


def build_prompt(question: str, chunks: list[dict], history: list[dict]) -> str:
    context = "\n\n".join(f"[Source: {c['source']}]\n{c['text']}" for c in chunks)

    history_text = ""
    if history:
        turns = "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in history)
        history_text = f"\nPrevious conversation:\n{turns}\n"

    return f"""Answer the question using ONLY the context below.
If the answer isn't in the context, say "I don't have enough information to answer that."
Use the previous conversation (if any) to understand follow-up questions, but
still base your actual answer only on the provided context.
{history_text}
Context:
{context}

Question: {question}

Answer:"""


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    history = get_history(session_id)

    request_id = str(uuid.uuid4())
    total_start = time.time()

    try:
        retrieval_start = time.time()
        search_query = rewrite_query_with_history(request.question, history)
        relevant_chunks = search_similar_chunks(search_query, top_k=3)
        retrieval_duration = time.time() - retrieval_start
        RETRIEVAL_LATENCY.observe(retrieval_duration)

        prompt = build_prompt(request.question, relevant_chunks, history)

        generation_start = time.time()
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        generation_duration = time.time() - generation_start
        GENERATION_LATENCY.observe(generation_duration)

        answer = response["message"]["content"]
        total_duration = time.time() - total_start
        TOTAL_LATENCY.observe(total_duration)

        history.append({"role": "user", "content": request.question})
        history.append({"role": "assistant", "content": answer})
        save_history(session_id, history)

        CHAT_REQUEST_COUNT.labels(status="success").inc()
        logger.info(
            "chat_request_completed",
            request_id=request_id,
            session_id=session_id,
            question=request.question,
            search_query=search_query,
            sources=[c["source"] for c in relevant_chunks],
            retrieval_ms=round(retrieval_duration * 1000, 2),
            generation_ms=round(generation_duration * 1000, 2),
            total_ms=round(total_duration * 1000, 2),
        )

        return {
            "session_id": session_id,
            "answer": answer,
            "citations": [
                {
                    "source": c["source"],
                    "text": c["text"],
                    "distance": round(c["distance"], 4),
                }
                for c in relevant_chunks
            ],
        }

    except Exception as e:
        CHAT_REQUEST_COUNT.labels(status="error").inc()
        logger.error(
            "chat_request_failed",
            request_id=request_id,
            session_id=session_id,
            question=request.question,
            error=str(e),
        )
        raise