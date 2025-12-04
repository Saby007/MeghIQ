using Microsoft.AspNetCore.Mvc;
using MonitoringDemo.Data;

namespace MonitoringDemo.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class DashboardController : ControllerBase
    {
        private readonly ApplicationDbContext _context;

        public DashboardController(ApplicationDbContext context)
        {
            _context = context;
        }

        [HttpGet]
        public IActionResult GetDashboard()
        {
            try
            {
                var html = GetSimpleDashboardHtml();
                Response.Headers["Cache-Control"] = "no-cache, no-store, must-revalidate";
                Response.Headers["Pragma"] = "no-cache";
                Response.Headers["Expires"] = "0";
                return Content(html, "text/html");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error generating dashboard: {ex.Message}");
            }
        }

        [HttpGet("clean")]
        public IActionResult GetCleanDashboard()
        {
            try
            {
                var html = GetSimpleDashboardHtml();
                Response.Headers["Cache-Control"] = "no-cache, no-store, must-revalidate";
                Response.Headers["Pragma"] = "no-cache";
                Response.Headers["Expires"] = "0";
                return Content(html, "text/html");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error generating clean dashboard: {ex.Message}");
            }
        }

        [HttpGet("stats")]
        public IActionResult GetStats()
        {
            try
            {
                var entityCount = _context.Entities.Count();
                var totalJobs = entityCount; // Using entity count as job count for demo
                var successfulJobs = (int)(entityCount * 0.85); // 85% success rate for demo
                var failedJobs = totalJobs - successfulJobs;
                var successRate = totalJobs > 0 ? Math.Round((double)successfulJobs / totalJobs * 100, 1) : 0;

                var stats = new
                {
                    totalJobs,
                    successfulJobs,
                    failedJobs,
                    successRate,
                    entityCount
                };

                return Ok(stats);
            }
            catch (Exception ex)
            {
                return StatusCode(500, new { error = ex.Message });
            }
        }

        private string GetSimpleDashboardHtml()
        {
            return @"<!DOCTYPE html>
<html>
<head>
    <meta charset=""UTF-8"">
    <title>Monitoring Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #e3f2fd; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; color: #1976d2; }
        .stat-label { color: #666; margin-top: 10px; }
        .btn { background: #1976d2; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #1565c0; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .response-area { margin-top: 10px; padding: 15px; background: #f5f5f5; border-radius: 4px; min-height: 50px; }
        .response-area.loading { background: #fff3cd; }
        .response-area.success { background: #d4edda; }
        .response-area.error { background: #f8d7da; }
        .response-area.warning { background: #ffeaa7; }
        .test-section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #fafafa; }
        .input-group { margin: 10px 0; }
        .input-group label { display: inline-block; width: 150px; font-weight: bold; }
        .input-group input, .input-group select { padding: 8px; border: 1px solid #ccc; border-radius: 4px; width: 200px; }
    </style>
</head>
<body>
    <div class='container'>
        <h1>Azure Monitoring Dashboard</h1>
        
        <div class='stats-section'>
            <h2>Statistics</h2>
            <button class='btn' onclick='refreshStats()'>Refresh Stats</button>
            <div class='stats-grid' id='stats-grid'>
                <div class='stat-card'>
                    <div class='stat-value' id='total-jobs'>-</div>
                    <div class='stat-label'>Total Jobs</div>
                </div>
                <div class='stat-card'>
                    <div class='stat-value' id='successful-jobs'>-</div>
                    <div class='stat-label'>Successful Jobs</div>
                </div>
                <div class='stat-card'>
                    <div class='stat-value' id='failed-jobs'>-</div>
                    <div class='stat-label'>Failed Jobs</div>
                </div>
                <div class='stat-card'>
                    <div class='stat-value' id='database-entities'>-</div>
                    <div class='stat-label'>Database Entities</div>
                </div>
            </div>
            <div class='response-area' id='stats-response'>Click Refresh Stats to load current statistics...</div>
        </div>
        
        <div class='test-section'>
            <h3>🚀 Latency Test</h3>
            <p>Test API response times with configurable delays.</p>
            <div class='input-group'>
                <label for='latency-delay'>Delay (ms):</label>
                <input type='number' id='latency-delay' value='1000' min='0' max='10000'>
                <button class='btn' id='latency-btn' onclick='testLatency()'>Test Latency</button>
            </div>
            <div class='response-area' id='latency-response'>Configure delay and click 'Test Latency' to start...</div>
        </div>
        
        <div class='test-section'>
            <h3>💻 CPU Load Test</h3>
            <p>Generate CPU load to test performance monitoring.</p>
            <div class='input-group'>
                <label for='cpu-duration'>Duration (ms):</label>
                <input type='number' id='cpu-duration' value='2000' min='500' max='30000'>
                <button class='btn' id='cpu-btn' onclick='testCpu()'>Generate CPU Load</button>
            </div>
            <div class='response-area' id='cpu-response'>Configure duration and click 'Generate CPU Load' to start...</div>
        </div>
        
        <div class='test-section'>
            <h3>💥 Exception Test</h3>
            <p>Generate different types of exceptions for error monitoring.</p>
            <div class='input-group'>
                <label for='exception-type'>Exception Type:</label>
                <select id='exception-type'>
                    <option value='runtime'>Runtime Exception</option>
                    <option value='argument'>Argument Exception</option>
                    <option value='nullref'>Null Reference</option>
                    <option value='timeout'>Timeout Exception</option>
                </select>
                <button class='btn' id='exception-btn' onclick='testException()'>Generate Exception</button>
            </div>
            <div class='response-area' id='exception-response'>Select exception type and click 'Generate Exception' to start...</div>
        </div>
        
        <div class='test-section'>
            <h3>🔗 Dependency Test</h3>
            <p>Test external service dependencies and connection monitoring.</p>
            <div class='input-group'>
                <label for='service-type'>Service Type:</label>
                <select id='service-type'>
                    <option value='httpbin'>HTTP Service (httpbin.org)</option>
                    <option value='sql'>SQL Database</option>
                    <option value='redis'>Redis Cache</option>
                    <option value='storage'>Azure Storage</option>
                </select>
                <button class='btn' id='dependency-btn' onclick='testDependency()'>Test Dependency</button>
            </div>
            <div class='response-area' id='dependency-response'>Select service and click 'Test Dependency' to start...</div>
        </div>
        
        <div class='test-section'>
            <h3>🗄️ Database Test</h3>
            <p>Test database operations and monitor database performance.</p>
            <div class='input-group'>
                <label for='db-operation'>Operation:</label>
                <select id='db-operation'>
                    <option value='read'>Read Operation</option>
                    <option value='write'>Write Operation</option>
                    <option value='bulk'>Bulk Insert</option>
                    <option value='query'>Complex Query</option>
                </select>
                <button class='btn' id='database-btn' onclick='testDatabase()'>Test Database</button>
            </div>
            <div class='response-area' id='database-response'>Select operation and click 'Test Database' to start...</div>
        </div>
        
        <div class='test-section'>
            <h3>🚀 Run All Tests</h3>
            <p>Execute all test scenarios in sequence to generate comprehensive telemetry data.</p>
            <button class='btn' id='all-tests-btn' onclick='runAllTests()' style='font-size: 16px; padding: 15px 30px;'>Run All Tests</button>
            <div class='response-area' id='all-tests-response'>Click 'Run All Tests' to execute the complete test suite...</div>
        </div>
    </div>

    <script>
        // Utility function to handle API calls
        async function callApi(endpoint, method = 'GET', body = null) {
            try {
                const options = {
                    method: method,
                    headers: { 'Content-Type': 'application/json' }
                };
                if (body) { options.body = JSON.stringify(body); }
                
                const response = await fetch(endpoint, options);
                const result = await response.text();
                
                return {
                    success: response.ok,
                    status: response.status,
                    data: result,
                    responseTime: new Date().toLocaleTimeString()
                };
            } catch (error) {
                return {
                    success: false,
                    status: 0,
                    data: 'Error: ' + error.message,
                    responseTime: new Date().toLocaleTimeString()
                };
            }
        }

        async function refreshStats() {
            const responseElement = document.getElementById('stats-response');
            responseElement.textContent = 'Loading statistics...';
            
            try {
                const response = await fetch('/api/dashboard/stats');
                const stats = await response.json();
                
                if (response.ok) {
                    document.getElementById('total-jobs').textContent = stats.totalJobs || 0;
                    document.getElementById('successful-jobs').textContent = stats.successfulJobs || 0;
                    document.getElementById('failed-jobs').textContent = stats.failedJobs || 0;
                    document.getElementById('database-entities').textContent = stats.entityCount || 0;
                    
                    responseElement.textContent = 'Statistics loaded successfully at ' + new Date().toLocaleTimeString();
                    responseElement.className = 'response-area success';
                } else {
                    responseElement.textContent = 'Error loading statistics: ' + (stats.error || 'Unknown error');
                    responseElement.className = 'response-area error';
                }
            } catch (error) {
                responseElement.textContent = 'Network error: ' + error.message;
                responseElement.className = 'response-area error';
            }
        }

        async function testLatency() {
            const button = document.getElementById('latency-btn');
            const responseElement = document.getElementById('latency-response');
            const delay = document.getElementById('latency-delay').value;
            
            button.disabled = true;
            button.textContent = 'Testing...';
            responseElement.textContent = 'Testing latency...';
            responseElement.className = 'response-area loading';
            
            const startTime = performance.now();
            const result = await callApi('/api/test/latency?delay=' + delay);
            const endTime = performance.now();
            const actualDelay = Math.round(endTime - startTime);
            
            if (result.success) {
                responseElement.textContent = '[SUCCESS] Latency test completed!\\nRequested delay: ' + delay + 'ms\\nActual response time: ' + actualDelay + 'ms\\nStatus: ' + result.status + '\\nResponse: ' + result.data;
                responseElement.className = 'response-area success';
            } else {
                responseElement.textContent = '[ERROR] Latency test failed!\\nError: ' + result.data + '\\nResponse time: ' + actualDelay + 'ms';
                responseElement.className = 'response-area error';
            }
            
            button.disabled = false;
            button.textContent = 'Test Latency';
        }

        async function testCpu() {
            const button = document.getElementById('cpu-btn');
            const responseElement = document.getElementById('cpu-response');
            const intensity = Math.max(1, Math.min(10, Math.round(document.getElementById('cpu-duration').value / 1000)));
            
            button.disabled = true;
            button.textContent = 'Processing...';
            responseElement.textContent = 'Generating CPU load...';
            responseElement.className = 'response-area loading';
            
            const startTime = performance.now();
            const result = await callApi('/api/test/cpu?intensity=' + intensity);
            const endTime = performance.now();
            const actualTime = Math.round(endTime - startTime);
            
            if (result.success) {
                responseElement.textContent = '[CPU] CPU load test completed!\\nIntensity level: ' + intensity + '\\nActual processing time: ' + actualTime + 'ms\\nStatus: ' + result.status + '\\nResponse: ' + result.data;
                responseElement.className = 'response-area success';
            } else {
                responseElement.textContent = '[ERROR] CPU load test failed!\\nError: ' + result.data + '\\nProcessing time: ' + actualTime + 'ms';
                responseElement.className = 'response-area error';
            }
            
            button.disabled = false;
            button.textContent = 'Generate CPU Load';
        }

        async function testException() {
            const button = document.getElementById('exception-btn');
            const responseElement = document.getElementById('exception-response');
            const exceptionType = document.getElementById('exception-type').value;
            
            button.disabled = true;
            button.textContent = 'Generating...';
            responseElement.textContent = 'Generating exception...';
            responseElement.className = 'response-area loading';
            
            const result = await callApi('/api/test/exception?type=' + exceptionType);
            
            if (result.success) {
                responseElement.textContent = '[WARNING] Unexpected success!\\nException type: ' + exceptionType + '\\nResponse: ' + result.data;
                responseElement.className = 'response-area warning';
            } else {
                responseElement.textContent = '[EXCEPTION] Exception generated successfully!\\nType: ' + exceptionType + '\\nStatus: ' + result.status + '\\nError: ' + result.data;
                responseElement.className = 'response-area success';
            }
            
            button.disabled = false;
            button.textContent = 'Generate Exception';
        }

        async function testDependency() {
            const button = document.getElementById('dependency-btn');
            const responseElement = document.getElementById('dependency-response');
            const serviceType = document.getElementById('service-type').value;
            
            button.disabled = true;
            button.textContent = 'Testing...';
            responseElement.textContent = 'Testing dependency...';
            responseElement.className = 'response-area loading';
            
            const result = await callApi('/api/test/dependency?endpoint=' + serviceType);
            
            if (result.success) {
                responseElement.textContent = '[API] Dependency test completed!\\nEndpoint: ' + serviceType + '\\nStatus: ' + result.status + '\\nResponse: ' + result.data;
                responseElement.className = 'response-area success';
            } else {
                responseElement.textContent = '[ERROR] Dependency test failed!\\nEndpoint: ' + serviceType + '\\nError: ' + result.data;
                responseElement.className = 'response-area error';
            }
            
            button.disabled = false;
            button.textContent = 'Test Dependency';
        }

        async function testDatabase() {
            const button = document.getElementById('database-btn');
            const responseElement = document.getElementById('database-response');
            const operation = document.getElementById('db-operation').value;
            
            button.disabled = true;
            button.textContent = 'Testing...';
            responseElement.textContent = 'Testing database operation...';
            responseElement.className = 'response-area loading';
            
            const result = await callApi('/api/test/database?operation=' + operation);
            
            if (result.success) {
                responseElement.textContent = '[DATABASE] Database test completed!\\nOperation: ' + operation + '\\nStatus: ' + result.status + '\\nResponse: ' + result.data;
                responseElement.className = 'response-area success';
            } else {
                responseElement.textContent = '[ERROR] Database test failed!\\nOperation: ' + operation + '\\nError: ' + result.data;
                responseElement.className = 'response-area error';
            }
            
            button.disabled = false;
            button.textContent = 'Test Database';
        }

        async function runAllTests() {
            const button = document.getElementById('all-tests-btn');
            const responseElement = document.getElementById('all-tests-response');
            
            button.disabled = true;
            button.textContent = 'Running All Tests...';
            responseElement.textContent = 'Starting comprehensive test suite...\\n';
            responseElement.className = 'response-area loading';
            
            const tests = [
                { name: 'Latency Test', endpoint: '/api/test/latency?delay=1000' },
                { name: 'CPU Load Test', endpoint: '/api/test/cpu?intensity=3' },
                { name: 'Exception Test', endpoint: '/api/test/exception?type=runtime' },
                { name: 'Dependency Test', endpoint: '/api/test/dependency?endpoint=get' },
                { name: 'Database Test', endpoint: '/api/test/database?operation=write' }
            ];
            
            let results = [];
            for (const test of tests) {
                responseElement.textContent += '\\n[RUNNING] ' + test.name + '...';
                const result = await callApi(test.endpoint);
                const status = result.success ? '[PASSED]' : '[FAILED]';
                results.push(status + ' ' + test.name + ': ' + result.status + ' - ' + result.data.substring(0, 50) + '...');
                responseElement.textContent += ' ' + status;
            }
            
            responseElement.textContent = results.join('\\n') + '\\n\\n[COMPLETE] All tests finished!';
            responseElement.className = 'response-area success';
            
            button.disabled = false;
            button.textContent = 'Run All Tests';
            
            // Refresh stats after all tests
            setTimeout(refreshStats, 1000);
        }
        
        // Auto-refresh stats every 30 seconds
        setInterval(refreshStats, 30000);
        
        // Load stats on page load
        window.onload = function() {
            refreshStats();
        };
    </script>
</body>
</html>";
        }
    }
}