# Stage 1: Build the React application
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the python backend
FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Copy built frontend assets from Stage 1 to the location Flask serves them from
COPY --from=frontend-builder /frontend/dist ./frontend/dist

EXPOSE 5000

CMD ["python", "app.py"]
