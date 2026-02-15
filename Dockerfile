FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY config.yaml .
COPY octopod/ octopod/
COPY run_cloud.py .

# Create data directory
RUN mkdir -p data/summaries

# Install the package
RUN pip install --no-cache-dir -e .

# Run the cloud pipeline
CMD ["python", "run_cloud.py"]
