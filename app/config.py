from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "gym_trainer"

    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_vision_model: str = "gpt-5-mini"

    platform_send_url: str = ""
    platform_api_key: str = ""

    enable_scheduler: bool = False
    dinner_reminder_hour: int = 18
    dinner_reminder_minute: int = 0
    timezone: str = "Asia/Karachi"


settings = Settings()
