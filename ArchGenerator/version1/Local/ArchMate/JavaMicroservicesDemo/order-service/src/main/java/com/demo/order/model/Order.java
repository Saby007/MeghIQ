package com.demo.order.model;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "orders")
public class Order {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private Long userId;
    
    @Column(nullable = false)
    private String productName;
    
    @Column(nullable = false)
    private Integer quantity;
    
    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal price;
    
    @Column(nullable = false)
    private String status;
    
    @Column(nullable = false)
    private LocalDateTime createdAt;

    // Default constructor
    public Order() {}

    // Constructor
    public Order(Long userId, String productName, Integer quantity, BigDecimal price, String status) {
        this.userId = userId;
        this.productName = productName;
        this.quantity = quantity;
        this.price = price;
        this.status = status;
        this.createdAt = LocalDateTime.now();
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public String getProductName() { return productName; }
    public void setProductName(String productName) { this.productName = productName; }

    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity; }

    public BigDecimal getPrice() { return price; }
    public void setPrice(BigDecimal price) { this.price = price; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }

    @Override
    public String toString() {
        return "Order{" +
                "id=" + id +
                ", userId=" + userId +
                ", productName='" + productName + '\'' +
                ", quantity=" + quantity +
                ", price=" + price +
                ", status='" + status + '\'' +
                ", createdAt=" + createdAt +
                '}';
    }
}