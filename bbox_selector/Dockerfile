FROM python:3.12-slim

# Install minimal system deps for building wheels if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Do NOT copy .env into the image in CI or production; prefer mounting it at runtime.
# Expose the port the app uses
EXPOSE 5000

# Use a simple command to run the Flask app. The app reads env vars via python-dotenv
# If you prefer gunicorn for production, replace the CMD with a gunicorn invocation
CMD ["python", "app.py"]
