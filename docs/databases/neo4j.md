# Neo4j Instrumentation

Profilis provides comprehensive instrumentation for Neo4j graph database operations, supporting both synchronous and asynchronous operations. This allows you to monitor Cypher queries, track performance metrics, and analyze graph database performance.

## Features

- **Session & Transaction Monitoring**: Automatic tracking of Neo4j sessions and transactions
- **Cypher Query Analysis**: Query execution time, result statistics, and performance metrics
- **Graph Metrics**: Node and relationship creation/modification counts
- **Error Tracking**: Detailed error information and failure analysis
- **Parameter Redaction**: Configurable parameter redaction for security
- **Query Preview**: Customizable query preview length for log readability

## Installation

Install Profilis with Neo4j support:

```bash
pip install profilis[neo4j]
```

This installs the required dependencies:
- `neo4j>=5.14` - Neo4j Python driver

## Basic Usage

### Synchronous Neo4j

```python
from profilis.neo4j.instrumentation import Neo4jConfig, instrument_neo4j_module
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
import neo4j
from neo4j import GraphDatabase

# Setup Profilis collector
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)

# Create Neo4j driver with instrumentation
config = Neo4jConfig(vendor_label="neo4j", preview_len=200, redact_cypher=True)
instrument_neo4j_module(neo4j, emitter, config)
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

# Use the driver normally
with driver.session() as session:
    # Create nodes
    result = session.run(
        "CREATE (p:Person {name: $name, age: $age}) RETURN p",
        name="Alice", age=30
    )

    # Query nodes
    result = session.run("MATCH (p:Person) WHERE p.age > $min_age RETURN p", min_age=25)
    people = list(result)
```

### Asynchronous Neo4j

```python
import asyncio
from profilis.neo4j.instrumentation import Neo4jConfig, instrument_neo4j_module
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
import neo4j
from neo4j import AsyncGraphDatabase

async def main():
    # Setup Profilis collector
    exporter = JSONLExporter(dir="./logs")
    collector = AsyncCollector(exporter)
    emitter = Emitter(collector)

    # Create async Neo4j driver with instrumentation
    config = Neo4jConfig(vendor_label="neo4j", preview_len=200, redact_cypher=True)
    instrument_neo4j_module(neo4j, emitter, config)
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

    # Use the driver normally
    async with driver.session() as session:
        # Create nodes
        result = await session.run(
            "CREATE (p:Person {name: $name, age: $age}) RETURN p",
            name="Bob", age=35
        )

        # Query nodes
        result = await session.run("MATCH (p:Person) WHERE p.age > $min_age RETURN p", min_age=30)
        people = await result.data()

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

### Neo4jConfig Options

```python
from profilis.neo4j.instrumentation import Neo4jConfig, instrument_neo4j_module

config = Neo4jConfig(
    vendor_label="neo4j",  # Custom vendor label for identification
    preview_len=150,  # Truncate query previews to 150 characters
    redact_cypher=True  # Whether to redact Cypher queries
)

instrument_neo4j_module(neo4j, emitter, config)
```

### Configuration Parameters

- **`vendor_label`**: Custom label to identify the database vendor (default: "neo4j")
- **`preview_len`**: Maximum length for query previews (default: 200)
- **`redact_cypher`**: Whether to redact Cypher queries (default: True)

## Monitored Operations

Profilis automatically tracks the following Neo4j operations:

### Session Operations
- `session.run()` - Execute Cypher queries
- `session.begin_transaction()` - Start transactions
- `session.close()` - Close sessions

### Transaction Operations
- `transaction.run()` - Execute queries within transactions
- `transaction.commit()` - Commit transactions
- `transaction.rollback()` - Rollback transactions

### Query Types
- **CREATE** - Node and relationship creation
- **MATCH** - Pattern matching queries
- **MERGE** - Create or match operations
- **DELETE** - Node and relationship deletion
- **SET** - Property updates
- **RETURN** - Result projection

## Metrics Extracted

For each Neo4j operation, Profilis extracts:

### Query Information
- **Query Text**: The Cypher query being executed (with preview truncation)
- **Parameters**: Query parameters (with redaction support)
- **Database**: Target database name
- **Transaction State**: Whether query is in a transaction

### Performance Metrics
- **Duration**: Query execution time in microseconds
- **Timestamp**: When the query was executed
- **Success/Failure**: Operation outcome

### Result Statistics
- **Nodes Created**: Number of nodes created
- **Relationships Created**: Number of relationships created
- **Properties Set**: Number of properties set
- **Labels Added**: Number of labels added
- **Indexes Added**: Number of indexes added
- **Constraints Added**: Number of constraints added

### Graph Metrics
- **Nodes Deleted**: Number of nodes deleted
- **Relationships Deleted**: Number of relationships deleted
- **Properties Removed**: Number of properties removed
- **Labels Removed**: Number of labels removed

### Error Information
- **Error Code**: Neo4j error code (if operation failed)
- **Error Message**: Detailed error description
- **Error Classification**: Error type classification

## Example Output

### Successful Query

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 2500,
  "query_type": "CREATE",
  "query_preview": "CREATE (p:Person {name: $name, age: $age}) RETURN p",
  "parameters": {"name": "Alice", "age": 30},
  "database": "neo4j",
  "result_stats": {
    "nodes_created": 1,
    "properties_set": 2,
    "labels_added": 1
  },
  "success": true
}
```

### Complex Query

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 5000,
  "query_type": "MATCH",
  "query_preview": "MATCH (p:Person)-[r:KNOWS]->(f:Person) WHERE p.age > $min_age RETURN p, f",
  "parameters": {"min_age": 25},
  "database": "neo4j",
  "result_stats": {
    "nodes_returned": 10,
    "relationships_returned": 15
  },
  "success": true
}
```

## Error Handling

Profilis provides comprehensive error tracking for Neo4j operations:

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 1000,
  "query_type": "CREATE",
  "query_preview": "CREATE (p:Person {name: $name}) RETURN p",
  "parameters": {"name": "Alice"},
  "database": "neo4j",
  "success": false,
  "error": {
    "code": "Neo.ClientError.Statement.SyntaxError",
    "message": "Invalid input 'P': expected whitespace, comment or ')' (line 1, column 8)",
    "classification": "ClientError"
  }
}
```

## Transaction Support

Profilis tracks transaction operations and their context:

```python
with driver.session() as session:
    with session.begin_transaction() as tx:
        # These operations will be tracked within the transaction context
        tx.run("CREATE (p:Person {name: 'Alice'})")
        tx.run("CREATE (p:Person {name: 'Bob'})")
        # Transaction commit/rollback will also be tracked
```

## Integration with Flask

```python
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.neo4j.instrumentation import Neo4jConfig, instrument_neo4j_module
from profilis.core.emitter import Emitter
import neo4j
from neo4j import GraphDatabase

app = Flask(__name__)

# Setup Profilis
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)
profilis = ProfilisFlask(app, collector=collector)

# Setup Neo4j with instrumentation
config = Neo4jConfig(vendor_label="neo4j", preview_len=200, redact_cypher=True)
instrument_neo4j_module(neo4j, emitter, config)
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

@app.route('/people')
def get_people():
    with driver.session() as session:
        result = session.run("MATCH (p:Person) RETURN p LIMIT 10")
        people = [record["p"] for record in result]
    return {"people": people}
```

## Advanced Features

### Custom Instrumentation

You can instrument specific sessions or transactions:

```python
from profilis.neo4j.instrumentation import instrument_neo4j_session

# Instrument a specific session
with driver.session() as session:
    instrument_neo4j_session(session, emitter, config)
    result = session.run("MATCH (p:Person) RETURN p")
```

### Tracing Integration

Profilis provides tracing context support:

```python
from profilis.runtime.context import get_current_parent_span_id

# Get current tracing context
parent_span_id = get_current_parent_span_id()
# Use in your application's tracing system
```

## Best Practices

1. **Parameter Redaction**: Always redact sensitive parameters in production
2. **Query Optimization**: Monitor slow queries and optimize Cypher patterns
3. **Transaction Management**: Use transactions for related operations
4. **Index Monitoring**: Track index usage and creation patterns
5. **Error Monitoring**: Monitor error patterns to identify issues

## Troubleshooting

### Common Issues

1. **Missing Events**: Ensure instrumentation is properly applied to the driver
2. **Performance Impact**: Profilis adds minimal overhead (~15µs per operation)
3. **Memory Usage**: Large query previews may increase memory usage

### Debug Mode

Enable debug logging to troubleshoot instrumentation:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Examples

See the complete examples in the repository:
- `examples/example_sync_graphdb.py` - Synchronous Neo4j usage
- `examples/example_async_graphdb.py` - Asynchronous Neo4j usage
