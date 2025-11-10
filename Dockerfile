FROM python:3.11-slim-bookworm AS base


ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1


WORKDIR /app


RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY . .

CMD ["python", "foot.py"]