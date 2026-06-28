FROM python:3.11-slim

# Install system dependencies (g++ compiler for compiling C++ code in the sandbox)
RUN apt-get update && apt-get install -y \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn google-genai

# Copy the rest of the application code
COPY . .

# Ensure necessary folders exist
RUN mkdir -p logs/runs workspace problems/custom

# Expose port 8000 for FastAPI
EXPOSE 8000

# Start FastAPI server using uvicorn
CMD ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8000"]
