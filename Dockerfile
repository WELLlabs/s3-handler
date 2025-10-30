# Use Python 3.13.7 as base image
FROM python:3.13.7

# Set working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY .python-version pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy application code
COPY . .

# Expose default port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "main.py"]

