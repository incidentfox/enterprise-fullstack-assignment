"""Configuration management using Pydantic settings."""
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "IncidentFox"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    port: int = 8000

    # Database
    database_url: str = Field(
        default="sqlite:///./incidentfox.db",
        description="Database connection string"
    )

    # GitHub App
    github_app_id: int = Field(..., description="GitHub App ID")
    github_installation_id: int = Field(..., description="GitHub App Installation ID")
    github_app_private_key_path: Path = Field(
        default=Path("./private-key.pem"),
        description="Path to GitHub App private key"
    )
    github_webhook_secret: str = Field(..., description="GitHub webhook secret")

    @field_validator("github_app_private_key_path")
    @classmethod
    def validate_private_key_exists(cls, v: Path) -> Path:
        """Ensure private key file exists."""
        if not v.exists():
            raise ValueError(f"GitHub App private key not found at {v}")
        return v

    # Coolify
    coolify_api_url: str = Field(..., description="Coolify instance URL")
    coolify_api_token: str = Field(..., description="Coolify API token")
    coolify_webhook_secret: Optional[str] = Field(
        default=None,
        description="Coolify webhook secret (optional)"
    )

    # LLM Configuration (Anthropic Claude only)
    anthropic_api_key: str = Field(..., description="Anthropic API key (required)")

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        """Ensure Anthropic API key is configured."""
        if not v or not v.startswith("sk-ant-"):
            raise ValueError("Valid Anthropic API key is required (should start with 'sk-ant-')")
        return v

    # Claude Model Configuration
    claude_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Claude model for analysis (default: Sonnet 4.5)"
    )
    claude_opus_model: str = Field(
        default="claude-opus-4-5-20251101",
        description="Claude Opus model for complex analysis (fallback)"
    )
    use_opus_for_complex: bool = Field(
        default=False,
        description="Use Opus for low-confidence failures (more intelligent but slower/pricier)"
    )
    opus_confidence_threshold: int = Field(
        default=60,
        description="Confidence threshold below which to use Opus (0-100)"
    )

    # Feature Flags
    enable_auto_fix: bool = Field(
        default=False,
        description="Allow automatic fix application (dangerous)"
    )
    max_patch_files: int = Field(
        default=5,
        description="Maximum files to patch in one operation"
    )

    # Security
    allowed_file_patterns: str = Field(
        default="Dockerfile,docker-compose*.yml,.env.example,package*.json,requirements*.txt,*.config.js,*.config.ts,tsconfig.json,Makefile",
        description="Comma-separated patterns for files allowed in patches"
    )

    @property
    def allowed_file_list(self) -> List[str]:
        """Parse allowed file patterns into a list."""
        return [p.strip() for p in self.allowed_file_patterns.split(",")]

    @property
    def github_private_key(self) -> str:
        """Read GitHub App private key from file."""
        return self.github_app_private_key_path.read_text()

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    def model_post_init(self, __context) -> None:
        """Post-initialization validation."""
        # Anthropic API key is required (validated in field validator above)
        pass


# Global settings instance
settings = Settings()
