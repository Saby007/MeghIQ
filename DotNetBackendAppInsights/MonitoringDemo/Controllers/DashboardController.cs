using Microsoft.AspNetCore.Mvc;
using Microsoft.ApplicationInsights;
using MonitoringDemo.Services;
using System.Text.Json;

namespace MonitoringDemo.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class DashboardController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;
        private readonly IExternalApiService _externalApiService;
        private readonly TelemetryClient _telemetryClient;
        private readonly ILogger<DashboardController> _logger;
        private static readonly Random _random = new();
        
        public DashboardController(
            IDatabaseService databaseService,
            IExternalApiService externalApiService,
            TelemetryClient telemetryClient,
            ILogger<DashboardController> logger)
        {
            _databaseService = databaseService;
            _externalApiService = externalApiService;
            _telemetryClient = telemetryClient;
            _logger = logger;
        }
        
        [HttpGet("")]
        public async Task<IActionResult> Dashboard()
        {
            var content = await GetDashboardHtml();
            return new ContentResult
            {
                Content = content,
                ContentType = "text/html"
            };
        }
        
        [HttpGet("stats")]
        public async Task<IActionResult> GetStats()
        {
            try
            {
                var jobStats = BackgroundJobService.GetJobStatistics();
                var entityCount = await _databaseService.GetEntityCountAsync();
                var dbHealth = await _databaseService.IsHealthyAsync();
                
                // Generate realistic metrics
                var now = DateTime.UtcNow;
                var stats = new
                {
                    timestamp = now,
                    serverMetrics = new
                    {
                        requests = new
                        {
                            total = _random.Next(850, 1200),
                            successful = _random.Next(780, 1100),
                            failed = _random.Next(15, 45),
                            avgDuration = Math.Round(_random.NextDouble() * 150 + 50, 1)
                        },
                        dependencies = new
                        {
                            calls = _random.Next(250, 400),
                            avgDuration = Math.Round(_random.NextDouble() * 200 + 100, 1),
                            failures = _random.Next(5, 20)
                        },
                        exceptions = new
                        {
                            count = _random.Next(2, 12),
                            types = new[] { "TimeoutException", "NullReferenceException", "InvalidOperationException" }
                        }
                    },
                    performance = new
                    {
                        cpu = Math.Round(_random.NextDouble() * 30 + 15, 1),
                        memory = Math.Round(_random.NextDouble() * 40 + 30, 1),
                        disk = Math.Round(_random.NextDouble() * 25 + 10, 1)
                    },
                    backgroundJobs = jobStats,
                    database = new
                    {
                        healthy = dbHealth,
                        entities = entityCount,
                        connections = _random.Next(8, 15),
                        avgResponseTime = Math.Round(_random.NextDouble() * 50 + 10, 1)
                    },
                    users = new
                    {
                        active = _random.Next(45, 85),
                        sessions = _random.Next(120, 200),
                        newUsers = _random.Next(5, 15)
                    }
                };
                
                return Ok(stats);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to retrieve dashboard statistics");
                return StatusCode(500, new { error = "Failed to retrieve statistics", message = ex.Message });
            }
        }
        
        [HttpGet("metrics/realtime")]
        public IActionResult GetRealtimeMetrics()
        {
            try
            {
                var metrics = new
                {
                    timestamp = DateTime.UtcNow,
                    requestsPerSecond = Math.Round(_random.NextDouble() * 15 + 5, 1),
                    responseTime = Math.Round(_random.NextDouble() * 100 + 50, 1),
                    errorRate = Math.Round(_random.NextDouble() * 5 + 1, 2),
                    throughput = Math.Round(_random.NextDouble() * 1000 + 500, 0),
                    activeConnections = _random.Next(20, 50),
                    memoryUsage = Math.Round(_random.NextDouble() * 30 + 40, 1),
                    cpuUsage = Math.Round(_random.NextDouble() * 25 + 20, 1)
                };
                
                return Ok(metrics);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to retrieve real-time metrics");
                return StatusCode(500, new { error = "Failed to retrieve metrics", message = ex.Message });
            }
        }
        
        private async Task<string> GetDashboardHtml()
        {
            try
            {
                var htmlPath = Path.Combine(Directory.GetCurrentDirectory(), "Views", "dashboard.html");
                return await System.IO.File.ReadAllTextAsync(htmlPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to load dashboard HTML file");
                return "<html><body><h1>Dashboard temporarily unavailable</h1></body></html>";
            }
        }
    }
}