package com.example.monitoring.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;
import java.util.Random;

@Service
@SuppressWarnings("unchecked")
public class ExternalApiService {
    
    private static final Logger logger = LoggerFactory.getLogger(ExternalApiService.class);
    
    private final WebClient webClient;
    private final Random random = new Random();
    
    @Value("${app.external-api.base-url:https://httpbin.org}")
    private String baseUrl;
    
    @Value("${app.external-api.timeout:5000}")
    private int timeout;
    
    public ExternalApiService(WebClient.Builder webClientBuilder) {
        this.webClient = webClientBuilder
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(1024 * 1024))
                .build();
    }
    
    public Mono<Map<String, Object>> callExternalApi(String endpoint) {
        logger.info("Calling external API: {}/{}", baseUrl, endpoint);
        
        return webClient.get()
                .uri(baseUrl + "/" + endpoint)
                .retrieve()
                .bodyToMono(Map.class)
                .cast(Map.class)
                .map(rawMap -> (Map<String, Object>) rawMap)
                .timeout(Duration.ofMillis(timeout))
                .doOnSuccess(response -> logger.info("External API call successful: {}", endpoint))
                .doOnError(error -> logger.error("External API call failed: {}", endpoint, error))
                .onErrorResume(WebClientRequestException.class, ex -> {
                    logger.error("Network error calling external API: {}", ex.getMessage());
                    return Mono.error(new RuntimeException("External service unavailable", ex));
                });
    }
    
    public Mono<Map<String, Object>> simulateSlowExternalCall() {
        logger.info("Simulating slow external API call");
        int delay = 2000 + random.nextInt(3000); // 2-5 seconds delay
        
        return webClient.get()
                .uri(baseUrl + "/delay/" + (delay / 1000))
                .retrieve()
                .bodyToMono(Map.class)
                .cast(Map.class)
                .map(rawMap -> (Map<String, Object>) rawMap)
                .timeout(Duration.ofMillis(timeout + delay))
                .doOnSuccess(response -> logger.info("Slow external API call completed after {}ms", delay))
                .doOnError(error -> logger.error("Slow external API call failed", error));
    }
    
    public Mono<Map<String, Object>> simulateFailingExternalCall() {
        logger.info("Simulating failing external API call");
        
        return webClient.get()
                .uri(baseUrl + "/status/500")
                .retrieve()
                .bodyToMono(Map.class)
                .cast(Map.class)
                .map(rawMap -> (Map<String, Object>) rawMap)
                .doOnError(error -> logger.error("External API returned error as expected", error))
                .onErrorReturn(Map.of("error", "Simulated external API failure", "status", 500));
    }
}