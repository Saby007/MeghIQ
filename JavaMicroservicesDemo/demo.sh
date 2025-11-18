#!/bin/bash

# Java Microservices Demo Script
# This script demonstrates the API functionality of both services

set -e

USER_SERVICE_URL="http://localhost:8080"
ORDER_SERVICE_URL="http://localhost:8081"

echo "🚀 Java Microservices API Demo"
echo "================================"

# Check if services are running
echo "🔍 Checking service health..."

if ! curl -f "$USER_SERVICE_URL/actuator/health" > /dev/null 2>&1; then
    echo "❌ User Service is not running at $USER_SERVICE_URL"
    echo "   Please start it with: cd user-service && mvn spring-boot:run"
    exit 1
fi

if ! curl -f "$ORDER_SERVICE_URL/actuator/health" > /dev/null 2>&1; then
    echo "❌ Order Service is not running at $ORDER_SERVICE_URL"
    echo "   Please start it with: cd order-service && mvn spring-boot:run"
    exit 1
fi

echo "✅ Both services are running!"
echo ""

# User Service Demo
echo "👤 USER SERVICE DEMO"
echo "===================="

echo "1️⃣ Creating users..."
USER1_RESPONSE=$(curl -s -X POST "$USER_SERVICE_URL/api/users" \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice Johnson","email":"alice@example.com","department":"Engineering"}')
echo "Created user: $USER1_RESPONSE"

USER2_RESPONSE=$(curl -s -X POST "$USER_SERVICE_URL/api/users" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bob Smith","email":"bob@example.com","department":"Sales"}')
echo "Created user: $USER2_RESPONSE"

USER3_RESPONSE=$(curl -s -X POST "$USER_SERVICE_URL/api/users" \
  -H "Content-Type: application/json" \
  -d '{"name":"Carol Davis","email":"carol@example.com","department":"Marketing"}')
echo "Created user: $USER3_RESPONSE"

echo ""

echo "2️⃣ Listing all users..."
ALL_USERS=$(curl -s "$USER_SERVICE_URL/api/users")
echo "All users: $ALL_USERS"
echo ""

echo "3️⃣ Getting user by ID..."
USER_BY_ID=$(curl -s "$USER_SERVICE_URL/api/users/1")
echo "User #1: $USER_BY_ID"
echo ""

echo "4️⃣ Getting user by email..."
USER_BY_EMAIL=$(curl -s "$USER_SERVICE_URL/api/users/email/alice@example.com")
echo "User by email: $USER_BY_EMAIL"
echo ""

# Order Service Demo
echo "📦 ORDER SERVICE DEMO"
echo "===================="

echo "1️⃣ Creating orders..."
ORDER1_RESPONSE=$(curl -s -X POST "$ORDER_SERVICE_URL/api/orders" \
  -H "Content-Type: application/json" \
  -d '{"userId":1,"productName":"MacBook Pro","quantity":1,"price":2499.99}')
echo "Created order: $ORDER1_RESPONSE"

ORDER2_RESPONSE=$(curl -s -X POST "$ORDER_SERVICE_URL/api/orders" \
  -H "Content-Type: application/json" \
  -d '{"userId":2,"productName":"Office Chair","quantity":2,"price":299.99}')
echo "Created order: $ORDER2_RESPONSE"

ORDER3_RESPONSE=$(curl -s -X POST "$ORDER_SERVICE_URL/api/orders" \
  -H "Content-Type: application/json" \
  -d '{"userId":1,"productName":"Wireless Mouse","quantity":3,"price":79.99}')
echo "Created order: $ORDER3_RESPONSE"

echo ""

echo "2️⃣ Listing all orders..."
ALL_ORDERS=$(curl -s "$ORDER_SERVICE_URL/api/orders")
echo "All orders: $ALL_ORDERS"
echo ""

echo "3️⃣ Getting orders by user ID..."
ORDERS_BY_USER=$(curl -s "$ORDER_SERVICE_URL/api/orders/user/1")
echo "Orders for User #1: $ORDERS_BY_USER"
echo ""

echo "4️⃣ Getting orders by status..."
ORDERS_BY_STATUS=$(curl -s "$ORDER_SERVICE_URL/api/orders/status/PENDING")
echo "Pending orders: $ORDERS_BY_STATUS"
echo ""

# Health Checks
echo "🏥 HEALTH CHECKS"
echo "================"

echo "User Service Health:"
curl -s "$USER_SERVICE_URL/actuator/health" | python -m json.tool 2>/dev/null || echo "Health check response received"
echo ""

echo "Order Service Health:"
curl -s "$ORDER_SERVICE_URL/actuator/health" | python -m json.tool 2>/dev/null || echo "Health check response received"
echo ""

echo "Order Service Custom Health:"
curl -s "$ORDER_SERVICE_URL/api/orders/health"
echo ""

# Security Demo (Intentional vulnerabilities)
echo "🔒 SECURITY DEMO (Intentional Vulnerabilities)"
echo "============================================="

echo "1️⃣ CORS vulnerability - Cross-origin requests allowed"
echo "   This allows requests from any origin (security risk)"
echo ""

echo "2️⃣ H2 Console enabled in production"
echo "   Access database console at: $USER_SERVICE_URL/h2-console"
echo "   JDBC URL: jdbc:h2:mem:userdb, User: sa, Password: password"
echo ""

echo "3️⃣ Vulnerable dependency: commons-text 1.9"
echo "   This version has known security vulnerabilities"
echo "   Dependabot should create PR to update it"
echo ""

echo "✅ Demo completed successfully!"
echo ""
echo "🔍 Next Steps:"
echo "   1. Check GitHub Actions for CI/CD pipeline"
echo "   2. Review Dependabot alerts for security updates"
echo "   3. Examine CodeQL results for code quality"
echo "   4. Deploy to AKS cluster for production demo"