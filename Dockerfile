FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir waitress

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run with waitress WSGI server
CMD ["waitress-serve", "--listen=0.0.0.0:8080", "server.app:app"]
