FROM python:3.13-slim

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 설치
COPY pyproject.toml uv.lock* ./
COPY src/ src/
RUN uv sync --no-dev

# git 설치 (git 파싱에 필요)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# ChromaDB 데이터 디렉토리
RUN mkdir -p /root/.deview/data/chroma

# MCP 서버 실행 (stdio)
# DEVIEW_PROJECT_PATH 환경변수로 프로젝트 경로 전달
ENTRYPOINT ["uv", "run", "--directory", "/app", "python", "-m", "deview.server"]
