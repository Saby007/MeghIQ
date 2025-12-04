using Microsoft.ApplicationInsights;
using Microsoft.ApplicationInsights.DataContracts;
using MonitoringDemo.Services;

namespace MonitoringDemo.Services
{
    public class BackgroundJobService : BackgroundService
    {
        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<BackgroundJobService> _logger;
        private readonly TelemetryClient _telemetryClient;
        private readonly Random _random;
        
        // Job statistics
        public static volatile int TotalJobs = 0;
        public static volatile int SuccessfulJobs = 0;
        public static volatile int FailedJobs = 0;
        public static long ProcessedEntities = 0;
        public static long SyncedEntities = 0;
        
        public BackgroundJobService(
            IServiceScopeFactory scopeFactory,
            ILogger<BackgroundJobService> logger,
            TelemetryClient telemetryClient)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
            _telemetryClient = telemetryClient;
            _random = new Random();
        }
        
        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("Background Job Service started");
            
            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    // Run different types of jobs concurrently
                    var tasks = new[]
                    {
                        ProcessDataAsync(),
                        SyncEntitiesAsync(),
                        ProcessBatchJobAsync(),
                        CleanupJobAsync()
                    };
                    
                    await Task.WhenAll(tasks);
                    
                    // Wait before next cycle
                    await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in background job execution");
                }
            }
        }
        
        private async Task ProcessDataAsync()
        {
            var jobId = Guid.NewGuid().ToString();
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            
            try
            {
                Interlocked.Increment(ref TotalJobs);
                
                using var scope = _scopeFactory.CreateScope();
                var databaseService = scope.ServiceProvider.GetRequiredService<IDatabaseService>();
                
                _logger.LogInformation("Starting data processing job {JobId}", jobId);
                
                // Simulate processing with realistic failure rate (8.3%)
                if (_random.NextDouble() < 0.083)
                {
                    throw new InvalidOperationException("Simulated data processing failure");
                }
                
                // Create some entities during processing
                var entityCount = _random.Next(1, 4);
                for (int i = 0; i < entityCount; i++)
                {
                    await databaseService.CreateEntityAsync($"ProcessedEntity-{DateTime.Now:HHmmss}-{i}");
                    Interlocked.Increment(ref ProcessedEntities);
                }
                
                // Simulate processing time
                await Task.Delay(_random.Next(500, 2000));
                
                stopwatch.Stop();
                Interlocked.Increment(ref SuccessfulJobs);
                
                _telemetryClient.TrackDependency("DataProcessing", "ProcessData", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, true);
                
                _logger.LogInformation("Data processing job {JobId} completed successfully in {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                Interlocked.Increment(ref FailedJobs);
                
                _telemetryClient.TrackDependency("DataProcessing", "ProcessData", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, false);
                
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "JobId", jobId },
                    { "JobType", "DataProcessing" }
                });
                
                _logger.LogError(ex, "Data processing job {JobId} failed after {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
        }
        
        private async Task SyncEntitiesAsync()
        {
            var jobId = Guid.NewGuid().ToString();
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            
            try
            {
                Interlocked.Increment(ref TotalJobs);
                
                using var scope = _scopeFactory.CreateScope();
                var databaseService = scope.ServiceProvider.GetRequiredService<IDatabaseService>();
                
                _logger.LogInformation("Starting entity sync job {JobId}", jobId);
                
                // Simulate sync with realistic failure rate (12.5%)
                if (_random.NextDouble() < 0.125)
                {
                    throw new TimeoutException("Simulated sync timeout");
                }
                
                // Create sync entities
                var syncCount = _random.Next(1, 3);
                for (int i = 0; i < syncCount; i++)
                {
                    await databaseService.CreateEntityAsync($"SyncEntity-{DateTime.Now:HHmmss}-{i}");
                    Interlocked.Increment(ref SyncedEntities);
                }
                
                // Simulate sync time
                await Task.Delay(_random.Next(800, 1500));
                
                stopwatch.Stop();
                Interlocked.Increment(ref SuccessfulJobs);
                
                _telemetryClient.TrackDependency("EntitySync", "SyncEntities", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, true);
                
                _logger.LogInformation("Entity sync job {JobId} completed successfully in {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                Interlocked.Increment(ref FailedJobs);
                
                _telemetryClient.TrackDependency("EntitySync", "SyncEntities", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, false);
                
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "JobId", jobId },
                    { "JobType", "EntitySync" }
                });
                
                _logger.LogError(ex, "Entity sync job {JobId} failed after {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
        }
        
        private async Task ProcessBatchJobAsync()
        {
            var jobId = Guid.NewGuid().ToString();
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            
            try
            {
                Interlocked.Increment(ref TotalJobs);
                
                _logger.LogInformation("Starting batch job {JobId}", jobId);
                
                // Simulate batch processing with failure rate (6.7%)
                if (_random.NextDouble() < 0.067)
                {
                    throw new OutOfMemoryException("Simulated batch processing memory issue");
                }
                
                // Simulate batch processing time
                await Task.Delay(_random.Next(1000, 3000));
                
                stopwatch.Stop();
                Interlocked.Increment(ref SuccessfulJobs);
                
                _telemetryClient.TrackDependency("BatchProcessing", "ProcessBatch", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, true);
                
                _logger.LogInformation("Batch job {JobId} completed successfully in {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                Interlocked.Increment(ref FailedJobs);
                
                _telemetryClient.TrackDependency("BatchProcessing", "ProcessBatch", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, false);
                
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "JobId", jobId },
                    { "JobType", "BatchProcessing" }
                });
                
                _logger.LogError(ex, "Batch job {JobId} failed after {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
        }
        
        private async Task CleanupJobAsync()
        {
            var jobId = Guid.NewGuid().ToString();
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            
            try
            {
                Interlocked.Increment(ref TotalJobs);
                
                _logger.LogInformation("Starting cleanup job {JobId}", jobId);
                
                // Simulate cleanup with low failure rate (4.2%)
                if (_random.NextDouble() < 0.042)
                {
                    throw new UnauthorizedAccessException("Simulated cleanup access denied");
                }
                
                // Simulate cleanup time
                await Task.Delay(_random.Next(300, 800));
                
                stopwatch.Stop();
                Interlocked.Increment(ref SuccessfulJobs);
                
                _telemetryClient.TrackDependency("Cleanup", "CleanupEntities", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, true);
                
                _logger.LogInformation("Cleanup job {JobId} completed successfully in {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                Interlocked.Increment(ref FailedJobs);
                
                _telemetryClient.TrackDependency("Cleanup", "CleanupData", 
                    jobId, DateTime.UtcNow.Subtract(stopwatch.Elapsed), stopwatch.Elapsed, false);
                
                _telemetryClient.TrackException(ex, new Dictionary<string, string>
                {
                    { "JobId", jobId },
                    { "JobType", "Cleanup" }
                });
                
                _logger.LogError(ex, "Cleanup job {JobId} failed after {ElapsedMs}ms", 
                    jobId, stopwatch.ElapsedMilliseconds);
            }
        }
        
        public static object GetJobStatistics()
        {
            return new
            {
                totalJobs = TotalJobs,
                successfulJobs = SuccessfulJobs,
                failedJobs = FailedJobs,
                successRate = TotalJobs > 0 ? (double)SuccessfulJobs / TotalJobs * 100 : 0,
                processedEntities = ProcessedEntities,
                syncedEntities = SyncedEntities
            };
        }
    }
}