# minmin-cau: cau noi Frigate MQTT -> MinMin. Nho gon: python slim + paho-mqtt.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir "paho-mqtt>=2.1,<3"
WORKDIR /app
COPY cau.py /app/cau.py
VOLUME ["/data"]
CMD ["python", "/app/cau.py"]
