from typing import Optional
from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    name: str = ""
    goal: str = ""
    weight_kg: float = 0
    target_weight_kg: float = 0
    height_cm: float = 0
    body_type: str = ""
    activity_level: str = ""
    current_workout: str = ""
    daily_calorie_target: float = 0
    daily_protein_target: float = 0


class Meal(BaseModel):
    description: str = ""
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    healthy: bool = True


class AgentOutput(BaseModel):
    reply: str
    onboarding_complete: bool = False
    profile_changed: bool = False
    profile_update: ProfileUpdate = ProfileUpdate()
    meal_logged: bool = False
    meal: Meal = Meal()
    weight_logged: bool = False
    weight_kg: float = 0
    wants_progress_chart: bool = False


class InboundMessage(BaseModel):
    """Normalized inbound payload from the WhatsApp platform."""
    phone_num: str = ""
    group_id: str = ""
    user_id: str = ""
    text: str = ""
    image_url: str = ""
    image_b64: str = ""
    image_mime: str = "image/jpeg"
    sender_name: str = ""
    contact_number: str = ""
    e164: str = ""

    @property
    def image_ref(self) -> str:
        """A value usable as OpenAI image_url: a data URL for base64, or the http URL."""
        if self.image_b64:
            return f"data:{self.image_mime};base64,{self.image_b64}"
        return self.image_url

    @property
    def has_image(self) -> bool:
        return bool(self.image_b64 or self.image_url)


# JSON Schema handed to OpenAI structured outputs (strict mode).
AGENT_JSON_SCHEMA = {
    "name": "gym_trainer_output",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reply": {"type": "string"},
            "onboarding_complete": {"type": "boolean"},
            "profile_changed": {"type": "boolean"},
            "profile_update": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "goal": {"type": "string"},
                    "weight_kg": {"type": "number"},
                    "target_weight_kg": {"type": "number"},
                    "height_cm": {"type": "number"},
                    "body_type": {"type": "string"},
                    "activity_level": {"type": "string"},
                    "current_workout": {"type": "string"},
                    "daily_calorie_target": {"type": "number"},
                    "daily_protein_target": {"type": "number"},
                },
                "required": [
                    "name", "goal", "weight_kg", "target_weight_kg", "height_cm",
                    "body_type", "activity_level", "current_workout",
                    "daily_calorie_target", "daily_protein_target",
                ],
            },
            "meal_logged": {"type": "boolean"},
            "meal": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                    "healthy": {"type": "boolean"},
                },
                "required": ["description", "calories", "protein_g", "carbs_g", "fat_g", "healthy"],
            },
            "weight_logged": {"type": "boolean"},
            "weight_kg": {"type": "number"},
            "wants_progress_chart": {"type": "boolean"},
        },
        "required": [
            "reply", "onboarding_complete", "profile_changed", "profile_update",
            "meal_logged", "meal", "weight_logged", "weight_kg", "wants_progress_chart",
        ],
    },
}
