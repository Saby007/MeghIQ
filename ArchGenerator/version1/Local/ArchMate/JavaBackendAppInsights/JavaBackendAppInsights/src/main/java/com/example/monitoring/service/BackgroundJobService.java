package com.example.monitoring.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.Random;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class BackgroundJobService {
    
    private static final Logger logger = LoggerFactory.getLogger(BackgroundJobService.class);
    
    @Autowired
    private DatabaseService databaseService;
    
    @Autowired
    private ExternalApiService externalApiService;
    
    private final Random random = new Random();
    private final AtomicLong jobCounter = new AtomicLong(0);
    private final AtomicLong successCounter = new AtomicLong(0);
    private final AtomicLong errorCounter = new AtomicLong(0);
    
    @Scheduled(fixedRate = 30000) // Every 30 seconds
    public void performScheduledDataProcessing() {
        long jobId = jobCounter.incrementAndGet();
        logger.info("Starting scheduled data processing job #{}", jobId);
        
        try {
            // Simulate batch data processing
            simulateDataProcessing(jobId);
            successCounter.incrementAndGet();
            logger.info("Completed scheduled data processing job #{}", jobId);
        } catch (Exception e) {
            errorCounter.incrementAndGet();
            logger.error("Failed scheduled data processing job #{}", jobId, e);
        }
    }
    
    @Scheduled(fixedRate = 60000) // Every minute
    public void performScheduledDataSync() {
        long jobId = jobCounter.incrementAndGet();
        logger.info("Starting scheduled data sync job #{}", jobId);
        
        try {
            // Simulate external data synchronization
            simulateDataSync(jobId);
            successCounter.incrementAndGet();
            logger.info("Completed scheduled data sync job #{}", jobId);
        } catch (Exception e) {
            errorCounter.incrementAndGet();
            logger.error("Failed scheduled data sync job #{}", jobId, e);
        }
    }
    
    @Scheduled(fixedRate = 120000) // Every 2 minutes
    public void performScheduledHealthCheck() {
        long jobId = jobCounter.incrementAndGet();
        logger.info("Starting scheduled health check job #{}", jobId);
        
        try {
            // Simulate health checks
            simulateHealthCheck(jobId);
            successCounter.incrementAndGet();
            logger.info("Completed scheduled health check job #{}", jobId);
        } catch (Exception e) {
            errorCounter.incrementAndGet();
            logger.error("Failed scheduled health check job #{}", jobId, e);
        }
    }
    
    private void simulateDataProcessing(long jobId) throws Exception {
        logger.info("Processing batch data for job #{}", jobId);
        
        // Simulate processing time
        Thread.sleep(1000 + random.nextInt(2000));
        
        // Create some sample entities during processing
        if (random.nextInt(3) == 0) { // 33% chance to create entities
            String entityName = "ProcessedEntity-" + jobId + "-" + System.currentTimeMillis();
            databaseService.createEntity(entityName);
            logger.info("Job #{}: Created entity: {}", jobId, entityName);
        }
        
        // Simulate database operations
        long entityCount = databaseService.getEntityCount();
        logger.info("Job #{}: Found {} entities to process", jobId, entityCount);
        
        // Simulate some processing work
        for (int i = 0; i < 5; i++) {
            Thread.sleep(100 + random.nextInt(200));
            logger.debug("Job #{}: Processing batch {}/5", jobId, i + 1);
        }
        
        // Occasionally simulate errors
        if (random.nextInt(8) < 1) { // 12.5% chance of error
            throw new RuntimeException("Random processing error in job #" + jobId);
        }
        
        logger.info("Job #{}: Data processing completed successfully", jobId);
    }
    
    private void simulateDataSync(long jobId) throws Exception {
        logger.info("Synchronizing external data for job #{}", jobId);
        
        try {
            // Call external API
            var result = externalApiService.callExternalApi("get").block();
            logger.info("Job #{}: External API call successful", jobId);
            
            // Simulate database update - create sync entity occasionally
            if (random.nextInt(4) == 0) { // 25% chance to create sync entities
                String entityName = "SyncEntity-" + jobId + "-" + System.currentTimeMillis();
                databaseService.createEntity(entityName);
                logger.info("Job #{}: Created sync entity: {}", jobId, entityName);
            }
            
            Thread.sleep(500 + random.nextInt(1000));
            
            // Occasionally simulate sync errors
            if (random.nextInt(10) < 1) { // 10% chance of sync error
                throw new RuntimeException("Data synchronization failed for job #" + jobId);
            }
            
            logger.info("Job #{}: Data sync completed successfully", jobId);
        } catch (Exception e) {
            logger.error("Job #{}: Data sync failed", jobId, e);
            throw e;
        }
    }
    
    private void simulateHealthCheck(long jobId) throws Exception {
        logger.info("Performing health checks for job #{}", jobId);
        
        // Check database connectivity
        try {
            long count = databaseService.getEntityCount();
            logger.info("Job #{}: Database health check passed, {} entities", jobId, count);
        } catch (Exception e) {
            logger.error("Job #{}: Database health check failed", jobId, e);
            throw new RuntimeException("Database health check failed", e);
        }
        
        // Check external API connectivity
        try {
            var result = externalApiService.callExternalApi("status/200").block();
            logger.info("Job #{}: External API health check passed", jobId);
        } catch (Exception e) {
            logger.error("Job #{}: External API health check failed", jobId, e);
            // Don't fail the entire health check for external API issues
            logger.warn("Job #{}: Continuing with degraded external API", jobId);
        }
        
        // Occasionally fail health check to show failed job statistics
        if (random.nextInt(15) < 1) { // 6.7% chance of health check failure
            throw new RuntimeException("System health check failed - simulated failure for job #" + jobId);
        }
        
        logger.info("Job #{}: Health check completed", jobId);
    }
    
    public long getJobCount() {
        return jobCounter.get();
    }
    
    public long getSuccessCount() {
        return successCounter.get();
    }
    
    public long getErrorCount() {
        return errorCounter.get();
    }
}