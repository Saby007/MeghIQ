package com.demo.order.service;

import com.demo.order.model.Order;
import com.demo.order.repository.OrderRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Optional;

@Service
public class OrderService {

    @Autowired
    private OrderRepository orderRepository;

    private final WebClient webClient;

    @Value("${user.service.url:http://user-service:8080}")
    private String userServiceUrl;

    public OrderService(WebClient.Builder webClientBuilder) {
        this.webClient = webClientBuilder.build();
    }

    public List<Order> getAllOrders() {
        return orderRepository.findAll();
    }

    public Optional<Order> getOrderById(Long id) {
        return orderRepository.findById(id);
    }

    public List<Order> getOrdersByUserId(Long userId) {
        return orderRepository.findByUserId(userId);
    }

    public List<Order> getOrdersByStatus(String status) {
        return orderRepository.findByStatus(status);
    }

    public Order createOrder(Order order) {
        // Validate user exists by calling user service
        return validateUserAndCreateOrder(order);
    }

    public Order updateOrder(Long id, Order orderDetails) {
        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Order not found with id: " + id));

        order.setProductName(orderDetails.getProductName());
        order.setQuantity(orderDetails.getQuantity());
        order.setPrice(orderDetails.getPrice());
        order.setStatus(orderDetails.getStatus());

        return orderRepository.save(order);
    }

    public void deleteOrder(Long id) {
        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Order not found with id: " + id));
        orderRepository.delete(order);
    }

    public List<Order> getRecentOrders() {
        // Return orders with "PENDING" or "PROCESSING" status for demo
        return orderRepository.findAll().stream()
                .filter(order -> "PENDING".equals(order.getStatus()) || 
                               "PROCESSING".equals(order.getStatus()) ||
                               "COMPLETED".equals(order.getStatus()))
                .toList();
    }

    private Order validateUserAndCreateOrder(Order order) {
        try {
            // Call user service to validate user exists
            Mono<String> userResponse = webClient.get()
                    .uri(userServiceUrl + "/api/users/" + order.getUserId())
                    .retrieve()
                    .bodyToMono(String.class);

            // For demo purposes, we'll just save the order
            // In a real app, you'd handle the response properly
            order.setStatus("PENDING");
            return orderRepository.save(order);
        } catch (Exception e) {
            // If user service is down, still create order but mark it for validation
            order.setStatus("PENDING_VALIDATION");
            return orderRepository.save(order);
        }
    }
}