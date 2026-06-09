"""LLM agent — onboarding + coaching with strict structured output, plus food-photo vision."""
import json
from typing import Optional

from openai import AsyncOpenAI

from .config import settings
from .schemas import AGENT_JSON_SCHEMA, AgentOutput

_client: Optional[AsyncOpenAI] = None


def _openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


SYSTEM_PROMPT = """You are an expert personal gym trainer and nutrition coach chatting with a user over WhatsApp. \
Be warm, motivating and concise (WhatsApp-length messages, use emojis sparingly). Always reply in the same language the user writes in.

USER IDENTITY: user_id={user_id}, name={name}.
CURRENT STORED PROFILE (JSON, may be empty for a new user): {profile}.

ONBOARDING: If the profile is missing or onboarding_complete is not true, run onboarding. Collect, ONE friendly question per \
message: goal (lose fat / build muscle / maintain), current weight (kg), height (cm), target weight (kg), body type, activity \
level, and their current workout routine. When you have enough info, estimate a sensible daily_calorie_target and \
daily_protein_target and set onboarding_complete=true.

ONGOING COACHING: After onboarding, help with meal logging, macro/calorie tracking, weight tracking, workout and meal guidance \
(what to eat / avoid), and motivation.

EXTRACTION RULES for the structured output you MUST return:
- reply: the message to send the user.
- If you learned or changed ANY profile info this turn, set profile_changed=true and put the FULL up-to-date profile in \
profile_update (merge old known values with new ones; use 0 or empty string ONLY for values still unknown). Otherwise false.
- If the user described a meal (in text or via the photo analysis), set meal_logged=true and fill meal with your best estimate \
of description, calories, protein_g, carbs_g, fat_g and healthy. Otherwise meal_logged=false.
- If the user reported their body weight, set weight_logged=true and weight_kg to that number. Otherwise weight_logged=false.
- If the user asks to SEE their progress / weight chart / graph / trend / how they are doing over time, set \
wants_progress_chart=true and make your reply briefly introduce the chart. Otherwise wants_progress_chart=false.
- onboarding_complete reflects whether the full profile is now collected.
Use 0 for unknown numbers and "" for unknown strings."""


async def analyze_food_photo(image_url: str) -> str:
    """Vision: describe a food photo with macro estimates and a healthy verdict."""
    resp = await _openai().chat.completions.create(
        model=settings.openai_vision_model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "You are a nutrition assistant. Identify the food and visible ingredients in this photo. "
                    "Estimate total calories and macros (protein, carbs, fat in grams). State clearly whether it "
                    "looks healthy and why, in one short sentence. Be concise."
                )},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }],
    )
    return resp.choices[0].message.content or ""


async def run_agent(user_id: str, name: str, profile: dict, user_text: str, history: list[dict]) -> AgentOutput:
    system = SYSTEM_PROMPT.format(
        user_id=user_id,
        name=name or "unknown",
        profile=json.dumps(profile, default=str) if profile else "{}",
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    resp = await _openai().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": AGENT_JSON_SCHEMA},
        reasoning_effort="minimal",
    )
    raw = resp.choices[0].message.content or "{}"
    return AgentOutput.model_validate_json(raw)
