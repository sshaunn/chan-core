# chan-core

A high-performance core computation engine library for Python.

## Requirements

- Python 3.9+
- See `requirements.txt` for dependencies

## Installation

```bash
# Development installation
pip install -e ".[dev]"

# Or with requirements.txt
pip install -r requirements.txt
```

## Development

### Code Style

This project uses:
- `black` for code formatting
- `isort` for import sorting
- `flake8` for linting
- `mypy` for type checking

Format code with:
```bash
black chan_core tests
isort chan_core tests
```

### Testing

Run tests with:
```bash
pytest
```

With coverage:
```bash
pytest --cov=chan_core
```

## Project Structure

```
chan-core/
├── chan_core/          # Main package
│   └── __init__.py
├── tests/              # Test suite
│   └── __init__.py
├── pyproject.toml      # Project configuration
├── requirements.txt    # Dependencies
└── README.md
```

## License

Apache License 2.0