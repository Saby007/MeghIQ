package com.demo.order.config;

import com.demo.order.model.Order;
import com.demo.order.repository.OrderRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

@Component
public class OrderDataInitializer implements CommandLineRunner {

    @Autowired
    private OrderRepository orderRepository;

    @Override
    public void run(String... args) throws Exception {
        // Initialize with sample data for CI/CD demo
        if (orderRepository.count() == 0) {
            orderRepository.save(new Order(1L, "Laptop", 1, new BigDecimal("999.99"), "COMPLETED"));
            orderRepository.save(new Order(2L, "Mouse", 2, new BigDecimal("25.50"), "PENDING"));
            orderRepository.save(new Order(1L, "Keyboard", 1, new BigDecimal("75.00"), "PROCESSING"));
            orderRepository.save(new Order(3L, "Monitor", 1, new BigDecimal("299.99"), "COMPLETED"));
            orderRepository.save(new Order(2L, "Headphones", 1, new BigDecimal("150.00"), "PENDING"));
            orderRepository.save(new Order(4L, "Webcam", 1, new BigDecimal("89.99"), "PROCESSING"));
            
            System.out.println("Sample order data initialized for CI/CD demo!");
        }
    }
}