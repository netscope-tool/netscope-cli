"""
System and tool detection.
"""

import platform
import sys
import shutil
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
import socket


class SystemInfo(BaseModel):
    """System information model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    os_type: str  # 'Linux', 'Darwin', 'Windows'
    platform: str
    python_version: str
    hostname: str


class MissingTool(BaseModel):
    """Information about a missing tool."""
    
    name: str
    suggestion: str


class SystemDetector:
    """Detect system information and tool availability."""
    
    def detect_system(self) -> SystemInfo:
        """Detect current system information."""
        return SystemInfo(
            os_type=platform.system(),
            platform=platform.platform(),
            python_version=sys.version.split()[0],
            hostname=socket.gethostname(),
        )
    
    def check_required_tools(self, tools: List[str]) -> List[MissingTool]:
        """Check if required tools are available."""
        missing = []
        os_type = platform.system()
        
        for tool in tools:
            # Map tool names to OS-specific equivalents
            actual_tool = self._get_tool_name(tool, os_type)
            
            if not self._is_tool_available(actual_tool):
                missing.append(MissingTool(
                    name=tool,
                    suggestion=self._get_installation_suggestion(tool, os_type)
                ))
        
        return missing
    
    def _get_tool_name(self, tool: str, os_type: str) -> str:
        """Get OS-specific tool name."""
        mappings = {
            "traceroute": {
                "Windows": "tracert",
                "Darwin": "traceroute",
                "Linux": "traceroute",
            },
            "dig": {
                "Windows": "nslookup",
                "Darwin": "dig",
                "Linux": "dig",
            },
        }
        
        if tool in mappings and os_type in mappings[tool]:
            return mappings[tool][os_type]
        
        return tool
    
    def _is_tool_available(self, tool: str) -> bool:
        """Check if a tool is available in PATH."""
        return shutil.which(tool) is not None
    
    def _get_installation_suggestion(self, tool: str, os_type: str) -> str:
        """Get installation suggestion for a missing tool."""
        suggestions = {
            "Linux": {
                "ping": "Usually pre-installed",
                "traceroute": "sudo apt-get install traceroute (or yum install traceroute)",
                "dig": "sudo apt-get install dnsutils (or yum install bind-utils)",
            },
            "Darwin": {
                "ping": "Pre-installed",
                "traceroute": "Pre-installed",
                "dig": "Pre-installed",
            },
            "Windows": {
                "ping": "Pre-installed",
                "tracert": "Pre-installed",
                "nslookup": "Pre-installed (NetScope uses nslookup for DNS on Windows)",
                "dig": "Pre-installed (NetScope uses nslookup for DNS on Windows)",
            },
        }
        
        if os_type in suggestions and tool in suggestions[os_type]:
            return suggestions[os_type][tool]
        
        return f"Please install {tool} manually"
    
    def get_tool_path(self, tool: str) -> Optional[str]:
        """Get the full path to a tool."""
        os_type = platform.system()
        actual_tool = self._get_tool_name(tool, os_type)
        return shutil.which(actual_tool)