from typing import TYPE_CHECKING

from pymongo import MongoClient

if TYPE_CHECKING:
    pass

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener

# Setup exporters
jsonl_exporter = JSONLExporter(dir="./logs", rotate_bytes=1024, rotate_secs=5)
col = AsyncCollector(jsonl_exporter, queue_size=1024)
em = Emitter(col)
listener = ProfilisCommandListener(
    em, MongoConfig(vendor_label="mongodb", preview_len=160, redact_collection=False)
)

# register listener on MongoClient
client = MongoClient("mongodb://localhost:27017", event_listeners=[listener])  # type: ignore[var-annotated]
db = client.mydb
db.users.find_one({"x": 1})
