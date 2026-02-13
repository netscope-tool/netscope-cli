# NetScope CLI Docker Image
# Includes ping, traceroute, dig, and optional nmap

FROM python:3.11-slim

LABEL maintainer="NetScope Team <team@netscope.dev>"
LABEL description="Network diagnostics and reporting tool"
LABEL version="1.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iputils-ping \
    traceroute \
    dnsutils \
    nmap \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy package files
COPY pyproject.toml setup.py ./
COPY netscope/ ./netscope/

# Install netscope in development mode (or use pip install . for production)
RUN pip install --no-cache-dir -e .

# Set working directory for data/output
WORKDIR /data

# Entry point
ENTRYPOINT ["netscope"]
CMD ["--help"]

# Example usage:
# docker run --rm netscope-cli:latest --version
# docker run --rm -v $(pwd)/output:/data netscope-cli:latest ping 8.8.8.8
# docker run --rm -v $(pwd)/output:/data netscope-cli:latest quick-check example.com
