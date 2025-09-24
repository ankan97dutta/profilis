# MongoDB Instrumentation

Profilis provides comprehensive instrumentation for MongoDB operations using PyMongo. This allows you to monitor database queries, track performance metrics, and identify bottlenecks in your MongoDB operations.

## Features

- **Command Monitoring**: Automatic tracking of MongoDB commands (find, insert, update, delete, etc.)
- **Performance Metrics**: Query execution time, document counts, and operation statistics
- **Error Tracking**: Detailed error information and failure analysis
- **Collection Redaction**: Configurable collection name redaction for security
- **Preview Truncation**: Customizable query preview length for log readability

## Installation

Install Profilis with MongoDB support:

```bash
pip install profilis[mongo]
```

This installs the required dependencies:
- `pymongo>=4.3` - MongoDB driver
- `motor>=3.3` - Async MongoDB driver

## Basic Usage

### Synchronous PyMongo

```python
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
import pymongo

# Setup Profilis collector
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)

# Create MongoDB client with Profilis instrumentation
config = MongoConfig(vendor_label="mongodb", preview_len=160, redact_collection=False)
listener = ProfilisCommandListener(emitter, config)
client = pymongo.MongoClient("mongodb://localhost:27017/", event_listeners=[listener])

# Use the client normally
db = client.test_db
collection = db.users

# MongoDB operations will be automatically profiled
result = collection.insert_one({"name": "John", "email": "john@example.com"})
users = list(collection.find({"name": "John"}))
```

### Asynchronous Motor

```python
import asyncio
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    # Setup Profilis collector
    exporter = JSONLExporter(dir="./logs")
    collector = AsyncCollector(exporter)
    emitter = Emitter(collector)

    # Create Motor client with Profilis instrumentation
    config = MongoConfig(vendor_label="mongodb", preview_len=160, redact_collection=False)
    listener = ProfilisCommandListener(emitter, config)
    client = AsyncIOMotorClient("mongodb://localhost:27017/", event_listeners=[listener])

    # Use the client normally
    db = client.test_db
    collection = db.users

    # MongoDB operations will be automatically profiled
    await collection.insert_one({"name": "Jane", "email": "jane@example.com"})
    users = await collection.find({"name": "Jane"}).to_list(length=100)

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

### MongoConfig Options

```python
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener

config = MongoConfig(
    vendor_label="mongodb",  # Custom vendor label
    preview_len=100,  # Truncate query previews to 100 characters
    redact_collection=False  # Whether to redact collection names
)

listener = ProfilisCommandListener(emitter, config)
```

### Configuration Parameters

- **`vendor_label`**: Custom label to identify the database vendor (default: "mongodb")
- **`preview_len`**: Maximum length for query previews (default: 160)
- **`redact_collection`**: Whether to redact collection names (default: False)

## Monitored Operations

Profilis automatically tracks the following MongoDB operations:

### Read Operations
- `find` - Document queries
- `findOne` - Single document retrieval
- `aggregate` - Aggregation pipelines
- `count` - Document counting
- `distinct` - Distinct value queries

### Write Operations
- `insert` - Document insertion
- `update` - Document updates
- `delete` - Document deletion
- `findAndModify` - Atomic find and modify operations

### Administrative Operations
- `createIndex` - Index creation
- `dropIndex` - Index removal
- `listCollections` - Collection listing
- `listIndexes` - Index listing

## Metrics Extracted

For each MongoDB operation, Profilis extracts:

### Command Information
- **Command Name**: The MongoDB command being executed
- **Collection**: Target collection name (with redaction support)
- **Database**: Target database name
- **Query**: Query parameters and filters
- **Options**: Command options and modifiers

### Performance Metrics
- **Duration**: Command execution time in microseconds
- **Timestamp**: When the command was executed
- **Success/Failure**: Operation outcome

### Result Statistics
- **Documents Returned**: Number of documents in result
- **Documents Modified**: Number of documents modified (for write operations)
- **Documents Matched**: Number of documents matched (for update operations)
- **Indexes Used**: Information about indexes utilized

### Error Information
- **Error Code**: MongoDB error code (if operation failed)
- **Error Message**: Detailed error description
- **Error Labels**: Additional error categorization

## Example Output

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 1250,
  "command": "find",
  "collection": "users",
  "database": "test_db",
  "query_preview": "{\"name\": \"John\", \"status\": \"active\"}",
  "options": {"limit": 10, "sort": {"created_at": -1}},
  "result_stats": {
    "n_returned": 5,
    "execution_time_ms": 1.25
  },
  "success": true
}
```

## Error Handling

Profilis provides comprehensive error tracking for MongoDB operations:

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 500,
  "command": "insert",
  "collection": "users",
  "database": "test_db",
  "query_preview": "{\"name\": \"John\", \"email\": \"invalid-email\"}",
  "success": false,
  "error": {
    "code": 11000,
    "message": "E11000 duplicate key error collection: test_db.users index: email_1 dup key: { email: \"invalid-email\" }",
    "labels": ["DuplicateKey"]
  }
}
```

## Integration with Flask

```python
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener
from profilis.core.emitter import Emitter
import pymongo

app = Flask(__name__)

# Setup Profilis
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)
profilis = ProfilisFlask(app, collector=collector)

# Setup MongoDB with instrumentation
config = MongoConfig(vendor_label="mongodb", preview_len=160, redact_collection=False)
listener = ProfilisCommandListener(emitter, config)
client = pymongo.MongoClient("mongodb://localhost:27017/", event_listeners=[listener])

@app.route('/users')
def get_users():
    db = client.test_db
    users = list(db.users.find())
    return {"users": users}
```

## Best Practices

1. **Collection Redaction**: Always redact sensitive collection names in production
2. **Preview Length**: Adjust preview length based on your logging requirements
3. **Error Monitoring**: Monitor error patterns to identify database issues
4. **Performance Tracking**: Use duration metrics to identify slow queries
5. **Index Analysis**: Review index usage patterns for optimization

## Troubleshooting

### Common Issues

1. **Missing Events**: Ensure the command listener is properly attached to the MongoDB client
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
- `examples/example_sync_pymongo.py` - Synchronous PyMongo usage
- `examples/example_async_motor.py` - Asynchronous Motor usage
