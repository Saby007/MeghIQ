package com.example.monitoring;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.context.TestPropertySource;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@TestPropertySource(properties = {
    "azure.application-insights.enabled=false"
})
class MonitoringDemoApplicationTests {

    @LocalServerPort
    private int port;

    private TestRestTemplate restTemplate = new TestRestTemplate();

    @Test
    void contextLoads() {
        // Test that the Spring context loads successfully
    }

    @Test
    void homeEndpointReturnsExpectedResponse() {
        var response = restTemplate.getForObject(
            "http://localhost:" + port + "/", 
            String.class
        );
        assertThat(response).contains("Welcome to Azure Monitoring Demo");
    }

    @Test
    void healthEndpointReturnsUp() {
        var response = restTemplate.getForObject(
            "http://localhost:" + port + "/health", 
            String.class
        );
        assertThat(response).contains("UP");
    }

    @Test
    void userEndpointReturnsUserData() {
        var response = restTemplate.getForObject(
            "http://localhost:" + port + "/api/users/123", 
            String.class
        );
        assertThat(response).contains("User 123");
    }
}