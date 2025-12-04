# Java Microservices Demo Script (PowerShell)
# This script demonstrates the API functionality of both services

param(
    [string]$UserServiceUrl = "http://localhost:8080",
    [string]$OrderServiceUrl = "http://localhost:8081"
)

Write-Host "🚀 Java Microservices API Demo" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check if services are running
Write-Host "🔍 Checking service health..." -ForegroundColor Yellow

try {
    $userHealth = Invoke-RestMethod -Uri "$UserServiceUrl/actuator/health" -Method Get -TimeoutSec 5
    Write-Host "✅ User Service is running!" -ForegroundColor Green
} catch {
    Write-Host "❌ User Service is not running at $UserServiceUrl" -ForegroundColor Red
    Write-Host "   Please start it with: cd user-service && mvn spring-boot:run" -ForegroundColor Yellow
    exit 1
}

try {
    $orderHealth = Invoke-RestMethod -Uri "$OrderServiceUrl/actuator/health" -Method Get -TimeoutSec 5
    Write-Host "✅ Order Service is running!" -ForegroundColor Green
} catch {
    Write-Host "❌ Order Service is not running at $OrderServiceUrl" -ForegroundColor Red
    Write-Host "   Please start it with: cd order-service && mvn spring-boot:run" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# User Service Demo
Write-Host "👤 USER SERVICE DEMO" -ForegroundColor Magenta
Write-Host "====================" -ForegroundColor Magenta

Write-Host "1️⃣ Creating users..." -ForegroundColor Yellow

$user1 = @{
    name = "Alice Johnson"
    email = "alice@example.com"
    department = "Engineering"
} | ConvertTo-Json

$user1Response = Invoke-RestMethod -Uri "$UserServiceUrl/api/users" -Method Post -Body $user1 -ContentType "application/json"
Write-Host "Created user: $($user1Response | ConvertTo-Json -Compress)" -ForegroundColor Green

$user2 = @{
    name = "Bob Smith"
    email = "bob@example.com"
    department = "Sales"
} | ConvertTo-Json

$user2Response = Invoke-RestMethod -Uri "$UserServiceUrl/api/users" -Method Post -Body $user2 -ContentType "application/json"
Write-Host "Created user: $($user2Response | ConvertTo-Json -Compress)" -ForegroundColor Green

$user3 = @{
    name = "Carol Davis"
    email = "carol@example.com"
    department = "Marketing"
} | ConvertTo-Json

$user3Response = Invoke-RestMethod -Uri "$UserServiceUrl/api/users" -Method Post -Body $user3 -ContentType "application/json"
Write-Host "Created user: $($user3Response | ConvertTo-Json -Compress)" -ForegroundColor Green

Write-Host ""

Write-Host "2️⃣ Listing all users..." -ForegroundColor Yellow
$allUsers = Invoke-RestMethod -Uri "$UserServiceUrl/api/users" -Method Get
Write-Host "All users: $($allUsers | ConvertTo-Json -Compress)" -ForegroundColor Green

Write-Host ""

Write-Host "3️⃣ Getting user by ID..." -ForegroundColor Yellow
$userById = Invoke-RestMethod -Uri "$UserServiceUrl/api/users/1" -Method Get
Write-Host "User #1: $($userById | ConvertTo-Json -Compress)" -ForegroundColor Green

Write-Host ""

# Order Service Demo
Write-Host "📦 ORDER SERVICE DEMO" -ForegroundColor Magenta
Write-Host "====================" -ForegroundColor Magenta

Write-Host "1️⃣ Creating orders..." -ForegroundColor Yellow

$order1 = @{
    userId = 1
    productName = "MacBook Pro"
    quantity = 1
    price = 2499.99
} | ConvertTo-Json

$order1Response = Invoke-RestMethod -Uri "$OrderServiceUrl/api/orders" -Method Post -Body $order1 -ContentType "application/json"
Write-Host "Created order: $($order1Response | ConvertTo-Json -Compress)" -ForegroundColor Green

$order2 = @{
    userId = 2
    productName = "Office Chair"
    quantity = 2
    price = 299.99
} | ConvertTo-Json

$order2Response = Invoke-RestMethod -Uri "$OrderServiceUrl/api/orders" -Method Post -Body $order2 -ContentType "application/json"
Write-Host "Created order: $($order2Response | ConvertTo-Json -Compress)" -ForegroundColor Green

$order3 = @{
    userId = 1
    productName = "Wireless Mouse"
    quantity = 3
    price = 79.99
} | ConvertTo-Json

$order3Response = Invoke-RestMethod -Uri "$OrderServiceUrl/api/orders" -Method Post -Body $order3 -ContentType "application/json"
Write-Host "Created order: $($order3Response | ConvertTo-Json -Compress)" -ForegroundColor Green

Write-Host ""

Write-Host "2️⃣ Listing all orders..." -ForegroundColor Yellow
$allOrders = Invoke-RestMethod -Uri "$OrderServiceUrl/api/orders" -Method Get
Write-Host "All orders: $($allOrders | ConvertTo-Json -Compress)" -ForegroundColor Green

Write-Host ""

Write-Host "3️⃣ Getting orders by user ID..." -ForegroundColor Yellow
$ordersByUser = Invoke-RestMethod -Uri "$OrderServiceUrl/api/orders/user/1" -Method Get
Write-Host "Orders for User #1: $($ordersByUser | ConvertTo-Json -Compress)" -ForegroundColor Green

Write-Host ""

# Health Checks
Write-Host "🏥 HEALTH CHECKS" -ForegroundColor Magenta
Write-Host "================" -ForegroundColor Magenta

Write-Host "User Service Health:" -ForegroundColor Yellow
$userServiceHealth = Invoke-RestMethod -Uri "$UserServiceUrl/actuator/health" -Method Get
Write-Host ($userServiceHealth | ConvertTo-Json -Depth 3) -ForegroundColor Green

Write-Host ""

Write-Host "Order Service Health:" -ForegroundColor Yellow
$orderServiceHealth = Invoke-RestMethod -Uri "$OrderServiceUrl/actuator/health" -Method Get
Write-Host ($orderServiceHealth | ConvertTo-Json -Depth 3) -ForegroundColor Green

Write-Host ""

Write-Host "Order Service Custom Health:" -ForegroundColor Yellow
$customHealth = Invoke-RestMethod -Uri "$OrderServiceUrl/api/orders/health" -Method Get
Write-Host $customHealth -ForegroundColor Green

Write-Host ""

# Security Demo
Write-Host "🔒 SECURITY DEMO (Intentional Vulnerabilities)" -ForegroundColor Red
Write-Host "=============================================" -ForegroundColor Red

Write-Host "1️⃣ CORS vulnerability - Cross-origin requests allowed" -ForegroundColor Yellow
Write-Host "   This allows requests from any origin (security risk)" -ForegroundColor Gray

Write-Host ""

Write-Host "2️⃣ H2 Console enabled in production" -ForegroundColor Yellow
Write-Host "   Access database console at: $UserServiceUrl/h2-console" -ForegroundColor Gray
Write-Host "   JDBC URL: jdbc:h2:mem:userdb, User: sa, Password: password" -ForegroundColor Gray

Write-Host ""

Write-Host "3️⃣ Vulnerable dependency: commons-text 1.9" -ForegroundColor Yellow
Write-Host "   This version has known security vulnerabilities" -ForegroundColor Gray
Write-Host "   Dependabot should create PR to update it" -ForegroundColor Gray

Write-Host ""

Write-Host "✅ Demo completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "🔍 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Check GitHub Actions for CI/CD pipeline" -ForegroundColor White
Write-Host "   2. Review Dependabot alerts for security updates" -ForegroundColor White
Write-Host "   3. Examine CodeQL results for code quality" -ForegroundColor White
Write-Host "   4. Deploy to AKS cluster for production demo" -ForegroundColor White