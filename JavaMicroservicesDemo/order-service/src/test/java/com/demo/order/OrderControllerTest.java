package com.demo.order;

import com.demo.order.controller.OrderController;
import com.demo.order.model.Order;
import com.demo.order.service.OrderService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.MockitoAnnotations;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(OrderController.class)
public class OrderControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private OrderService orderService;

    @Autowired
    private ObjectMapper objectMapper;

    private Order testOrder;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        testOrder = new Order(1L, "Laptop", 1, new BigDecimal("999.99"), "PENDING");
        testOrder.setId(1L);
    }

    @Test
    void getAllOrders_ReturnsListOfOrders() throws Exception {
        when(orderService.getAllOrders()).thenReturn(Arrays.asList(testOrder));

        mockMvc.perform(get("/api/orders"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].productName").value("Laptop"))
                .andExpect(jsonPath("$[0].status").value("PENDING"));
    }

    @Test
    void getOrderById_ExistingOrder_ReturnsOrder() throws Exception {
        when(orderService.getOrderById(1L)).thenReturn(Optional.of(testOrder));

        mockMvc.perform(get("/api/orders/1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.productName").value("Laptop"))
                .andExpect(jsonPath("$.status").value("PENDING"));
    }

    @Test
    @SuppressWarnings("null")
    void createOrder_ValidOrder_ReturnsCreatedOrder() throws Exception {
        when(orderService.createOrder(any(Order.class))).thenReturn(testOrder);

        String orderJson = objectMapper.writeValueAsString(testOrder);
        
        mockMvc.perform(post("/api/orders")
                .contentType(MediaType.APPLICATION_JSON)
                .content(orderJson))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.productName").value("Laptop"));
    }

    @Test
    void health_ReturnsHealthyStatus() throws Exception {
        mockMvc.perform(get("/api/orders/health"))
                .andExpect(status().isOk())
                .andExpect(content().string("Order Service is running! Version 2.0 - CI/CD Demo"));
    }
}