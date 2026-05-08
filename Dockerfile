# Use an official lightweight Python image.
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED True

# Set the working directory
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy local code to the container image.
COPY . ./

# Run the web service on container startup.
# Cloud Run sets the PORT environment variable automatically.
CMD exec uvicorn src.main:app --host 0.0.0.0 --port $PORT --workers 1