package com.example.monitoring;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@SpringBootApplication
@EnableScheduling
public class MonitoringDemoApplication {

    private static final Logger logger = LoggerFactory.getLogger(MonitoringDemoApplication.class);

    public static void main(String[] args) {
        logger.info("Starting Monitoring Demo Application with Spring Boot 3.5.7 and Java 21");
        SpringApplication.run(MonitoringDemoApplication.class, args);
    }
}