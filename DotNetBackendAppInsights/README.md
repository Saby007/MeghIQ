# .NET Monitoring Demo Application

A comprehensive ASP.NET Core 8.0 application designed to demonstrate Azure Application Insights integration with live analytics dashboard, similar to the Java version but built with .NET technologies.

## 🚀 Features

### Live Analytics Dashboard
- **Real-time Metrics**: Live performance monitoring with auto-refresh every 3 seconds
- **Application Insights Style**: Dashboard styled to match Azure Application Insights interface
- **Comprehensive Statistics**: Server metrics, performance data, background job status, database health

### Test Endpoints
- **Health Check**: `/api/test/health` - Application and service health status
- **Latency Test**: `/api/test/latency?delay=500` - Configurable latency simulation
- **CPU Test**: `/api/test/cpu?duration=2000` - CPU intensive operations
- **Exception Test**: `/api/test/exception` - Exception handling and telemetry
- **Dependency Test**: `/api/test/dependency` - External API dependency calls
- **Database Test**: `/api/test/database?operation=create` - Database operations (create, read, update, delete)
- **Entity List**: `/api/test/entities` - View all database entities

### Background Services
- **Multi-threaded Processing**: 4 concurrent background job types
- **Realistic Failure Simulation**: Configurable failure rates (6.7% - 12.5%)
- **Entity Creation**: Automatic database entity generation during processing
- **Application Insights Telemetry**: Full telemetry tracking for all operations

## 🛠 Technology Stack

- **Framework**: ASP.NET Core 8.0
- **Runtime**: .NET 9.0 SDK
- **Database**: Entity Framework Core InMemory 8.0.11
- **Telemetry**: Microsoft Application Insights for ASP.NET Core 2.22.0
- **Background Services**: .NET Hosted Services with multi-threading
- **API Documentation**: Swagger/OpenAPI 3.0
- **Frontend**: HTML5, CSS3, JavaScript with Chart.js for real-time charts

## 📁 Project Structure

```
MonitoringDemo/
├── Controllers/
│   ├── DashboardController.cs    # Live analytics dashboard API
│   └── TestController.cs         # Comprehensive test endpoints
├── Data/
│   └── ApplicationDbContext.cs   # Entity Framework configuration
├── Models/
│   └── DemoEntity.cs            # Database entity model
├── Services/
│   ├── DatabaseService.cs       # Database operations service
│   ├── ExternalApiService.cs    # External API simulation service
│   └── BackgroundJobService.cs  # Multi-threaded background processor
├── Views/
│   └── dashboard.html           # Application Insights-style dashboard
├── Program.cs                   # Application configuration and startup
└── MonitoringDemo.csproj       # Project dependencies and configuration
```

## 🏃‍♂️ Getting Started

### Prerequisites
- .NET 9.0 SDK
- Azure CLI (for deployment)
- Git (for source control)

### Local Development

1. **Clone and Navigate**
   ```bash
   git clone https://github.com/ssamadda_microsoft/SfMC_Projects.git
   cd SfMC_Projects/DotNetBackendAppInsights/MonitoringDemo
   ```

2. **Restore Dependencies**
   ```bash
   dotnet restore
   ```

3. **Run the Application**
   ```bash
   dotnet run
   ```

4. **Access the Application**
   - Dashboard: http://localhost:5049/api/dashboard
   - Health Check: http://localhost:5049/api/test/health
   - Swagger UI: http://localhost:5049/swagger
   - All Test Endpoints: http://localhost:5049/api/test/*

### Key Endpoints

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/api/dashboard` | Live analytics dashboard (HTML) | Main monitoring interface |
| `/api/dashboard/stats` | JSON statistics API | Real-time metrics data |
| `/api/test/health` | Application health status | Service health check |
| `/api/test/latency?delay=1000` | Latency simulation | Performance testing |
| `/api/test/cpu?duration=3000` | CPU load testing | Resource utilization |
| `/api/test/exception` | Exception generation | Error handling testing |
| `/api/test/dependency` | External API calls | Dependency monitoring |
| `/api/test/database?operation=create` | Database operations | Data layer testing |
| `/api/test/entities` | View all entities | Database content inspection |

## 🔧 Configuration

### Application Settings
- **Application Insights**: Configure `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable
- **Database**: Uses Entity Framework InMemory for demo purposes
- **Background Jobs**: Multi-threaded processing with realistic failure rates
- **CORS**: Enabled for cross-origin requests during development

### Environment Variables
```bash
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=<your-key>;IngestionEndpoint=<endpoint>
ASPNETCORE_ENVIRONMENT=Development
```

## 🌐 Azure Deployment

### App Service Configuration
- **Runtime Stack**: .NET 8 (LTS)
- **Operating System**: Linux
- **SKU**: Premium V2 (for optimal performance)
- **Application Insights**: Integrated with existing monitoring-demo instance

### Deployment Script
```bash
# Build and publish the application
dotnet publish --configuration Release --output ./publish

# Deploy to Azure App Service
az webapp deploy \
  --name dotnet-monitoring-demo-1763185446530 \
  --resource-group monitoring-demo-1763185446530-rg \
  --src-path ./monitoring-demo.zip \
  --type zip
```

### Post-Deployment Verification
```bash
# Test the deployed application
curl https://dotnet-monitoring-demo-1763185446530.azurewebsites.net/api/test/health

# Access live dashboard
https://dotnet-monitoring-demo-1763185446530.azurewebsites.net/api/dashboard
```

## 📊 Monitoring and Observability

### Application Insights Integration
- **Custom Telemetry**: All operations tracked with Application Insights
- **Dependency Tracking**: External API calls and database operations
- **Exception Tracking**: Comprehensive error reporting with context
- **Performance Counters**: System metrics and custom performance data
- **Live Analytics**: Real-time dashboard with Chart.js visualization

### Background Job Monitoring
- **Job Statistics**: Success/failure rates, processing times
- **Entity Creation**: Automatic database entity generation during processing
- **Failure Simulation**: Realistic failure rates for testing
- **Telemetry Integration**: All background operations tracked

### Database Monitoring
- **Entity Tracking**: All database entities with creation timestamps
- **Health Monitoring**: Database connectivity and performance
- **Operation Metrics**: CRUD operation success/failure rates
- **InMemory Database**: Suitable for demo and development environments

## 🔄 Background Services

### Job Types
1. **Data Processing**: Simulates data processing with entity creation
2. **Entity Sync**: Synchronization operations with external systems
3. **Batch Processing**: Bulk data processing operations
4. **Cleanup**: Maintenance and cleanup operations

### Failure Simulation
- **Data Processing**: 6.7% failure rate
- **Entity Sync**: 8.3% failure rate  
- **Batch Processing**: 10.0% failure rate
- **Cleanup**: 12.5% failure rate

## 🎨 Dashboard Features

### Real-time Metrics
- **Request Statistics**: Total, successful, failed requests with average duration
- **Dependency Calls**: External API call metrics and failure tracking
- **Exception Monitoring**: Exception counts and types
- **Performance Metrics**: CPU, memory, and disk utilization
- **Background Jobs**: Job execution statistics and entity processing
- **Database Health**: Connection status, entity counts, response times
- **User Analytics**: Active users, sessions, and new user tracking

### Chart Visualizations
- **Performance Trends**: Line charts showing system performance over time
- **Job Success Rate**: Pie chart of background job success/failure rates
- **Request Distribution**: Bar chart of request types and volumes
- **System Resources**: Gauge charts for CPU and memory utilization

## 🛡️ Error Handling

- **Global Exception Handler**: Comprehensive error catching and logging
- **Application Insights Integration**: All exceptions automatically tracked
- **Graceful Degradation**: Service failures don't affect overall application health
- **Detailed Error Responses**: Structured error responses with correlation IDs

## 🧪 Testing

### Manual Testing
```bash
# Test all endpoints
curl http://localhost:5049/api/test/health
curl http://localhost:5049/api/test/latency?delay=1000
curl http://localhost:5049/api/test/cpu?duration=2000
curl http://localhost:5049/api/test/exception
curl http://localhost:5049/api/test/dependency
curl http://localhost:5049/api/test/database?operation=create
curl http://localhost:5049/api/test/entities
```

### Dashboard Testing
1. Open http://localhost:5049/api/dashboard
2. Verify all 6 statistics cards display data
3. Check that charts auto-refresh every 3 seconds
4. Confirm background job statistics update in real-time
5. Test responsive design on different screen sizes

## 📈 Performance

### Optimizations
- **Entity Framework InMemory**: Fast in-memory database for demos
- **Background Service Threading**: Efficient multi-threaded job processing
- **Application Insights**: Optimized telemetry collection
- **JSON Serialization**: Fast API response serialization
- **Chart.js**: Lightweight frontend charting library

### Scalability
- **Horizontal Scaling**: Designed for Azure App Service scaling
- **Resource Management**: Efficient memory and CPU utilization
- **Connection Pooling**: Optimized database connection handling
- **Async Operations**: Non-blocking I/O operations throughout

## 🔗 Related Projects

- **Java Version**: [JavaBackendAppInsights](../JavaBackendAppInsights/) - Equivalent Java Spring Boot application
- **Original Requirement**: Identical functionality with .NET technology stack

## 🤝 Contributing

This is a demonstration application for Azure Application Insights integration. For improvements or issues:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is for demonstration purposes and is part of the Microsoft SfMC (Sales, Marketing & Customer Experience) projects.

## 🆘 Troubleshooting

### Common Issues

1. **Application Won't Start**
   - Verify .NET 9.0 SDK is installed
   - Check for port conflicts (default: 5049)
   - Ensure all NuGet packages are restored

2. **Dashboard Not Loading**
   - Check that the application is running
   - Verify `/api/dashboard/stats` endpoint returns JSON data
   - Check browser console for JavaScript errors

3. **Background Jobs Not Running**
   - Check application logs for service startup messages
   - Verify database connectivity
   - Check for resource constraints

4. **Azure Deployment Issues**
   - Verify Application Insights connection string is configured
   - Check build logs for compilation errors
   - Ensure correct runtime stack (.NET 8) is selected

### Support

For issues specific to this demonstration application, please check the project documentation or create an issue in the repository.