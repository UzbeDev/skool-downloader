FROM python:3.11

WORKDIR /app

# Copy requirements first for Docker layer caching
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Install Playwright Chromium browser with all system dependencies
RUN python -m playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Create downloads directory
RUN mkdir -p backend/downloads

EXPOSE 5000

CMD ["python", "backend/app.py"]
