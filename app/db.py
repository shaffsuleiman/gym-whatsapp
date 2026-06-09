"""MongoDB access layer — mirrors the n8n collections: users, meals, weights, chat_histories."""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings

_client: Optional[AsyncIOMotorClient] = None


def _db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client[settings.mongodb_db]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_profile(user_id: str) -> dict[str, Any]:
    doc = await _db().users.find_one({"user_id": user_id}, {"_id": 0})
    return doc or {}


async def save_contact(msg) -> None:
    """Always-on upsert of contact info (parity with n8n 'Save Contact Number')."""
    await _db().users.update_one(
        {"user_id": msg.user_id},
        {"$set": {
            "user_id": msg.user_id,
            "phone_num": msg.phone_num,
            "group_id": msg.group_id,
            "contact_number": msg.contact_number,
            "e164": msg.e164,
        }},
        upsert=True,
    )


async def upsert_profile(msg, profile_update: dict, onboarding_complete: bool) -> None:
    fields = {
        "user_id": msg.user_id,
        "phone_num": msg.phone_num,
        "group_id": msg.group_id,
        "contact_number": msg.contact_number,
        "e164": msg.e164,
        "onboarding_complete": onboarding_complete,
        "updated_at": now_iso(),
        **profile_update,
    }
    await _db().users.update_one({"user_id": msg.user_id}, {"$set": fields}, upsert=True)


async def insert_meal(msg, meal: dict, source: str) -> None:
    await _db().meals.insert_one({
        "user_id": msg.user_id,
        "phone_num": msg.phone_num,
        "group_id": msg.group_id,
        "ts": datetime.now(timezone.utc),
        "source": source,
        **meal,
    })


async def insert_weight(msg, weight_kg: float) -> None:
    await _db().weights.insert_one({
        "user_id": msg.user_id,
        "phone_num": msg.phone_num,
        "group_id": msg.group_id,
        "weight_kg": weight_kg,
        "ts": datetime.now(timezone.utc),
    })


async def get_weights(user_id: str) -> list[dict]:
    cur = _db().weights.find({"user_id": user_id}, {"_id": 0}).sort("ts", 1)
    return [d async for d in cur]


async def get_today_calories(user_id: str) -> float:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cur = _db().meals.find({"user_id": user_id, "ts": {"$gte": start}}, {"calories": 1, "_id": 0})
    total = 0.0
    async for d in cur:
        total += float(d.get("calories", 0) or 0)
    return total


async def get_onboarded_users() -> list[dict]:
    cur = _db().users.find({"onboarding_complete": True}, {"_id": 0})
    return [d async for d in cur]


async def append_history(user_id: str, role: str, content: str) -> None:
    await _db().chat_histories.insert_one({
        "user_id": user_id, "role": role, "content": content, "ts": datetime.now(timezone.utc),
    })


async def get_history(user_id: str, limit: int = 12) -> list[dict]:
    cur = _db().chat_histories.find(
        {"user_id": user_id, "content": {"$nin": [None, ""]}},
        {"_id": 0, "role": 1, "content": 1},
    ).sort("ts", -1).limit(limit)
    msgs = [d async for d in cur]
    return list(reversed(msgs))
