package com.example.monitoring.service;

import com.example.monitoring.model.DemoEntity;
import com.example.monitoring.repository.DemoEntityRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.Random;

@Service
@Transactional
public class DatabaseService {
    
    private static final Logger logger = LoggerFactory.getLogger(DatabaseService.class);
    
    @Autowired
    private DemoEntityRepository demoRepository;
    
    private final Random random = new Random();
    
    public List<DemoEntity> getAllEntities() {
        logger.info("Fetching all entities from database");
        try {
            List<DemoEntity> entities = demoRepository.findAll();
            logger.info("Successfully retrieved {} entities", entities.size());
            return entities;
        } catch (Exception e) {
            logger.error("Error fetching entities", e);
            throw new RuntimeException("Database error while fetching entities", e);
        }
    }
    
    public Optional<DemoEntity> getEntityById(Integer id) {
        logger.info("Fetching entity with ID: {}", id);
        try {
            Optional<DemoEntity> entity = demoRepository.findById(id);
            if (entity.isPresent()) {
                logger.info("Successfully retrieved entity: {}", entity.get());
            } else {
                logger.warn("Entity not found with ID: {}", id);
            }
            return entity;
        } catch (Exception e) {
            logger.error("Error fetching entity with ID: {}", id, e);
            throw new RuntimeException("Database error while fetching entity", e);
        }
    }
    
    public DemoEntity createEntity(String name) {
        logger.info("Creating new entity with name: {}", name);
        try {
            DemoEntity entity = new DemoEntity(name);
            DemoEntity saved = demoRepository.save(entity);
            logger.info("Successfully created entity: {}", saved);
            return saved;
        } catch (Exception e) {
            logger.error("Error creating entity with name: {}", name, e);
            throw new RuntimeException("Database error while creating entity", e);
        }
    }
    
    public List<DemoEntity> searchEntities(String searchTerm) {
        logger.info("Searching entities with term: {}", searchTerm);
        try {
            List<DemoEntity> entities = demoRepository.findByNameContainingIgnoreCase(searchTerm);
            logger.info("Search returned {} entities", entities.size());
            return entities;
        } catch (Exception e) {
            logger.error("Error searching entities with term: {}", searchTerm, e);
            throw new RuntimeException("Database error while searching entities", e);
        }
    }
    
    public void simulateSlowQuery() {
        logger.info("Simulating slow database query");
        try {
            // Simulate a complex query that takes time
            Thread.sleep(1000 + random.nextInt(2000)); // 1-3 seconds
            List<DemoEntity> entities = demoRepository.findAll();
            logger.info("Slow query completed, retrieved {} entities", entities.size());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            logger.error("Slow query interrupted", e);
            throw new RuntimeException("Query interrupted", e);
        } catch (Exception e) {
            logger.error("Error in slow query", e);
            throw new RuntimeException("Database error in slow query", e);
        }
    }
    
    public void simulateDatabaseError(Integer id) {
        logger.info("Simulating database error for ID: {}", id);
        try {
            // This will cause a SQL error due to division by zero in the query
            DemoEntity entity = demoRepository.findWithError(id);
            logger.warn("Database error simulation did not fail as expected");
        } catch (Exception e) {
            logger.error("Database error simulated successfully", e);
            throw new RuntimeException("Simulated database error", e);
        }
    }
    
    public long getEntityCount() {
        try {
            long count = demoRepository.count();
            logger.info("Total entities count: {}", count);
            return count;
        } catch (Exception e) {
            logger.error("Error getting entity count", e);
            throw new RuntimeException("Database error while counting entities", e);
        }
    }
}