FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    rm -rf /opt/venv/lib/python3.11/site-packages/pip \
    /opt/venv/lib/python3.11/site-packages/setuptools \
    /opt/venv/lib/python3.11/site-packages/wheel

FROM python:3.11-slim
COPY --from=builder /opt/venv /opt/venv
WORKDIR /usr/src/app
COPY . .
ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 5000
CMD ["python", "app.py"]
