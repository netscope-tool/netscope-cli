"""
Configuration management.
"""

from pathlib import Path
from datetime import datetime
from typing import Any, Optional
import json
from pydantic import BaseModel, ConfigDict, Field, field_validator


def load_config_file() -> dict[str, Any]:
    """
    Load optional config from ~/.netscope.yaml or ./.netscope.yaml.
    Returns dict with output_dir (str or Path), verbose (bool), timeout (int).
    Missing keys are omitted so callers can use their own defaults.
    """
    result: dict[str, Any] = {}
    candidates = [
        Path.home() / ".netscope.yaml",
        Path.cwd() / ".netscope.yaml",
    ]
    raw: dict[str, Any] = {}
    for path in candidates:
        if path.exists():
            try:
                try:
                    import yaml
                except ImportError:
                    break
                with open(path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                break
            except Exception:
                raw = {}
                break
    if not raw:
        return result
    if "output_dir" in raw:
        result["output_dir"] = Path(raw["output_dir"]).expanduser().resolve()
    if "verbose" in raw:
        result["verbose"] = bool(raw["verbose"])
    if "timeout" in raw:
        try:
            result["timeout"] = int(raw["timeout"])
        except (TypeError, ValueError):
            pass
    return result


class AppConfig(BaseModel):
    """Application configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output_dir: Path = Field(default=Path("output"))
    verbose: bool = False
    timeout: int = 30
    
    @field_validator('output_dir', mode='before')
    @classmethod
    def validate_output_dir(cls, v):
        """Validate and convert output_dir to Path."""
        if v is None:
            return Path("output")
        if isinstance(v, str):
            return Path(v)
        if isinstance(v, Path):
            return v
        return Path("output")
    
    def model_post_init(self, __context):
        """Ensure output directory exists and is resolved to absolute path."""
        self.output_dir = self.output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_test_run_dir(self, test_name: str) -> Path:
        """Create a directory for a test run."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        test_dir = self.output_dir / f"{timestamp}_{test_name}"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (test_dir / "raw_output").mkdir(exist_ok=True)
        
        return test_dir
    
    def save_metadata(self, test_dir: Path, metadata: dict):
        """Save test metadata to JSON file."""
        metadata_file = test_dir / "metadata.json"
        
        # Add timestamp
        metadata["timestamp"] = datetime.now().isoformat()
        
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)