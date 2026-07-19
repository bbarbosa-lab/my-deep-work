import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import redis
from passlib.context import CryptContext
from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

_redis: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5)
    return _redis


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def create_session(user_id: int, ip: str | None = None, user_agent: str | None = None) -> str:
    r = get_redis()
    sid = generate_token(32)
    now = datetime.now(timezone.utc).isoformat()
    key = f"session:{sid}"
    r.hset(key, mapping={
        "user_id": str(user_id),
        "created_at": now,
        "ip": ip or "",
        "user_agent": (user_agent or "")[:256],
        "csrf_token": generate_token(24),
    })
    r.expire(key, settings.session_ttl_seconds)
    r.sadd(f"user_sessions:{user_id}", sid)
    r.expire(f"user_sessions:{user_id}", settings.session_ttl_seconds)
    return sid


def get_session(sid: str) -> Optional[dict]:
    if not sid or len(sid) < 20:
        return None
    data = get_redis().hgetall(f"session:{sid}")
    return data or None


def destroy_session(sid: str) -> None:
    if not sid:
        return
    r = get_redis()
    data = r.hgetall(f"session:{sid}")
    r.delete(f"session:{sid}")
    if data and data.get("user_id"):
        r.srem(f"user_sessions:{data['user_id']}", sid)


def destroy_all_user_sessions(user_id: int, except_sid: str | None = None) -> int:
    r = get_redis()
    key = f"user_sessions:{user_id}"
    sids = r.smembers(key)
    count = 0
    for sid in sids:
        if except_sid and sid == except_sid:
            continue
        r.delete(f"session:{sid}")
        r.srem(key, sid)
        count += 1
    return count


def rotate_session(old_sid: str | None, user_id: int, ip: str | None = None, ua: str | None = None) -> str:
    if old_sid:
        destroy_session(old_sid)
    return create_session(user_id, ip=ip, user_agent=ua)


def check_rate(prefix: str, identifier: str, limit: int, window: int = 60) -> Tuple[bool, int]:
    r = get_redis()
    key = f"rl:{prefix}:{identifier}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)
    count = pipe.execute()[0]
    return count <= limit, count


def store_reset_token(user_id: int, token: str) -> None:
    r = get_redis()
    r.setex(f"pwdreset:{token}", settings.password_reset_ttl_seconds, str(user_id))


def consume_reset_token(token: str) -> Optional[int]:
    r = get_redis()
    key = f"pwdreset:{token}"
    uid = r.get(key)
    if not uid:
        return None
    r.delete(key)
    return int(uid)


def log_auth_event(event: str, email: str | None = None, ip: str | None = None, detail: str = "") -> None:
    r = get_redis()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "email": email or "",
        "ip": ip or "",
        "detail": detail[:200],
    }
    import json
    r.lpush("auth_events", json.dumps(entry))
    r.ltrim("auth_events", 0, 999)
