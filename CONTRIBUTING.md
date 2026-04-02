# Contributing to MeghIQ MCP Server

Thank you for your interest in contributing to the MeghIQ MCP Server!

## Getting Started

1. Fork the repository
2. Create a feature branch from `main`
3. Set up your development environment:

```bash
cd mcp-server
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and fill in your Azure subscription ID
5. Ensure you have `az login` configured with appropriate RBAC roles

## Development Guidelines

### Code Style

- Follow existing code conventions (PEP 8, type hints, docstrings)
- All public functions must have docstrings
- Use `async/await` for all Azure API calls
- Return standardised JSON via `response.py` helpers (`success_response`, `error_response`)

### Security Requirements

- **Input validation**: All user-provided identifiers (subscription IDs, resource names, resource IDs) must be validated using helpers from `tools/validators.py` before use in URLs or queries
- **KQL safety**: User inputs interpolated into KQL queries must pass through `sanitize_kql_input()`
- **Path safety**: File output paths must be validated with `validate_output_path()` or `validate_output_directory()`
- **XML parsing**: Use `defusedxml` instead of `xml.etree.ElementTree` for external XML
- **Error messages**: Use `sanitize_error_message()` to prevent leaking internal details
- **No hardcoded secrets**: Never commit `.env` files, API keys, subscription IDs, or credentials

### Adding a New Tool

1. Create a new module in `tools/` with your tool logic
2. Import and validate all user inputs using `tools/validators.py`
3. Return results via `response.py` helpers
4. Register the tool in `server.py` with a `@mcp.tool()` wrapper
5. Add documentation to the README Tools Reference section
6. Add tests in `tests/`

### Testing

```bash
# Start the server
python server.py

# Run smoke tests (requires running server + Azure credentials)
python tests/test_mcp.py
```

## Pull Request Process

1. Ensure all existing tests pass
2. Add tests for new functionality
3. Update the README if adding/changing tools
4. Keep PRs focused — one feature or fix per PR
5. Include a clear description of what changed and why

## Reporting Issues

When reporting bugs, please include:
- Python version and OS
- Steps to reproduce
- Expected vs actual behaviour
- Relevant error messages (redact any subscription IDs or secrets)

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
