from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ors_api_key: str = ""
    bmkg_base_url: str = "https://peta-maritim.bmkg.go.id/public_api"
    database_url: str = "postgresql+psycopg2://route_planner:route_planner@localhost:5432/route_planner"
    bmkg_cache_ttl_seconds: int = 10800


settings = Settings()
