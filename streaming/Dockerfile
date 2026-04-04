# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/

# Set the working directory in the container
WORKDIR /app

# Install Node.js and npm
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Keep the virtual environment outside /app so host bind mounts do not shadow it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Install JavaScript dependencies with better Docker cache behavior.
COPY package*.json ./
RUN npm install

# Install Python dependencies from lockfile.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy all files from the project directory
COPY . .

# Print TypeScript configuration
RUN cat tsconfig.json

# Run TypeScript compiler separately to check for errors
RUN npx tsc --noEmit

# Vite inlines VITE_* at build time — pass when building the streaming image for production.
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

# Build the frontend assets (app + widget)
RUN npm run build:all

# Verify that the directory was created
RUN ls -la client/dist/assets

# Expose port 8001
EXPOSE 8001

# Run the FastAPI server using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
