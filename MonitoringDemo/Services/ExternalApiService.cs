using System.Diagnostics;
using System.Text.Json;

namespace MonitoringDemo.Services
{
    public interface IExternalApiService
    {
        Task<string> CallExternalApiAsync(string endpoint);
        Task<bool> IsHealthyAsync();
    }
    
    public class ExternalApiService : IExternalApiService
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<ExternalApiService> _logger;
        private const string BaseUrl = "https://httpbin.org";
        
        public ExternalApiService(HttpClient httpClient, ILogger<ExternalApiService> logger)
        {
            _httpClient = httpClient;
            _logger = logger;
        }
        
        public async Task<string> CallExternalApiAsync(string endpoint)
        {
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                var url = $"{BaseUrl}/{endpoint}";
                _logger.LogInformation("Calling external API: {Url}", url);
                
                var response = await _httpClient.GetAsync(url);
                stopwatch.Stop();
                
                if (response.IsSuccessStatusCode)
                {
                    var content = await response.Content.ReadAsStringAsync();
                    _logger.LogInformation("External API call successful: {Url} in {ElapsedMs}ms", 
                        url, stopwatch.ElapsedMilliseconds);
                    return content;
                }
                else
                {
                    _logger.LogWarning("External API call failed: {Url} - Status: {StatusCode}", 
                        url, response.StatusCode);
                    throw new HttpRequestException($"API call failed with status: {response.StatusCode}");
                }
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "External API call failed: {Endpoint} after {ElapsedMs}ms", 
                    endpoint, stopwatch.ElapsedMilliseconds);
                throw;
            }
        }
        
        public async Task<bool> IsHealthyAsync()
        {
            try
            {
                await CallExternalApiAsync("status/200");
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "External API health check failed");
                return false;
            }
        }
    }
}