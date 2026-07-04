FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY timetable-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY timetable-engine/ .

RUN chmod +x entrypoint.sh

EXPOSE 5002

CMD ["./entrypoint.sh"]
