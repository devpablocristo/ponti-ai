FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY adapters /app/adapters
COPY contexts /app/contexts

EXPOSE 8090

CMD ["uvicorn", "src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
