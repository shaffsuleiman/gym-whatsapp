"""Daily dinner / calories-left reminder job (parity with the n8n Reminders workflow)."""
from . import db
from .platform import send_message


def _e164_for(user: dict) -> str:
    e164 = user.get("e164")
    if e164:
        return e164
    cn = "".join(ch for ch in str(user.get("contact_number", "")) if ch.isdigit())
    return f"+{cn}" if cn else user.get("phone_num", "")


async def run_dinner_reminders() -> dict:
    users = await db.get_onboarded_users()
    sent = []
    for u in users:
        target = float(u.get("daily_calorie_target", 0) or 0)
        if target <= 0:
            continue
        consumed = round(await db.get_today_calories(u["user_id"]))
        remaining = round(target - consumed)
        name = u.get("name") or "there"
        if remaining > 50:
            msg = (f"Hi {name}! Dinner check-in: you have logged {consumed} kcal so far today. "
                   f"You still have {remaining} kcal left of your {target:g} kcal goal — plan dinner accordingly.")
        elif remaining >= -100:
            msg = f"Nice work {name}! You are right on your {target:g} kcal goal today ({consumed} kcal). Keep dinner light."
        else:
            msg = f"Heads up {name}! You are {abs(remaining)} kcal over your {target:g} kcal goal today. Consider a lighter dinner."

        result = await send_message(_e164_for(u), msg)
        sent.append({"user_id": u["user_id"], "remaining": remaining, "send": result})
    return {"users_notified": len(sent), "details": sent}
