FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y build-essential

# Install a specific version of numpy to ensure compatibility
RUN pip install --no-cache-dir numpy==1.23.5
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "refiner"]
