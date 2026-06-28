import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ModelConfig:
    mathematician_model: str = "claude-sonnet-4-6"
    architect_model: str = "claude-sonnet-4-6"
    adversary_model: str = "claude-sonnet-4-6"


@dataclass(frozen=True)
class SandboxConfig:
    compile_timeout_seconds: int = 10
    run_timeout_seconds: int = 5
    memory_limit_mb: int = 256


@dataclass(frozen=True)
class PolicyConfig:
    max_architect_retries: int = 5          # per Mathematician approach
    max_mathematician_escalations: int = 2  # times we allow "approach is wrong, try again"


@dataclass(frozen=True)
class PathConfig:
    workspace_dir: Path = PROJECT_ROOT / "workspace"
    logs_dir: Path = PROJECT_ROOT / "logs" / "runs"
    prompts_dir: Path = PROJECT_ROOT / "config" / "prompts"
    testdata_cache_dir: Path = PROJECT_ROOT / "testdata" / "cache"


@dataclass(frozen=True)
class Settings:
    models: ModelConfig = ModelConfig()
    sandbox: SandboxConfig = SandboxConfig()
    policy: PolicyConfig = PolicyConfig()
    paths: PathConfig = PathConfig()


class SettingsValidationSchema(BaseModel):
    MATHEMATICIAN_MODEL: str = "claude-sonnet-4-6"
    ARCHITECT_MODEL: str = "claude-sonnet-4-6"
    ADVERSARY_MODEL: str = "claude-sonnet-4-6"
    CPP_COMPILE_TIMEOUT_SECONDS: int = Field(default=10, ge=1)
    CPP_RUN_TIMEOUT_SECONDS: int = Field(default=5, ge=1)
    CPP_MEMORY_LIMIT_MB: int = Field(default=256, ge=1)
    MAX_ARCHITECT_RETRIES: int = Field(default=5, ge=0)
    MAX_MATHEMATICIAN_ESCALATIONS: int = Field(default=2, ge=0)
    LOG_LEVEL: str = "INFO"
    WORKSPACE_DIR: str = "./workspace"
    LOGS_DIR: str = "./logs/runs"


def load_settings() -> Settings:
    """
    Reads from .env / environment, validates with Pydantic, and returns Settings.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    
    # Filter os.environ to get keys relevant to settings
    keys = [
        "MATHEMATICIAN_MODEL", "ARCHITECT_MODEL", "ADVERSARY_MODEL",
        "CPP_COMPILE_TIMEOUT_SECONDS", "CPP_RUN_TIMEOUT_SECONDS", "CPP_MEMORY_LIMIT_MB",
        "MAX_ARCHITECT_RETRIES", "MAX_MATHEMATICIAN_ESCALATIONS",
        "LOG_LEVEL", "WORKSPACE_DIR", "LOGS_DIR"
    ]
    env_data = {k: os.environ[k] for k in keys if k in os.environ}
    
    # Validate with Pydantic
    validated = SettingsValidationSchema(**env_data)
    
    # Map to typed Settings dataclass
    models = ModelConfig(
        mathematician_model=validated.MATHEMATICIAN_MODEL,
        architect_model=validated.ARCHITECT_MODEL,
        adversary_model=validated.ADVERSARY_MODEL,
    )
    
    sandbox = SandboxConfig(
        compile_timeout_seconds=validated.CPP_COMPILE_TIMEOUT_SECONDS,
        run_timeout_seconds=validated.CPP_RUN_TIMEOUT_SECONDS,
        memory_limit_mb=validated.CPP_MEMORY_LIMIT_MB,
    )
    
    policy = PolicyConfig(
        max_architect_retries=validated.MAX_ARCHITECT_RETRIES,
        max_mathematician_escalations=validated.MAX_MATHEMATICIAN_ESCALATIONS,
    )
    
    # Resolve relative paths relative to PROJECT_ROOT
    workspace_dir = Path(validated.WORKSPACE_DIR)
    if not workspace_dir.is_absolute():
        workspace_dir = (PROJECT_ROOT / workspace_dir).resolve()
        
    logs_dir = Path(validated.LOGS_DIR)
    if not logs_dir.is_absolute():
        logs_dir = (PROJECT_ROOT / logs_dir).resolve()
        
    paths = PathConfig(
        workspace_dir=workspace_dir,
        logs_dir=logs_dir,
        prompts_dir=PROJECT_ROOT / "config" / "prompts",
        testdata_cache_dir=PROJECT_ROOT / "testdata" / "cache",
    )
    
    return Settings(
        models=models,
        sandbox=sandbox,
        policy=policy,
        paths=paths,
    )


settings = load_settings()
