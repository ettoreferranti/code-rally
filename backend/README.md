# CodeRally Backend

FastAPI backend server for CodeRally racing game.

## Requirements

- Python 3.11+
- pip

## Quick Start

### 1. Run Development Server

The easiest way to get started:

```bash
./run_dev.sh
```

This script will:
- Create a virtual environment (if needed)
- Install all dependencies
- Start the server with auto-reload

### 2. Manual Setup

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scriptsctivate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once the server is running, visit:

- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

## Testing

Run tests with pytest:

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_health.py -v
```

## Project Structure

```
backend/
├── app/
│   ├── api/              # API routes and endpoints
│   │   └── routes/
│   │       └── health.py # Health check endpoints
│   ├── core/             # Game engine (physics, track, etc.)
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   ├── bot_runtime/      # Bot sandbox execution
│   ├── config.py         # Configuration
│   └── database.py       # Database setup
├── data/                 # SQLite database files
├── tests/                # Test files
├── main.py               # FastAPI application
├── requirements.txt      # Python dependencies
├── pytest.ini            # Pytest configuration
└── run_dev.sh            # Development server script
```

## Configuration

Server settings can be modified in `app/config.py`:

- Server host and port
- Database location
- Game physics parameters
- Bot execution limits
- CORS origins

## Database

The application uses SQLite with the database file stored at:
```
backend/data/coderally.db
```

The database is automatically created on first run.

## Development

### Code Style

- Use type hints for all functions
- Follow PEP 8 style guide
- Document with docstrings

### Running with Different Ports

```bash
uvicorn main:app --reload --port 8080
```

### Debug Mode

Debug mode is enabled by default in development. To disable:

Edit `app/config.py` and set:
```python
DEBUG: bool = False
```

## Common Issues

### Port Already in Use

If port 8000 is already in use:
```bash
uvicorn main:app --reload --port 8080
```

### Database Locked

If you get database locked errors, ensure no other processes are accessing the database file.

## Next Steps

See `CLAUDE.md` in the project root for:
- Implementation guidelines
- Architecture documentation
- Development workflow
