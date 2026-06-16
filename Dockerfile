# Start from the blank Python slate
FROM python:3.10-slim
# Set the working directory inside the container
WORKDIR /app
# Copy your requirements file into the container
COPY requirements.txt .
# Install the dependencies inside the container's isolated environment
RUN pip install --no-cache-dir -r requirements.txt