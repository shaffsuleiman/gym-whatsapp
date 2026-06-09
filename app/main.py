"""FastAPI port of the n8n Gym Trainer — single inbound webhook + dinner-reminder job."""
import asyncio
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from . import db
from .agent import analyze_food_photo, run_agent
from .chart import build_progress_chart
from .config import settings
from .reminders import run_dinner_reminders
from .schemas import InboundMessage


def normalize(body: dict) -> InboundMessage:
    """Handles both the flat payload and the nested {event, metadata, message} envelope."""
    msg = body.get("message") if isinstance(body.get("message"), dict) else {}
    meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}

    def pick(*keys):
        for src in (msg, meta, body):
            for k in keys:
                v = src.get(k)
                if v not in (None, ""):
                    return v
        return ""

    phone = str(pick("from", "phoneNumber", "phone_num"))
    group = str(pick("agentId", "group_id"))
    contact = str(pick("contactNumber", "contact_number"))
    digits = re.sub(r"[^0-9]", "", contact)

    media = msg.get("media") if isinstance(msg.get("media"), dict) else body.get("media")
    image_b64, image_mime = "", "image/jpeg"
    if isinstance(media, dict) and str(media.get("type", "")).startswith("image"):
        image_b64 = media.get("data", "") or ""
        image_mime = media.get("type", "image/jpeg")

    # Prefer `content` (the user's actual caption/text); processedContent can be a broken
    # auto-description for images. Fall back to processedContent for voice transcripts etc.
    text = str(pick("content", "processedContent", "text") or "")

    return InboundMessage(
        phone_num=phone,
        group_id=group,
        user_id=f"{phone}:{group}",
        text=text,
        image_url=str(pick("image_url", "imageUrl") or ""),
        image_b64=image_b64,
        image_mime=image_mime,
        sender_name=str(pick("contactName", "name") or ""),
        contact_number=contact,
        e164=(f"+{digits}" if digits else ""),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.enable_scheduler:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler(timezone=settings.timezone)
        scheduler.add_job(
            run_dinner_reminders,
            CronTrigger(hour=settings.dinner_reminder_hour, minute=settings.dinner_reminder_minute),
            id="dinner_reminders",
        )
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Gym Trainer API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


WEBHOOK_PATHS = [
    "/webhook/gym-trainer",
    "/api/whatsapp/messages",                       # platform appends this to the base URL
    "/webhook/gym-trainer/api/whatsapp/messages",   # base configured as /webhook/gym-trainer
]


@app.post("/webhook/gym-trainer")
async def webhook(request: Request):
    body = await request.json()
    msg = normalize(body)

    # Always capture the contact number, then load profile + history.
    await db.save_contact(msg)
    profile = await db.get_profile(msg.user_id)

    # Prefer the platform's chatHistory (clean, authoritative) over MongoDB which may be polluted.
    platform_history = [
        {"role": m["role"], "content": m["content"]}
        for m in body.get("chatHistory") or []
        if m.get("content")
    ]
    history = platform_history or await db.get_history(msg.user_id)

    user_text = msg.text
    if msg.has_image:
        try:
            analysis = await analyze_food_photo(msg.image_ref)
        except Exception:
            analysis = "(could not analyze the photo — unsupported or unreadable image)"
        user_text = f"{msg.text or '(sent a food photo)'}\n\n[Food photo analysis]:\n{analysis}"

    out = await run_agent(msg.user_id, msg.sender_name or profile.get("name", ""), profile, user_text, history)

    # Persist conversation + structured side effects.
    await db.append_history(msg.user_id, "user", user_text)
    if out.reply:
        await db.append_history(msg.user_id, "assistant", out.reply)
    if out.profile_changed:
        await db.upsert_profile(msg, out.profile_update.model_dump(), out.onboarding_complete)
    if out.meal_logged:
        await db.insert_meal(msg, out.meal.model_dump(), "photo" if msg.has_image else "text")
    if out.weight_logged:
        await db.insert_weight(msg, out.weight_kg)

    response: dict = {"text": out.reply}
    if out.wants_progress_chart:
        weights = await db.get_weights(msg.user_id)
        target = float(profile.get("target_weight_kg") or out.profile_update.target_weight_kg or 0) or None
        _summary, b64 = await asyncio.to_thread(build_progress_chart, weights, target)
        if b64:
            response["image"] = b64
    return response


@app.post("/tasks/dinner-reminders")
async def dinner_reminders():
    """Manually trigger the daily reminder (or point your own cron / scheduler here)."""
    return await run_dinner_reminders()


# Register the same webhook handler on the extra paths the platform may call.
for _p in WEBHOOK_PATHS[1:]:
    app.add_api_route(_p, webhook, methods=["POST"])
