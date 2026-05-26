"""
core/config.py

All BlobFi settings, loaded from .env via pydantic-settings.
Access anywhere with: from core.config import settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "BlobFi"
    app_env: str = "development"
    app_port: int = 8000
    log_level: str = "INFO"

    # Database (lightweight sqlite, no postgres needed for hackathon)
    database_url: str = "sqlite+aiosqlite:///./blobfi.db"

    # Sui RPC (via Tatum)
    tatum_api_key: str = ""
    sui_rpc_mainnet: str = "https://sui-mainnet.gateway.tatum.io"
    sui_rpc_testnet: str = "https://sui-testnet.gateway.tatum.io"
    sui_network: str = "mainnet"  # mainnet | testnet | devnet

    # DefiLlama
    defillama_base_url: str = "https://api.llama.fi"
    defillama_yields_url: str = "https://yields.llama.fi"

    # Walrus
    walrus_publisher_url: str = "https://publisher.walrus-testnet.walrus.space"
    walrus_aggregator_url: str = "https://aggregator.walrus-testnet.walrus.space"
    walrus_epochs: int = 5  # number of epochs to store blob

    # AI
    anthropic_api_key: str = ""

    # Pipeline
    snapshot_interval_seconds: int = 300  # every 5 mins
    cache_ttl_seconds: int = 60
    top_protocols_count: int = 10

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def sui_rpc_url(self) -> str:
        return self.sui_rpc_mainnet if self.sui_network == "mainnet" else self.sui_rpc_testnet

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
