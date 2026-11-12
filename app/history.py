import json
import redis

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

MAX_HISTORY_TURNS = 5
SESSION_TTL_SECONDS = 60 * 60  # 1 hour


def get_history(session_id: str) -> list[dict]:
    raw = redis_client.get(f"chat_history:{session_id}")
    if raw is None:
        return []
    return json.loads(raw)


def save_history(session_id: str, history: list[dict]) -> None:
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    redis_client.set(
        f"chat_history:{session_id}",
        json.dumps(trimmed),
        ex=SESSION_TTL_SECONDS,
    )