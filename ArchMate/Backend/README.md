# Health API

FastAPI application with health check endpoints, ready for Azure Web App deployment.

## Endpoints

- `GET /` - Root endpoint with welcome message
- `GET /health` - Basic health check endpoint
- `GET /health/detailed` - Detailed health information with environment details
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:8000`

## Azure Web App Deployment

This application is configured for Azure Web App deployment:

- Environment variables are read automatically (`PORT`, `WEBSITE_HOSTNAME`)
- `startup.txt` contains the production startup command
- Health endpoints can be used for Azure monitoring and availability checks

### Environment Variables

- `PORT` - Port number (default: 8000, Azure sets this automatically)
- `ENVIRONMENT` - Environment name (development, staging, production)
- `WEBSITE_HOSTNAME` - Hostname (Azure sets this automatically)

## Extending the API

To add new endpoints, simply add new route functions in `app.py`:

```python
@app.get("/your-endpoint")
async def your_function():
    return {"message": "Your response"}
```
