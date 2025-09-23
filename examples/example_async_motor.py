import asyncio
from typing import TYPE_CHECKING

from motor.motor_asyncio import AsyncIOMotorClient

if TYPE_CHECKING:
    pass

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener

jsonl_exporter = JSONLExporter(dir="./logs", rotate_bytes=1024, rotate_secs=5)
col = AsyncCollector(jsonl_exporter, queue_size=1024)
em = Emitter(col)
listener = ProfilisCommandListener(em, MongoConfig(preview_len=160, redact_collection=False))

# register listener with Motor client (Motor forwards event_listeners to pymongo client)
client = AsyncIOMotorClient(  # type: ignore[var-annotated]
    "mongodb://localhost:27017", event_listeners=[listener]
)


async def main() -> None:
    await client.mydb.users.insert_one({"x": 42})
    await client.mydb.users.find_one({"x": 42})


asyncio.run(main())
