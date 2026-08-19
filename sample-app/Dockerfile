# Stage 1: Build the React frontend
FROM node:20-slim AS build-ui
WORKDIR /app/ui
COPY ui/ ./

# Stage 2: Build the Python backend
FROM python:3.12
WORKDIR /app

# Install missing geospatial C-deps
RUN apt-get update && apt-get install -y gdal-bin libgdal-dev g++

# Copy requirements
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Copy the built frontend
COPY --from=build-ui /app/ui/dist ./ui/dist

# Expose the port and run the application
EXPOSE 8080
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}