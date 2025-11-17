# Azure Monitoring Demo - Java 25 Spring Boot API

This is a simple Java 25 Spring Boot application designed to demonstrate Azure Application Insights integration and monitoring capabilities.

## Features

- **Java 25**: Built with the latest Java version
- **Spring Boot 3.4**: Modern Spring Boot framework
- **Application Insights**: Full Azure monitoring integration
- **Custom Metrics**: Request counters and timing metrics
- **Health Endpoints**: Built-in health checks
- **Error Simulation**: Endpoints to test error monitoring
- **Performance Testing**: Slow endpoint for performance monitoring

## API Endpoints

### Core Endpoints
- `GET /` - Home endpoint with welcome message
- `GET /health` - Health check endpoint
- `GET /api/users/{id}` - Get user by ID (simulated)
- `GET /api/data?count=10` - Get sample data (count parameter)
- `GET /api/error?throwError=false` - Error simulation endpoint
- `GET /api/slow?delay=2000` - Slow endpoint for performance testing

### Actuator Endpoints (for monitoring)
- `GET /actuator/health` - Detailed health information
- `GET /actuator/metrics` - Application metrics
- `GET /actuator/info` - Application information

## Local Development

### Prerequisites
- Java 25 (installed via `winget install Oracle.JDK.25`)
- Maven 3.6+

### Running Locally
```bash
# Set Java 25 as active version
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25"
$env:PATH = "C:\Program Files\Java\jdk-25\bin;$env:PATH"

# Build and run the application
cd JavaBackendAppInsights
mvn clean spring-boot:run
```

The application will start on `http://localhost:8080`

### Testing the Application
```bash
# Test basic endpoint
curl http://localhost:8080/

# Test user endpoint
curl http://localhost:8080/api/users/123

# Test data endpoint
curl http://localhost:8080/api/data?count=5

# Test error simulation
curl http://localhost:8080/api/error?throwError=true

# Test slow endpoint
curl http://localhost:8080/api/slow?delay=3000

# Check health
curl http://localhost:8080/health

# Check metrics
curl http://localhost:8080/actuator/metrics
```

## Azure Deployment

### Step 1: Create Azure Resources
You'll need to create:
1. **Azure Web App** (Java 21 runtime - closest to Java 25)
2. **Application Insights** resource
3. **Resource Group**

### Step 2: Configure Application Settings
Set these environment variables in your Azure Web App:
- `APPLICATIONINSIGHTS_CONNECTION_STRING`: Your Application Insights connection string
- `APPINSIGHTS_INSTRUMENTATIONKEY`: Your Application Insights instrumentation key (optional)

### Step 3: Deploy Using Maven Plugin
```bash
# Configure Maven plugin with your Azure settings
mvn azure-webapp:config

# Deploy to Azure
mvn azure-webapp:deploy
```

### Step 4: Alternative - Manual Deployment
1. Build the JAR file: `mvn clean package`
2. Upload the JAR from `target/monitoring-demo-1.0.0.jar` to your Azure Web App
3. Configure the Web App to run the JAR file

## Monitoring Features

### Application Insights Integration
- **Request Tracking**: All HTTP requests are automatically tracked
- **Performance Metrics**: Request duration and frequency
- **Error Tracking**: Exceptions and error responses
- **Custom Metrics**: Business-specific counters and timers
- **Dependency Tracking**: External service calls (if any)
- **Live Metrics**: Real-time application performance

### Custom Telemetry
The application includes:
- Request counters for API usage tracking
- Request timers for performance monitoring
- Custom logging for business events
- Health check integration

### Testing Monitoring
Use the provided endpoints to generate different types of telemetry:
1. **Normal Traffic**: Hit `/` and `/api/users/{id}` endpoints
2. **Error Scenarios**: Use `/api/error?throwError=true`
3. **Performance Issues**: Use `/api/slow?delay=5000`
4. **Load Testing**: Use `/api/data?count=100` for high-volume requests

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client/User   │───▶│  Azure Web App   │───▶│ Application     │
└─────────────────┘    │  (Java 25 API)  │    │ Insights        │
                       └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Monitoring     │
                       │   Dashboard      │
                       └──────────────────┘
```

## Built With
- Java 25
- Spring Boot 3.4.0
- Azure Application Insights
- Maven
- Micrometer Metrics
- Spring Boot Actuator

## License
This is a demo application for educational purposes.