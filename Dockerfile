FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN pip install --no-cache-dir uv && cd backend && uv sync --frozen --no-dev
COPY backend/main.py ./backend/main.py
COPY --from=frontend /frontend/dist ./frontend/dist
ENV PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
