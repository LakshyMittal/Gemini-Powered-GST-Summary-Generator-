# kafka_financial_worker.py
import asyncio
import json
import logging
import signal
from string import printable

import config
from confluent_kafka import Consumer
from task_handler import TASK_DISPATCH

# ─── logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
)
log = logging.getLogger("kafka-financial-worker")

# ─── Kafka consumer config (mirrors TS example) ─────────────────────
consumer_conf = {
    "bootstrap.servers": config.KAFKA_BOOTSTRAP,
    "group.id": "underwriting",
    "client.id": config.KAFKA_CLIENT_ID,
    "enable.auto.commit": True,
    "auto.offset.reset": "earliest",
    "session.timeout.ms": 60_000,
    "heartbeat.interval.ms": 3_000,
}
consumer = Consumer(consumer_conf)
consumer.subscribe([config.KAFKA_TOPIC])
log.info("✅ Kafka consumer connected and subscribed to topic: %s", config.KAFKA_TOPIC)

stop_event = asyncio.Event()


def _stop(*_):
    stop_event.set()


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


async def handle_message(msg):
    raw = msg.value()
    if not raw:
        log.warning("⚠️  Received empty message (offset %s)", msg.offset())
        return False

    try:
        payload = json.loads(raw.decode())
    except json.JSONDecodeError:
        log.error("❌ Malformed JSON at offset %s — skipping", msg.offset())
        return False
    task_type = payload.get("type")
    if not task_type:
        log.error("❌ 'type' field missing in payload at offset %s", msg.offset())
        return False

    task_type = task_type.upper()
    handler = TASK_DISPATCH.get(task_type)

    if not handler:
        log.error("❌ Unknown task type '%s' at offset %s", task_type, msg.offset())
        return False

    log.info("▶ Dispatching task type '%s'", task_type)

    retries = 3
    last_err = None
    while retries > 0:
        try:
            summary = await handler(payload)
            log.info("✓ Task '%s' completed — %s chars", task_type, len(summary))
            return True
        except Exception as err:
            last_err = err
            retries -= 1
            log.warning(
                "⚠️  Retry failed (%s left) for %s — %s", retries, task_type, err
            )
            consumer.poll(0)

    log.error("❌ Final failure for task %s — %s", task_type, last_err)
    return False


# ─── main poll loop ────────────────────────────────────────────────
async def poll_forever():
    try:
        while not stop_event.is_set():
            msg = consumer.poll(1.0)  # 1-second poll
            if msg is None:
                await asyncio.sleep(0)  # yield the loop
                continue
            if msg.error():
                log.error("Kafka error: %s", msg.error())
                continue

            if await handle_message(msg):
                consumer.commit(msg)  # ack only on success
    finally:
        consumer.close()
        log.info("Consumer closed.")


if __name__ == "__main__":
    asyncio.run(poll_forever())