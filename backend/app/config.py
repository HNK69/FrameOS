from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("backend/.env", "../.env", ".env"), extra="ignore")

    database_url: str = "sqlite:///./frameops.db"
    frontend_origin: str = "http://localhost:3000"
    auth_secret: str = ""
    auth_token_minutes: int = 720
    auth_cookie_secure: bool = False
    groq_api_key: str = ""
    groq_model: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    hindsight_api_url: str = ""
    hindsight_api_token: str = ""
    hindsight_rerank_model: str = "hs-decide-1-flash"
    openclaw_gateway_url: str = ""
    openclaw_auth_token: str = ""
    openclaw_agent_id: str = "main"
    openclaw_bin: str = ""
    openclaw_node_bin: str = ""
    upload_dir: str = "../storage/uploads"
    max_upload_bytes: int = 25 * 1024 * 1024
    cors_origins: str = "http://localhost:3000"
    trusted_proxies: str = "127.0.0.1,::1"
    redis_url: str = ""
    app_env: str = "development"


settings = Settings()
