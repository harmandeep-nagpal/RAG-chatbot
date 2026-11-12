from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_returns_answer_and_citations():
    response = client.post("/chat", json={"question": "What is this document about?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert isinstance(data["citations"], list)

def test_chat_returns_citations_with_text_and_distance():
    response = client.post("/chat", json={"question": "What is this document about?"})
    data = response.json()
    first_citation = data["citations"][0]
    assert "source" in first_citation
    assert "text" in first_citation
    assert "distance" in first_citation

def test_chat_remembers_session_history():
    first = client.post("/chat", json={"question": "What is this document about?"})
    session_id = first.json()["session_id"]

    second = client.post("/chat", json={
        "question": "Can you elaborate on that?",
        "session_id": session_id,
    })
    assert second.status_code == 200
    assert second.json()["session_id"] == session_id