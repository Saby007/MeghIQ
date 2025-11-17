package com.example.monitoring.controller;

import com.example.monitoring.service.DatabaseService;
import com.example.monitoring.service.ExternalApiService;
import com.example.monitoring.service.BackgroundJobService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.CompletableFuture;

@RestController
@RequestMapping("/test")
public class TestController {
    
    private static final Logger logger = LoggerFactory.getLogger(TestController.class);
    private final Random random = new Random();
    
    @Autowired
    private DatabaseService databaseService;
    
    @Autowired
    private ExternalApiService externalApiService;
    
    @Autowired
    private BackgroundJobService backgroundJobService;
    
    @GetMapping("/latency")
    public ResponseEntity<Map<String, Object>> testLatency(@RequestParam(defaultValue = "2000") int delayMs) {
        logger.info("Testing latency with delay: {}ms", delayMs);
        
        long startTime = System.currentTimeMillis();
        
        try {
            // Simulate slow processing
            Thread.sleep(delayMs);
            
            long duration = System.currentTimeMillis() - startTime;
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Latency test completed");
            response.put("requestedDelayMs", delayMs);
            response.put("actualDurationMs", duration);
            response.put("timestamp", System.currentTimeMillis());
            
            logger.info("Latency test completed in {}ms", duration);
            return ResponseEntity.ok(response);
            
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            logger.error("Latency test interrupted", e);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "error");
            response.put("message", "Test was interrupted");
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(500).body(response);
        }
    }
    
    @GetMapping("/highcpu")
    public ResponseEntity<Map<String, Object>> testHighCpu(@RequestParam(defaultValue = "5000") int durationMs) {
        logger.info("Testing high CPU usage for duration: {}ms", durationMs);
        
        long startTime = System.currentTimeMillis();
        long endTime = startTime + durationMs;
        
        // Simulate high CPU usage
        CompletableFuture.runAsync(() -> {
            while (System.currentTimeMillis() < endTime) {
                // Busy work to consume CPU
                double result = 0;
                for (int i = 0; i < 10000; i++) {
                    result += Math.sqrt(i) * Math.sin(i) * Math.cos(i);
                }
            }
        });
        
        // Additional CPU work on main thread
        double result = 0;
        while (System.currentTimeMillis() < endTime) {
            for (int i = 0; i < 5000; i++) {
                result += Math.sqrt(i) * Math.sin(i);
            }
        }
        
        long actualDuration = System.currentTimeMillis() - startTime;
        
        Map<String, Object> response = new HashMap<>();
        response.put("status", "success");
        response.put("message", "High CPU test completed");
        response.put("requestedDurationMs", durationMs);
        response.put("actualDurationMs", actualDuration);
        response.put("computationResult", result);
        response.put("timestamp", System.currentTimeMillis());
        
        logger.info("High CPU test completed in {}ms", actualDuration);
        return ResponseEntity.ok(response);
    }
    
    @GetMapping("/exception")
    public ResponseEntity<Map<String, Object>> testException(@RequestParam(defaultValue = "runtime") String type) {
        logger.info("Testing exception of type: {}", type);
        
        try {
            switch (type.toLowerCase()) {
                case "runtime":
                    throw new RuntimeException("Simulated runtime exception for testing");
                case "null":
                    String nullString = null;
                    nullString.length(); // Will cause NullPointerException
                    break;
                case "array":
                    int[] array = new int[5];
                    int value = array[10]; // Will cause ArrayIndexOutOfBoundsException
                    break;
                case "arithmetic":
                    int result = 10 / 0; // Will cause ArithmeticException
                    break;
                case "illegal":
                    throw new IllegalArgumentException("Simulated illegal argument exception");
                default:
                    throw new UnsupportedOperationException("Unsupported exception type: " + type);
            }
        } catch (Exception e) {
            logger.error("Exception test triggered: {}", type, e);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "exception_triggered");
            response.put("message", "Exception successfully triggered for testing");
            response.put("exceptionType", e.getClass().getSimpleName());
            response.put("exceptionMessage", e.getMessage());
            response.put("requestedType", type);
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.status(500).body(response);
        }
        
        // This should never be reached
        Map<String, Object> response = new HashMap<>();
        response.put("status", "error");
        response.put("message", "Expected exception was not thrown");
        return ResponseEntity.status(500).body(response);
    }
    
    @GetMapping("/dependencyFail")
    public ResponseEntity<Map<String, Object>> testDependencyFailure(@RequestParam(defaultValue = "external") String service) {
        logger.info("Testing dependency failure for service: {}", service);
        
        long startTime = System.currentTimeMillis();
        
        try {
            switch (service.toLowerCase()) {
                case "external":
                case "api":
                    // Test external API failure
                    var result = externalApiService.simulateFailingExternalCall().block();
                    break;
                case "slow":
                    // Test slow external API
                    var slowResult = externalApiService.simulateSlowExternalCall().block();
                    break;
                default:
                    throw new IllegalArgumentException("Unknown service type: " + service);
            }
            
            long duration = System.currentTimeMillis() - startTime;
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "unexpected_success");
            response.put("message", "Dependency call succeeded when failure was expected");
            response.put("service", service);
            response.put("durationMs", duration);
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            long duration = System.currentTimeMillis() - startTime;
            logger.error("Dependency failure test completed: {}", service, e);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "dependency_failure");
            response.put("message", "Dependency failure successfully simulated");
            response.put("service", service);
            response.put("errorType", e.getClass().getSimpleName());
            response.put("errorMessage", e.getMessage());
            response.put("durationMs", duration);
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.status(503).body(response);
        }
    }
    
    @GetMapping("/dbError")
    public ResponseEntity<Map<String, Object>> testDatabaseError(@RequestParam(defaultValue = "error") String type) {
        logger.info("Testing database error of type: {}", type);
        
        long startTime = System.currentTimeMillis();
        
        try {
            switch (type.toLowerCase()) {
                case "error":
                    databaseService.simulateDatabaseError(5);
                    break;
                case "slow":
                    databaseService.simulateSlowQuery();
                    break;
                case "timeout":
                    // Simulate very slow query that might timeout
                    Thread.sleep(30000); // 30 seconds
                    databaseService.getAllEntities();
                    break;
                default:
                    throw new IllegalArgumentException("Unknown database test type: " + type);
            }
            
            long duration = System.currentTimeMillis() - startTime;
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "unexpected_success");
            response.put("message", "Database operation succeeded when error was expected");
            response.put("testType", type);
            response.put("durationMs", duration);
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            long duration = System.currentTimeMillis() - startTime;
            logger.error("Database error test completed: {}", type, e);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "database_error");
            response.put("message", "Database error successfully simulated");
            response.put("testType", type);
            response.put("errorType", e.getClass().getSimpleName());
            response.put("errorMessage", e.getMessage());
            response.put("durationMs", duration);
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.status(500).body(response);
        }
    }
    
    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getTestStats() {
        logger.info("Retrieving test statistics");
        
        Map<String, Object> response = new HashMap<>();
        response.put("backgroundJobs", Map.of(
            "totalJobs", backgroundJobService.getJobCount(),
            "successfulJobs", backgroundJobService.getSuccessCount(),
            "failedJobs", backgroundJobService.getErrorCount()
        ));
        
        try {
            response.put("database", Map.of(
                "entityCount", databaseService.getEntityCount(),
                "status", "connected"
            ));
        } catch (Exception e) {
            response.put("database", Map.of(
                "status", "error",
                "error", e.getMessage()
            ));
        }
        
        response.put("timestamp", System.currentTimeMillis());
        response.put("status", "success");
        
        return ResponseEntity.ok(response);
    }
    
    @GetMapping("/analytics")
    public ResponseEntity<Map<String, Object>> getLiveAnalytics() {
        logger.info("Retrieving live analytics data");
        
        Map<String, Object> response = new HashMap<>();
        Runtime runtime = Runtime.getRuntime();
        
        // Incoming Requests Metrics
        Map<String, Object> incomingRequests = new HashMap<>();
        incomingRequests.put("requestRate", generateMetricData(0.5, 8.0, "requests/sec"));
        incomingRequests.put("requestDuration", generateMetricData(50, 800, "ms"));
        incomingRequests.put("requestFailureRate", generateMetricData(0, 15, "percent"));
        response.put("incomingRequests", incomingRequests);
        
        // Outgoing Requests (Dependencies) Metrics
        Map<String, Object> outgoingRequests = new HashMap<>();
        outgoingRequests.put("dependencyCallRate", generateMetricData(0.2, 4.0, "calls/sec"));
        outgoingRequests.put("dependencyCallDuration", generateMetricData(100, 1200, "ms"));
        outgoingRequests.put("dependencyCallFailureRate", generateMetricData(0, 10, "percent"));
        response.put("outgoingRequests", outgoingRequests);
        
        // Overall Health Metrics
        Map<String, Object> overallHealth = new HashMap<>();
        
        // Memory metrics
        long totalMemory = runtime.totalMemory();
        long freeMemory = runtime.freeMemory();
        long usedMemory = totalMemory - freeMemory;
        long maxMemory = runtime.maxMemory();
        
        overallHealth.put("committedMemory", Map.of(
            "current", totalMemory / (1024 * 1024), // MB
            "max", maxMemory / (1024 * 1024), // MB
            "unit", "MB",
            "trend", generateTrendData(200, 400)
        ));
        
        overallHealth.put("cpuTotal", generateMetricData(5, 85, "percent"));
        overallHealth.put("exceptionRate", generateMetricData(0, 5, "exceptions/min"));
        
        // Background Jobs Analytics
        overallHealth.put("backgroundJobs", Map.of(
            "totalJobs", backgroundJobService.getJobCount(),
            "successRate", calculateSuccessRate(),
            "avgJobsPerMinute", generateMetricData(1, 3, "jobs/min")
        ));
        
        response.put("overallHealth", overallHealth);
        
        // Server Metrics
        Map<String, Object> serverMetrics = new HashMap<>();
        serverMetrics.put("activeThreads", Thread.activeCount());
        serverMetrics.put("availableProcessors", runtime.availableProcessors());
        serverMetrics.put("uptime", java.lang.management.ManagementFactory.getRuntimeMXBean().getUptime());
        
        try {
            serverMetrics.put("databaseConnections", Map.of(
                "active", databaseService.getEntityCount() > 0 ? 1 : 0,
                "status", "healthy"
            ));
        } catch (Exception e) {
            serverMetrics.put("databaseConnections", Map.of(
                "active", 0,
                "status", "error"
            ));
        }
        
        response.put("serverMetrics", serverMetrics);
        response.put("timestamp", System.currentTimeMillis());
        response.put("status", "success");
        
        return ResponseEntity.ok(response);
    }
    
    private Map<String, Object> generateMetricData(double min, double max, String unit) {
        Random random = new Random();
        double current = min + (max - min) * random.nextDouble();
        
        return Map.of(
            "current", Math.round(current * 100.0) / 100.0,
            "unit", unit,
            "trend", generateTrendData(min, max),
            "status", current > (max * 0.8) ? "warning" : "healthy"
        );
    }
    
    private java.util.List<Double> generateTrendData(double min, double max) {
        Random random = new Random();
        java.util.List<Double> trend = new java.util.ArrayList<>();
        double current = min + (max - min) * 0.5; // Start at middle
        
        for (int i = 0; i < 20; i++) {
            // Add some variation but keep within bounds
            double variation = (random.nextDouble() - 0.5) * (max - min) * 0.1;
            current += variation;
            current = Math.max(min, Math.min(max, current));
            trend.add(Math.round(current * 100.0) / 100.0);
        }
        
        return trend;
    }
    
    private double calculateSuccessRate() {
        long total = backgroundJobService.getJobCount();
        long successful = backgroundJobService.getSuccessCount();
        
        if (total == 0) return 100.0;
        return Math.round((successful * 100.0 / total) * 100.0) / 100.0;
    }
    
    @GetMapping("/entities")
    public ResponseEntity<Map<String, Object>> getAllEntities() {
        logger.info("Retrieving all database entities");
        
        Map<String, Object> response = new HashMap<>();
        
        try {
            var entities = databaseService.getAllEntities();
            response.put("entities", entities);
            response.put("count", entities.size());
            response.put("status", "success");
        } catch (Exception e) {
            logger.error("Error retrieving entities", e);
            response.put("status", "error");
            response.put("error", e.getMessage());
        }
        
        response.put("timestamp", System.currentTimeMillis());
        
        return ResponseEntity.ok(response);
    }
}