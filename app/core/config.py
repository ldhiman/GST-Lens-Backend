from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()  # Load .env file

class Settings(BaseSettings):
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str
    GEMINI_API_KEY: str
    SERVICE_ACCOUNT: str
    RAZORPAY_MONTHLY_PLAN_ID: str = "plan_Rv5J2PDzXG0hV2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
