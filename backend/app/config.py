from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_webhook_id: str | None = None
    paypal_return_url: str | None = None
    paypal_cancel_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str = "authenticated"
    request_timeout_seconds: float = 15
    allowed_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = 30

    def validate_sandbox(self) -> None:
        if self.paypal_base_url.rstrip("/") != "https://api-m.sandbox.paypal.com":
            raise RuntimeError("AgentPay payment integration only permits PayPal Sandbox URLs")


settings = Settings()
