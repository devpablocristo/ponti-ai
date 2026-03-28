FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
COPY core/http/python /opt/core-http-python
COPY core/ai/python /opt/core-ai
RUN pip install --no-cache-dir /opt/core-http-python && \
    pip install --no-cache-dir /opt/core-ai && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY adapters /app/adapters
COPY contexts /app/contexts

EXPOSE 8090

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
