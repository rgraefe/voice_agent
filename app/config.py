from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "production"] = "development"
    persistence_backend: Literal["sqlite", "firestore"] = "sqlite"
    database_path: str = ".local/interviews.db"
    firestore_project: str | None = None
    firestore_database: str = "(default)"
    admin_password: str = ""
    session_secret: str = ""
    worker_secret: str = ""
    public_origin: str = "http://localhost:8000"
    backend_url: str = "http://localhost:8000"
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_stt_api_key: str = ""
    # Server-wide provider selection; it must match in the API and worker environments.
    stt_provider: Literal["deepgram", "elevenlabs"] = "deepgram"
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"

    @model_validator(mode="after")
    # Fail during startup rather than run a deployment with development security defaults.
    def production_safety(self):
        if self.environment == "production":
            if any(len(v) < 32 for v in (self.session_secret, self.worker_secret, self.admin_password)):
                raise ValueError("Production requires secrets of at least 32 characters")
            if len({self.session_secret, self.worker_secret, self.admin_password}) != 3:
                raise ValueError("Use different secrets")
            if self.persistence_backend != "firestore" or not self.public_origin.startswith("https://"):
                raise ValueError("Production requires Firestore and an HTTPS origin")
        return self

    # Configuration readiness only: this does not authenticate keys or check a running worker.
    def missing_voice(self) -> list[str]:
        names = ["livekit_url", "livekit_api_key", "livekit_api_secret", "worker_secret", "elevenlabs_api_key", "openai_api_key"]
        if self.stt_provider == 'deepgram':
            names.append('deepgram_api_key')
        return [name.upper() for name in names if not getattr(self, name).strip()]
