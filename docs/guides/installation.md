# Installation Guide

This guide covers all the different ways to install Profilis and what each installation option provides.

## Prerequisites

- **Python**: 3.9 or higher
- **pip**: Latest version recommended
- **Virtual Environment**: Recommended for isolation

## Installation Methods

### Method 1: Using pip with extras (Recommended)

This is the most flexible and recommended approach:

```bash
# Core package only
pip install profilis

# With Flask support
pip install profilis[flask]

# With database support
pip install profilis[flask,sqlalchemy]

# With all integrations
pip install profilis[all]
```

**Available Extras:**
- `flask`: Flask framework integration
- `fastapi`: FastAPI framework integration (ASGI middleware + UI router)
- `sanic`: Sanic framework integration (native middleware + UI blueprint)
- `sqlalchemy`: SQLAlchemy database instrumentation
- `mongo`: MongoDB integration with PyMongo
- `neo4j`: Neo4j graph database integration
- `pyodbc`: pyodbc database instrumentation with raw cursor wrapper
- `perf`: Performance optimization with orjson
- `all`: All available integrations
- `dev`: Development dependencies

### Method 2: Using requirements files

For users who prefer requirements files:

```bash
# Minimal setup (core only)
pip install -r requirements-minimal.txt

# Flask integration
pip install -r requirements-flask.txt

# SQLAlchemy integration
pip install -r requirements-sqlalchemy.txt

# MongoDB integration
pip install -r requirements-mongo.txt

# All integrations
pip install -r requirements-all.txt
```

### Method 3: Manual installation

For complete control over dependencies:

```bash
# Core dependencies
pip install typing_extensions>=4.0

# Flask support
pip install flask[async]>=3.0

# SQLAlchemy support
pip install sqlalchemy>=2.0 aiosqlite greenlet

# MongoDB support
pip install pymongo>=4.3 motor>=3.3

# Neo4j support
pip install neo4j>=5.14

# pyodbc support
pip install pyodbc

# Performance optimization
pip install orjson>=3.8
```

## What Each Installation Provides

### Core Package (`pip install profilis`)

**Dependencies:**
- `typing_extensions>=4.0`

**Features:**
- AsyncCollector for non-blocking event collection
- Emitter for high-performance event creation
- Runtime context management
- Basic exporters (JSONL, Console)
- Function profiling decorator

**Use Case:** Basic profiling without framework integration

### Flask Integration (`pip install profilis[flask]`)

**Dependencies:**
- Core dependencies
- `flask[async]>=3.0`

**Features:**
- Everything from core
- Automatic Flask request/response profiling
- Built-in dashboard integration
- Route detection and sampling

**Use Case:** Flask web applications

### FastAPI Integration (`pip install profilis[fastapi]`)

**Dependencies:**
- Core dependencies
- `fastapi>=0.110`
- `starlette>=0.37`
- `httpx>=0.24.0`

**Features:**
- Everything from core
- ASGI middleware for automatic request/response profiling
- Route template detection (OpenAPI path formats)
- Optional built-in dashboard via `make_ui_router()`
- Configurable sampling and route exclusions

**Use Case:** FastAPI and other ASGI applications

### Sanic Integration (`pip install profilis[sanic]`)

**Dependencies:**
- Core dependencies
- `sanic>=23.0`

**Features:**
- Everything from core
- Native request/response/exception middleware
- Optional built-in dashboard via `make_ui_blueprint()`
- Configurable sampling and route exclusions
- Optional ASGI app mounting for UI (best-effort by Sanic version)

**Use Case:** Sanic web applications

### SQLAlchemy Integration (`pip install profilis[sqlalchemy]`)

**Dependencies:**
- Core dependencies
- `sqlalchemy>=2.0`
- `aiosqlite`
- `greenlet`

**Features:**
- Everything from core
- Automatic SQL query profiling
- Query redaction for security
- Performance metrics

**Use Case:** Applications using SQLAlchemy

### MongoDB Integration (`pip install profilis[mongo]`)

**Dependencies:**
- Core dependencies
- `pymongo>=4.3`
- `motor>=3.3`

**Features:**
- Everything from core
- Automatic MongoDB command profiling
- PyMongo and Motor support
- Command statistics extraction
- Error tracking and analysis

**Use Case:** Applications using MongoDB

### Neo4j Integration (`pip install profilis[neo4j]`)

**Dependencies:**
- Core dependencies
- `neo4j>=5.14`

**Features:**
- Everything from core
- Automatic Neo4j query profiling
- Session and transaction monitoring
- Cypher query analysis
- Graph metrics extraction

**Use Case:** Applications using Neo4j graph database

### pyodbc Integration (`pip install profilis[pyodbc]`)

**Dependencies:**
- Core dependencies
- `pyodbc`

**Features:**
- Everything from core
- Automatic pyodbc cursor profiling
- Raw cursor wrapper for execute/executemany operations
- SQL monitoring with parameter redaction
- Multi-vendor database support

**Use Case:** Applications using pyodbc with ODBC-compatible databases

### Performance Optimization (`pip install profilis[perf]`)

**Dependencies:**
- Core dependencies
- `orjson>=3.8`

**Features:**
- Everything from core
- Faster JSON serialization
- Reduced memory usage
- Better performance for high-throughput applications

**Use Case:** Production applications with high event volumes

### All Integrations (`pip install profilis[all]`)

**Dependencies:**
- All framework integrations
- All database integrations
- Performance optimizations

**Features:**
- Complete feature set
- All available integrations
- Maximum performance

**Use Case:** Applications using multiple frameworks/databases

## Development Installation

For contributors and developers:

```bash
# Clone the repository
git clone https://github.com/ankan97dutta/profilis.git
cd profilis

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Or use the requirements file
pip install -r requirements-dev.txt
```

## Virtual Environment Setup

**Recommended approach:**

```bash
# Create virtual environment
python -m venv profilis-env

# Activate virtual environment
# On Windows:
profilis-env\Scripts\activate
# On macOS/Linux:
source profilis-env/bin/activate

# Install Profilis
pip install profilis[flask,sqlalchemy]
```

## Production Installation

For production deployments:

```bash
# Install with specific versions for stability
pip install profilis[flask,sqlalchemy]==0.3.0

# Or use requirements file with pinned versions
pip install -r requirements-production.txt
```

## Troubleshooting Installation

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure core dependencies are installed
   pip install typing_extensions>=4.0
   ```

2. **Framework Integration Not Working**
   ```bash
   # Check if framework dependencies are installed
   pip list | grep flask
   pip list | grep sqlalchemy
   ```

3. **Performance Issues**
   ```bash
   # Install performance optimizations
   pip install profilis[perf]
   ```

4. **Version Conflicts**
   ```bash
   # Use virtual environment
   python -m venv profilis-env
   source profilis-env/bin/activate
   pip install profilis[flask,sqlalchemy]
   ```

### Dependency Resolution

If you encounter dependency conflicts:

```bash
# Check current environment
pip list

# Install with --force-reinstall if needed
pip install --force-reinstall profilis[flask]

# Or use pip-tools for dependency resolution
pip install pip-tools
pip-compile requirements-flask.txt
pip install -r requirements-flask.txt
```

## Platform-Specific Notes

### Windows

- Ensure Visual C++ build tools are installed for some dependencies
- Use `py` instead of `python` if you have multiple Python versions

### macOS

- Use Homebrew Python for better dependency management
- Some dependencies may require Xcode command line tools

### Linux

- Install development headers: `sudo apt-get install python3-dev`
- For pyodbc: `sudo apt-get install unixodbc-dev`

## Next Steps

After installation:

1. [Getting Started](getting-started.md) - Quick setup and basic usage
2. [Configuration](configuration.md) - Tuning and customization
3. [Framework Adapters](../adapters/flask.md) - Framework-specific integration
4. [Database Support](../databases/sqlalchemy.md) - Database instrumentation
5. [Exporters](../exporters/jsonl.md) - Output configuration
