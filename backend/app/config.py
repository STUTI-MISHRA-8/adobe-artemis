from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    groq_api_key: str = ""
    groq_api_keys: str = ""  # optional: comma-separated additional keys, rotated for more daily quota
    # optional: same idea as groq_api_keys, but one key per env var — no comma-splitting to get
    # wrong, no "singular vs plural field name" to mix up. Any subset can be set; unset ones are "".
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    groq_api_key_4: str = ""
    groq_api_key_5: str = ""
    groq_api_key_6: str = ""
    groq_api_key_7: str = ""
    groq_api_key_8: str = ""
    groq_api_key_9: str = ""
    groq_api_key_10: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    @property
    def groq_api_key_list(self) -> list[str]:
        keys = [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]
        numbered = [
            self.groq_api_key_1, self.groq_api_key_2, self.groq_api_key_3, self.groq_api_key_4,
            self.groq_api_key_5, self.groq_api_key_6, self.groq_api_key_7, self.groq_api_key_8,
            self.groq_api_key_9, self.groq_api_key_10,
        ]
        for k in numbered:
            if k.strip() and k.strip() not in keys:
                keys.append(k.strip())
        if self.groq_api_key and self.groq_api_key not in keys:
            keys.insert(0, self.groq_api_key)
        return keys

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    fluffyjaws_api_host: str = "https://api.fluffyjaws.adobe.com"
    fluffyjaws_model: str = "gpt-5.1"

    aep_client_id: str = ""
    aep_client_secret: str = ""
    aep_org_id: str = ""
    aep_scopes: str = "openid,AdobeID,read_organizations,additional_info.projectedProductContext,session"
    aep_sandbox_name: str = ""

    db_path: Path = DATA_DIR / "artemis.db"

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def aep_configured(self) -> bool:
        return bool(self.aep_client_id and self.aep_client_secret and self.aep_org_id and self.aep_sandbox_name)


settings = Settings()
