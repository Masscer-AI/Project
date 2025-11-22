# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install Node.js and npm
RUN apt-get update && apt-get install -y nodejs npm

# Copy all files from the project directory
COPY . .

# Install the npm dependencies
RUN npm install

# Print TypeScript configuration
RUN cat tsconfig.json

# Run TypeScript compiler separately to check for errors
RUN npx tsc --noEmit

# Build the frontend assets (app + widget)
RUN npm run build:all

# Verify that the directory was created
RUN ls -la client/dist/assets

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8001
EXPOSE 8001

# Run the FastAPI server using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
