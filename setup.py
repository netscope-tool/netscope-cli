from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="netscope",
    version="1.0.0",  # Keep in sync with netscope/__init__.py and pyproject.toml
    author="NetScope Team",
    author_email="team@netscope.dev",
    description="Comprehensive network diagnostics and reporting tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/netscope-tool/netscope-cli",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Networking :: Monitoring",
    ],
    python_requires=">=3.9",
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "questionary>=2.0.0",
        "pandas>=2.0.0",
        "loguru>=0.7.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dateutil>=2.8.0",
        "PyYAML>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0",
            "ruff>=0.1.0",
            "mypy>=1.0",
        ],
        "security": [
            "cryptography>=41.0",
            "python-nmap>=0.7.1",
        ],
        "bandwidth": [
            "speedtest-cli>=2.1.3",
        ],
        "advanced": [
            "scapy>=2.5.0",
            "netifaces>=0.11.0",
            "aiohttp>=3.9.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "netscope=netscope.__main__:main",
        ],
    },
)