package com.example.monitoring.config;

import com.microsoft.applicationinsights.TelemetryClient;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ApplicationInsightsConfig {

    @Bean
    @ConditionalOnProperty(name = "applicationinsights.connection.string")
    public TelemetryClient telemetryClient() {
        // With Spring Boot 3.x and newer Application Insights starter,
        // TelemetryClient is auto-configured based on application properties
        return new TelemetryClient();
    }
}