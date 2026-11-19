FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    STEEL_LAB_HOST=0.0.0.0 \
    STEEL_LAB_PORT=8765

COPY . /app

EXPOSE 8765
CMD ["python", "-u", "app.py"]
