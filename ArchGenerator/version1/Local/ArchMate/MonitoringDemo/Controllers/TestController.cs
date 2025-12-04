using Microsoft.AspNetCore.Mvc;
using Microsoft.ApplicationInsights;
using Microsoft.ApplicationInsights.DataContracts;
using MonitoringDemo.Services;
using System.Diagnostics;
using System.Text.Json;

namespace MonitoringDemo.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class TestController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;
        private readonly IExternalApiService _externalApiService;
        private readonly TelemetryClient _telemetryClient;
        private readonly ILogger<TestController> _logger;
        private static readonly Random _random = new();
        
        public TestController(
            IDatabaseService databaseService,
            IExternalApiService externalApiService,
            TelemetryClient telemetryClient,
            ILogger<TestController> logger)
        {
            _databaseService = databaseService;
            _externalApiService = externalApiService;
            _telemetryClient = telemetryClient;
            _logger = logger;
        }
        
        [HttpGet("latency")]
        public async Task<IActionResult> TestLatency([FromQuery] int delay = 0)
        {
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                // Add random base latency
                var baseDelay = _random.Next(50, 200);
                var totalDelay = baseDelay + delay;
                
                _logger.LogInformation("Testing latency with {Delay}ms delay", totalDelay);
                
                await Task.Delay(totalDelay);
                
                stopwatch.Stop();
                
                var result = new
                {
                    message = "Latency test completed",
                    requestedDelay = delay,
                    actualDelay = totalDelay,
                    processingTime = stopwatch.ElapsedMilliseconds,
                    timestamp = DateTime.UtcNow
                };
                
                _telemetryClient.TrackDependency("LatencyTest", "ProcessDelay", 
                    Guid.NewGuid().ToString(), DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, true);
                
                return Ok(result);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "Latency test failed");
                _telemetryClient.TrackException(ex);
                return StatusCode(500, new { error = "Latency test failed", message = ex.Message });
            }
        }
        
        [HttpGet("cpu")]
        public IActionResult TestCpu([FromQuery] int intensity = 1)
        {
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                _logger.LogInformation("Testing CPU with intensity {Intensity}", intensity);
                
                // Simulate CPU intensive work
                var iterations = Math.Max(1, Math.Min(intensity, 10)) * 100000;
                double result = 0;
                
                for (int i = 0; i < iterations; i++)
                {
                    result += Math.Sqrt(i) * Math.Sin(i) * Math.Cos(i);
                }
                
                stopwatch.Stop();
                
                var response = new
                {
                    message = "CPU test completed",
                    intensity = intensity,
                    iterations = iterations,
                    result = Math.Round(result, 2),
                    processingTime = stopwatch.ElapsedMilliseconds,
                    timestamp = DateTime.UtcNow
                };
                
                _telemetryClient.TrackMetric("CpuTestIntensity", intensity);
                _telemetryClient.TrackMetric("CpuTestDuration", stopwatch.ElapsedMilliseconds);
                
                return Ok(response);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "CPU test failed");
                _telemetryClient.TrackException(ex);
                return StatusCode(500, new { error = "CPU test failed", message = ex.Message });
            }
        }
        
        [HttpGet("exception")]
        public IActionResult TestException([FromQuery] string type = "generic")
        {
            try
            {
                _logger.LogInformation("Testing exception of type {Type}", type);
                
                switch (type.ToLower())
                {
                    case "null":
                        throw new NullReferenceException("Simulated null reference exception");
                    case "argument":
                        throw new ArgumentException("Simulated argument exception", nameof(type));
                    case "invalid":
                        throw new InvalidOperationException("Simulated invalid operation exception");
                    case "timeout":
                        throw new TimeoutException("Simulated timeout exception");
                    case "unauthorized":
                        throw new UnauthorizedAccessException("Simulated unauthorized access exception");
                    case "notfound":
                        throw new FileNotFoundException("Simulated file not found exception");
                    default:
                        throw new Exception($"Simulated generic exception for type: {type}");
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Exception test executed: {ExceptionType}", type);
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "TestType", "ExceptionTest" },
                    { "ExceptionCategory", type }
                });
                
                return StatusCode(500, new
                {
                    error = "Exception test executed successfully",
                    exceptionType = ex.GetType().Name,
                    message = ex.Message,
                    testType = type,
                    timestamp = DateTime.UtcNow
                });
            }
        }
        
        [HttpGet("dependency")]
        public async Task<IActionResult> TestDependency([FromQuery] string endpoint = "get")
        {
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                _logger.LogInformation("Testing external dependency: {Endpoint}", endpoint);
                
                var result = await _externalApiService.CallExternalApiAsync(endpoint);
                
                stopwatch.Stop();
                
                var response = new
                {
                    message = "Dependency test completed",
                    endpoint = endpoint,
                    success = true,
                    responseLength = result.Length,
                    processingTime = stopwatch.ElapsedMilliseconds,
                    timestamp = DateTime.UtcNow
                };
                
                return Ok(response);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "Dependency test failed for endpoint {Endpoint}", endpoint);
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "TestType", "DependencyTest" },
                    { "Endpoint", endpoint }
                });
                
                return StatusCode(500, new
                {
                    error = "Dependency test failed",
                    endpoint = endpoint,
                    message = ex.Message,
                    processingTime = stopwatch.ElapsedMilliseconds,
                    timestamp = DateTime.UtcNow
                });
            }
        }
        
        [HttpGet("database")]
        public async Task<IActionResult> TestDatabase([FromQuery] string operation = "read")
        {
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                _logger.LogInformation("Testing database operation: {Operation}", operation);
                
                object result;
                
                switch (operation.ToLower())
                {
                    case "create":
                        var entityName = $"TestEntity-{DateTime.Now:HHmmssff}";
                        var createdEntity = await _databaseService.CreateEntityAsync(entityName);
                        result = new { operation = "create", entity = createdEntity };
                        break;
                        
                    case "read":
                        var entities = await _databaseService.GetAllEntitiesAsync();
                        result = new { operation = "read", count = entities.Count(), entities = entities.Take(5) };
                        break;
                        
                    case "count":
                        var count = await _databaseService.GetEntityCountAsync();
                        result = new { operation = "count", totalEntities = count };
                        break;
                        
                    case "health":
                        var isHealthy = await _databaseService.IsHealthyAsync();
                        result = new { operation = "health", isHealthy = isHealthy };
                        break;
                        
                    default:
                        throw new ArgumentException($"Unknown database operation: {operation}");
                }
                
                stopwatch.Stop();
                
                var response = new
                {
                    message = "Database test completed",
                    operation = operation,
                    result = result,
                    processingTime = stopwatch.ElapsedMilliseconds,
                    timestamp = DateTime.UtcNow
                };
                
                _telemetryClient.TrackDependency("Database", operation, 
                    Guid.NewGuid().ToString(), DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, true);
                
                return Ok(response);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "Database test failed for operation {Operation}", operation);
                
                _telemetryClient.TrackDependency("Database", operation, 
                    Guid.NewGuid().ToString(), DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, false);
                
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "TestType", "DatabaseTest" },
                    { "Operation", operation }
                });
                
                return StatusCode(500, new
                {
                    error = "Database test failed",
                    operation = operation,
                    message = ex.Message,
                    processingTime = stopwatch.ElapsedMilliseconds,
                    timestamp = DateTime.UtcNow
                });
            }
        }
        
        [HttpGet("entities")]
        public async Task<IActionResult> GetDatabaseEntities()
        {
            try
            {
                var entities = await _databaseService.GetAllEntitiesAsync();
                var count = await _databaseService.GetEntityCountAsync();
                
                var response = new
                {
                    message = "Database entities retrieved successfully",
                    totalCount = count,
                    entities = entities.OrderByDescending(e => e.CreatedAt).Take(20),
                    timestamp = DateTime.UtcNow
                };
                
                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to retrieve database entities");
                _telemetryClient.TrackException(ex);
                return StatusCode(500, new { error = "Failed to retrieve entities", message = ex.Message });
            }
        }
        
        [HttpGet("health")]
        public async Task<IActionResult> HealthCheck()
        {
            try
            {
                var dbHealth = await _databaseService.IsHealthyAsync();
                var apiHealth = await _externalApiService.IsHealthyAsync();
                var jobStats = BackgroundJobService.GetJobStatistics();
                
                var response = new
                {
                    status = dbHealth && apiHealth ? "Healthy" : "Unhealthy",
                    database = dbHealth,
                    externalApi = apiHealth,
                    backgroundJobs = jobStats,
                    timestamp = DateTime.UtcNow
                };
                
                return Ok(response);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Health check failed");
                _telemetryClient.TrackException(ex);
                return StatusCode(500, new { status = "Unhealthy", error = ex.Message });
            }
        }
    }
}