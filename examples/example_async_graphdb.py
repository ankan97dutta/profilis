import asyncio

import neo4j
from neo4j import AsyncGraphDatabase

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
from profilis.neo4j.instrumentation import (
    Neo4jConfig,
    instrument_neo4j_module,
    instrument_neo4j_session,
)

jsonl_exporter = JSONLExporter(dir="./logs", rotate_bytes=1024, rotate_secs=5)
col = AsyncCollector(jsonl_exporter, queue_size=1024)
em = Emitter(col)

cfg = Neo4jConfig(preview_len=200, redact_cypher=True)
# Option A: instrument module so newly-created sessions are instrumented
instrument_neo4j_module(neo4j, em, cfg)


async def main() -> None:
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))
    async with driver.session() as sess:
        res = await sess.run("CREATE (n:Person {name:$name}) RETURN n", {"name": "Bob"})
        await res.consume()  # may be coroutine

    # Option B: instrument an existing session (non-invasive)
    async with driver.session() as sess2:
        instrument_neo4j_session(sess2, em, cfg)
        res = await sess2.run("MATCH (n) RETURN count(n)")
        await res.consume()


if __name__ == "__main__":
    asyncio.run(main())
