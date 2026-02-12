"""
Configuration management.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
import json
from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Application configuration."""
    
    output_dir: Path = Field(default=Path("output"))
    verbose: bool = False
    timeout: int = 30
    
    class Config:
        arbitrary_types_allowed = True
    
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
        """Ensure output directory exists after initialization."""
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