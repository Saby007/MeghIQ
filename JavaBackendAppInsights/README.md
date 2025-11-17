# Azure Monitoring Demo - Spring Boot 3.5.7

**Java Backend with Application Insights Integration**

## Overview
This is a production-ready Spring Boot application demonstrating Azure Application Insights integration and comprehensive monitoring capabilities for Mission Critical workloads.

## Key Features
- **Java 21**: Enterprise-grade runtime compatibility
- **Spring Boot 3.5.7**: Latest patch version with security updates
- **Azure Integration**: Application Insights monitoring and telemetry
- **Custom Metrics**: Request counters via Micrometer
- **Health Checks**: Built-in health endpoints and actuator integration
- **Clean Code**: Optimized codebase with no unused dependencies

## Live Demo
🌐 **Deployed Application**: [https://monitoring-demo-1763185446530.azurewebsites.net](https://monitoring-demo-1763185446530.azurewebsites.net)

## API Endpoints

### Core Endpoints
- `GET /` - Welcome message with version info
- `GET /health` - Application health status
- `GET /api/users/{id}` - User data simulation
- `GET /api/data?count=N` - Sample data generation
- `GET /api/error?throwError=true` - Error simulation for monitoring
- `GET /api/slow?delay=ms` - Performance testing endpoint

### Monitoring Endpoints
- `GET /actuator/health` - Detailed health information
- `GET /actuator/metrics` - Application metrics
- `GET /actuator/metrics/api.requests.total` - Custom request counter

## Quick Start

### Local Development
```bash
# Prerequisites: Java 21, Maven 3.6+
cd JavaBackendAppInsights
mvn clean spring-boot:run
```

### Azure Deployment
```bash
# Build and deploy to Azure App Service
mvn clean package
mvn azure-webapp:deploy
```

## Testing Examples
```bash
# Test main endpoint
curl https://monitoring-demo-1763185446530.azurewebsites.net/

# Check metrics
curl https://monitoring-demo-1763185446530.azurewebsites.net/actuator/metrics/api.requests.total

# Generate test data
curl "https://monitoring-demo-1763185446530.azurewebsites.net/api/data?count=5"
```

## Architecture
```
Client → Azure App Service (Java 21) → Application Insights → Monitoring Dashboard
```

## Built With
- Spring Boot 3.5.7
- Java 21 Runtime
- Azure Application Insights
- Micrometer Metrics
- Maven Build System
- Azure App Service Linux

## Deployment Status
✅ **Successfully deployed** with Spring Boot 3.5.7  
✅ **All tests passing** (4/4)  
✅ **Monitoring active** with request counting  
✅ **Code optimized** - removed unused dependencies  

---
*Part of SfMC India Team Projects - Mission Critical Solutions*