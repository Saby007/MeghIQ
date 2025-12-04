package com.example.monitoring;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Counter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.HashMap;
import java.util.Random;

@SpringBootApplication
@RestController
public class MonitoringDemoApplication {

    private static final Logger logger = LoggerFactory.getLogger(MonitoringDemoApplication.class);
    private final Counter requestCounter;
    private final Random random = new Random();

    public MonitoringDemoApplication(MeterRegistry meterRegistry) {
        this.requestCounter = Counter.builder("api.requests.total")
                .description("Total number of API requests")
                .register(meterRegistry);
    }

    public static void main(String[] args) {
        logger.info("Starting Monitoring Demo Application with Spring Boot 3.5.7 and Java 21");
        SpringApplication.run(MonitoringDemoApplication.class, args);
    }

    @GetMapping("/")
    public Map<String, Object> home() {
        requestCounter.increment();
        
        logger.info("Home endpoint accessed");
        
        Map<String, Object> response = new HashMap<>();
        response.put("message", "Welcome to Azure Monitoring Demo with Spring Boot 3.5.7 and Java 21!");
        response.put("timestamp", LocalDateTime.now());
        response.put("status", "healthy");
        response.put("java_version", System.getProperty("java.version"));
        response.put("spring_boot_version", "3.5.7");
        
        return response;
    }

    @GetMapping("/api/users/{id}")
    public Map<String, Object> getUser(@PathVariable String id) {
        requestCounter.increment();
        
        logger.info("Getting user with ID: {}", id);
        
        try {
            // Simulate some processing time
            Thread.sleep(random.nextInt(100, 500));
            
            Map<String, Object> user = new HashMap<>();
            user.put("id", id);
            user.put("name", "User " + id);
            user.put("email", "user" + id + "@example.com");
            user.put("timestamp", LocalDateTime.now());
            
            logger.info("Successfully retrieved user: {}", id);
            return user;
            
        } catch (InterruptedException e) {
            logger.error("Error processing user request for ID: {}", id, e);
            Thread.currentThread().interrupt();
            throw new RuntimeException("Processing interrupted", e);
        }
    }

    @GetMapping("/api/data")
    public Map<String, Object> getData(@RequestParam(defaultValue = "10") int count) {
        requestCounter.increment();
        
        logger.info("Generating {} data items", count);
        
        try {
            // Simulate database query time based on count
            Thread.sleep(count * 10L);
            
            Map<String, Object> response = new HashMap<>();
            response.put("count", count);
            response.put("data", generateSampleData(count));
            response.put("timestamp", LocalDateTime.now());
            
            logger.info("Successfully generated {} data items", count);
            return response;
            
        } catch (InterruptedException e) {
            logger.error("Error generating data", e);
            Thread.currentThread().interrupt();
            throw new RuntimeException("Data generation interrupted", e);
        }
    }

    @GetMapping("/api/error")
    public Map<String, Object> simulateError(@RequestParam(defaultValue = "false") boolean throwError) {
        requestCounter.increment();
        logger.warn("Error endpoint accessed with throwError={}", throwError);
        
        if (throwError) {
            logger.error("Simulating application error");
            throw new RuntimeException("This is a simulated error for monitoring purposes");
        }
        
        Map<String, Object> response = new HashMap<>();
        response.put("message", "Error simulation disabled");
        response.put("timestamp", LocalDateTime.now());
        
        return response;
    }

    @GetMapping("/api/slow")
    public Map<String, Object> slowEndpoint(@RequestParam(defaultValue = "2000") int delay) {
        requestCounter.increment();
        
        logger.info("Slow endpoint called with {}ms delay", delay);
        
        try {
            Thread.sleep(delay);
            
            Map<String, Object> response = new HashMap<>();
            response.put("message", "Slow operation completed");
            response.put("delay_ms", delay);
            response.put("timestamp", LocalDateTime.now());
            
            logger.info("Slow endpoint completed after {}ms", delay);
            return response;
            
        } catch (InterruptedException e) {
            logger.error("Slow endpoint interrupted", e);
            Thread.currentThread().interrupt();
            throw new RuntimeException("Slow operation interrupted", e);
        }
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> health = new HashMap<>();
        health.put("status", "UP");
        health.put("timestamp", LocalDateTime.now());
        health.put("uptime", System.currentTimeMillis());
        
        return health;
    }

    private Object[] generateSampleData(int count) {
        Object[] data = new Object[count];
        for (int i = 0; i < count; i++) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", i + 1);
            item.put("value", random.nextDouble() * 100);
            item.put("category", "Category " + (char) ('A' + (i % 5)));
            data[i] = item;
        }
        return data;
    }
}