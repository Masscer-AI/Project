# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by some Python tools.
# Pandoc is required by pypandoc for document conversion (html/md -> docx/pdf/etc).
RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

# Keep the virtual environment outside /app so host bind mounts do not shadow it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Copy dependency metadata and install locked dependencies.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application code into the container
COPY . .

# Expose port if needed
EXPOSE 8000

# Command to run the Django server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
