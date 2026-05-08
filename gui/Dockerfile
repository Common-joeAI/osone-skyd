FROM node:20-slim AS builder
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN pip install fastapi uvicorn[standard] httpx psutil pyjwt bcrypt python-multipart
WORKDIR /app
COPY server.py .
COPY --from=builder /app/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "websockets"]
