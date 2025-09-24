# pyodbc Instrumentation

Profilis provides comprehensive instrumentation for pyodbc database operations through a non-invasive raw cursor wrapper. This allows you to monitor SQL queries, track performance metrics, and identify bottlenecks in your pyodbc database operations.

## Features

- **Non-Invasive Wrapping**: Raw cursor wrapper that preserves original cursor semantics
- **SQL Monitoring**: Automatic tracking of SQL text with optional redaction
- **Performance Metrics**: Query execution time and row count tracking
- **Parameter Analysis**: Parameter preview with configurable redaction
- **Error Tracking**: Detailed error information and failure analysis
- **Vendor Support**: Configurable vendor labeling for different database systems

## Installation

Install Profilis with pyodbc support:

```bash
pip install profilis[pyodbc]
```

This installs the required dependencies:
- `pyodbc` - Python ODBC database driver

## Basic Usage

### Basic Cursor Wrapping

```python
from profilis.pyodbc.instrumentation import PyODBCConfig, instrument_pyodbc_cursor
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
import pyodbc

# Setup Profilis collector
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)

# Create pyodbc connection
conn = pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=testdb;UID=user;PWD=password")

# Get cursor and instrument it
cursor = conn.cursor()
config = PyODBCConfig(vendor_label="SQL Server", redact_statements=True, preview_len=200, redact_params=True)
instrument_pyodbc_cursor(cursor, emitter, config)

# Use the cursor normally - all operations will be profiled
cursor.execute("SELECT * FROM users WHERE age > ?", 25)
rows = cursor.fetchall()

cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", "John", "john@example.com")
cursor.commit()
```

### Advanced Configuration

```python
from profilis.pyodbc.instrumentation import PyODBCConfig, instrument_pyodbc_cursor

config = PyODBCConfig(
    vendor_label="SQL Server",  # Custom vendor label
    preview_len=100,  # Truncate SQL previews to 100 characters
    redact_statements=True,  # Whether to redact SQL statements
    redact_params=True  # Whether to redact parameters
)

instrument_pyodbc_cursor(cursor, emitter, config)
```

### Batch Operations

```python
# Profilis automatically tracks executemany operations
data = [
    ("Alice", "alice@example.com"),
    ("Bob", "bob@example.com"),
    ("Charlie", "charlie@example.com")
]

cursor.executemany("INSERT INTO users (name, email) VALUES (?, ?)", data)
cursor.commit()
```

## Configuration

### PyODBCConfig Options

```python
from profilis.pyodbc.instrumentation import PyODBCConfig

config = PyODBCConfig(
    vendor_label="PostgreSQL",  # Custom vendor label for identification
    preview_len=150,  # Maximum length for SQL previews (default: 200)
    redact_statements=True,  # Whether to redact SQL statements (default: True)
    redact_params=True  # Whether to redact parameters (default: True)
)
```

### Configuration Parameters

- **`vendor_label`**: Custom label to identify the database vendor (default: "pyodbc")
- **`preview_len`**: Maximum length for SQL previews (default: 200)
- **`redact_statements`**: Whether to redact SQL statements (default: True)
- **`redact_params`**: Whether to redact parameters (default: True)

## Monitored Operations

Profilis automatically tracks the following pyodbc operations:

### Cursor Methods
- `cursor.execute()` - Single SQL statement execution
- `cursor.executemany()` - Batch SQL statement execution
- `cursor.fetchone()` - Fetch single row
- `cursor.fetchall()` - Fetch all rows
- `cursor.fetchmany()` - Fetch multiple rows

### Connection Methods
- `connection.commit()` - Transaction commit
- `connection.rollback()` - Transaction rollback

## Metrics Extracted

For each pyodbc operation, Profilis extracts:

### SQL Information
- **SQL Text**: The SQL statement being executed (with redaction support)
- **Parameters**: Query parameters (with redaction support)
- **Vendor Label**: Database vendor identification
- **Operation Type**: execute or executemany

### Performance Metrics
- **Duration**: Query execution time in microseconds
- **Timestamp**: When the query was executed
- **Success/Failure**: Operation outcome
- **Row Count**: Number of rows affected/returned

### Error Information
- **Error Code**: pyodbc error code (if operation failed)
- **Error Message**: Detailed error description
- **SQL State**: SQL state information

## Example Output

### Successful Query

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 1500,
  "vendor": "SQL Server",
  "operation": "execute",
  "sql_preview": "SELECT * FROM users WHERE age > ?",
  "parameters": [25],
  "row_count": 5,
  "success": true
}
```

### Batch Operation

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 3000,
  "vendor": "PostgreSQL",
  "operation": "executemany",
  "sql_preview": "INSERT INTO users (name, email) VALUES (?, ?)",
  "parameters": [["Alice", "alice@example.com"], ["Bob", "bob@example.com"]],
  "row_count": 2,
  "success": true
}
```

## Error Handling

Profilis provides comprehensive error tracking for pyodbc operations:

```json
{
  "event_type": "DB_META",
  "timestamp": "2025-09-24T10:30:45.123456Z",
  "duration_us": 500,
  "vendor": "SQL Server",
  "operation": "execute",
  "sql_preview": "INSERT INTO users (name, email) VALUES (?, ?)",
  "parameters": ["John", "invalid-email"],
  "success": false,
  "error": {
    "code": "23000",
    "message": "UNIQUE constraint failed: users.email",
    "sql_state": "23000"
  }
}
```

## Integration with Flask

```python
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.pyodbc.instrumentation import PyODBCConfig, instrument_pyodbc_cursor
from profilis.core.emitter import Emitter
import pyodbc

app = Flask(__name__)

# Setup Profilis
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)
profilis = ProfilisFlask(app, collector=collector)

# Setup pyodbc with instrumentation
conn = pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=testdb;UID=user;PWD=password")

@app.route('/users')
def get_users():
    cursor = conn.cursor()
    config = PyODBCConfig(vendor_label="SQL Server", redact_statements=True, preview_len=200, redact_params=True)
    instrument_pyodbc_cursor(cursor, emitter, config)

    cursor.execute("SELECT * FROM users WHERE active = ?", 1)
    users = cursor.fetchall()

    return {"users": [dict(user) for user in users]}
```

## Advanced Usage

### Custom Vendor Configuration

```python
# Different configurations for different database vendors
sql_server_config = PyODBCConfig(
    vendor_label="SQL Server",
    redact_statements=True,
    preview_len=200
)

postgres_config = PyODBCConfig(
    vendor_label="PostgreSQL",
    redact_statements=True,
    preview_len=150
)

# Apply different configs based on connection
if "SQL Server" in connection_string:
    instrument_pyodbc_cursor(cursor, emitter, sql_server_config)
else:
    instrument_pyodbc_cursor(cursor, emitter, postgres_config)
```

### Transaction Monitoring

```python
# Profilis tracks transaction operations
try:
    cursor.execute("INSERT INTO users (name) VALUES (?)", "Alice")
    cursor.execute("INSERT INTO users (name) VALUES (?)", "Bob")
    conn.commit()  # This will be tracked
except Exception:
    conn.rollback()  # This will also be tracked
```

### Connection Pool Integration

```python
# Works with connection pools
from pyodbc import pool

# Create connection pool
pool = pyodbc.pool(connection_string, min_connections=1, max_connections=10)

# Get connection and instrument cursor
conn = pool.get_connection()
cursor = conn.cursor()
config = PyODBCConfig(vendor_label="SQL Server", redact_statements=True, preview_len=200, redact_params=True)
instrument_pyodbc_cursor(cursor, emitter, config)

# Use normally
cursor.execute("SELECT * FROM users")
```

## Best Practices

1. **Parameter Redaction**: Always redact sensitive parameters in production
2. **SQL Redaction**: Use statement redaction for sensitive SQL patterns
3. **Vendor Labeling**: Use descriptive vendor labels for multi-database environments
4. **Error Monitoring**: Monitor error patterns to identify database issues
5. **Performance Tracking**: Use duration metrics to identify slow queries

## Supported Database Vendors

Profilis pyodbc instrumentation works with any ODBC-compatible database:

- **Microsoft SQL Server**
- **PostgreSQL**
- **MySQL**
- **Oracle**
- **IBM DB2**
- **SQLite**
- **Any ODBC-compatible database**

## Troubleshooting

### Common Issues

1. **Missing Events**: Ensure the cursor is properly instrumented before use
2. **Performance Impact**: Profilis adds minimal overhead (~15µs per operation)
3. **Memory Usage**: Large SQL previews may increase memory usage

### Debug Mode

Enable debug logging to troubleshoot instrumentation:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Cursor Semantics Preservation

The instrumentation preserves all original cursor semantics:

```python
# Original behavior is preserved
result = cursor.execute("SELECT * FROM users")
# result is the original cursor object

# Exceptions are re-raised
try:
    cursor.execute("INVALID SQL")
except pyodbc.Error as e:
    # Original exception is preserved
    print(f"Error: {e}")
```

## Examples

See the complete examples in the repository:
- `tests/test_pyodbc_instrumentation.py` - Comprehensive test suite
- Integration examples with various database vendors

## Performance Considerations

- **Overhead**: ~15µs per operation
- **Memory**: ~100 bytes per event
- **Throughput**: 100K+ operations/second
- **Non-blocking**: All instrumentation is asynchronous
