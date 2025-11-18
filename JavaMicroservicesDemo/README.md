# Java Microservices AKS Demo

[![CI/CD Pipeline](https://github.com/Saby007/java-microservices-aks-demo/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Saby007/java-microservices-aks-demo/actions/workflows/ci-cd.yml)
[![Security Scanning](https://github.com/Saby007/java-microservices-aks-demo/actions/workflows/security.yml/badge.svg)](https://github.com/Saby007/java-microservices-aks-demo/actions/workflows/security.yml)

A comprehensive demonstration of Java microservices with GitHub Actions CI/CD, advanced security scanning, and blue-green deployment to Azure Kubernetes Service (AKS).

## 🏗️ **Architecture Overview**

This project demonstrates:
- **Two Spring Boot microservices** (User Service & Order Service)
- **GitHub Actions CI/CD** with Maven build and Docker containerization
- **Advanced Security Features** (Dependabot, CodeQL, Container Scanning)
- **Blue-Green Deployment** to AKS cluster
- **Infrastructure as Code** with Azure CLI
- **Monitoring & Health checks** with Spring Boot Actuator

```
┌─────────────────┐    ┌─────────────────┐
│   User Service  │    │  Order Service  │
│    (Port 8080)  │◄───┤   (Port 8081)   │
└─────────────────┘    └─────────────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌─────────────────────────┐
         │     AKS Cluster         │
         │  (Blue-Green Deploy)    │
         └─────────────────────────┘
```

## 🚀 **Services**

### **User Service** (`user-service/`)
- **Port**: 8080
- **Database**: H2 (in-memory)
- **Features**: CRUD operations for user management
- **Endpoints**:
  - `GET /api/users` - List all users
  - `GET /api/users/{id}` - Get user by ID
  - `POST /api/users` - Create new user
  - `PUT /api/users/{id}` - Update user
  - `DELETE /api/users/{id}` - Delete user

### **Order Service** (`order-service/`)
- **Port**: 8081
- **Database**: H2 (in-memory)
- **Features**: Order management with user service integration
- **Endpoints**:
  - `GET /api/orders` - List all orders
  - `GET /api/orders/{id}` - Get order by ID
  - `GET /api/orders/user/{userId}` - Get orders by user
  - `POST /api/orders` - Create new order

## 🔒 **Security Features**

### **Dependabot**
- Automatically scans for vulnerable dependencies
- Creates PRs for security updates
- Configured for Maven ecosystem

### **CodeQL Analysis**
- Static code analysis for security vulnerabilities
- Scans for common security issues (SQL injection, XSS, etc.)
- Runs on every push and PR

### **Container Scanning**
- Scans Docker images for vulnerabilities
- Uses Trivy scanner in GitHub Actions
- Fails builds on critical vulnerabilities

### **Intentional Vulnerabilities** (for demo)
- Older version of `commons-text` library
- CORS enabled for all origins
- H2 console enabled in production

## ⚙️ **Prerequisites**

### **Local Development**
- Java 21+
- Maven 3.6+
- Docker Desktop

### **Azure Infrastructure**
- Azure subscription
- Resource Group: `githubactions-rg`
- AKS Cluster: `javamicroservices-aks`
- ACR: `javamicroservicesdemo.azurecr.io`
- Managed Identity configured for GitHub Actions

### **GitHub Secrets**
```bash
AZURE_CLIENT_ID=26d86939-b905-4472-83de-edbe662a1a74
AZURE_TENANT_ID=16b3c013-d300-468d-ac64-7eda0820b6d3
AZURE_SUBSCRIPTION_ID=616dc9b8-b4aa-415f-8dcb-71bc462916c5
ACR_LOGIN_SERVER=javamicroservicesdemo.azurecr.io
AKS_CLUSTER_NAME=javamicroservices-aks
AKS_RESOURCE_GROUP=githubactions-rg
```

## 🏃‍♂️ **Quick Start**

### **Local Development**
```bash
# Clone repository
git clone https://github.com/Saby007/java-microservices-aks-demo.git
cd java-microservices-aks-demo

# Build all services
mvn clean package

# Run User Service
cd user-service
mvn spring-boot:run

# Run Order Service (in new terminal)
cd order-service
mvn spring-boot:run
```

### **Docker**
```bash
# Build images
docker build -t user-service ./user-service
docker build -t order-service ./order-service

# Run with Docker Compose (if available)
docker-compose up
```

### **Test APIs**
```bash
# Create a user
curl -X POST http://localhost:8080/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","email":"john@example.com","department":"Engineering"}'

# Create an order
curl -X POST http://localhost:8081/api/orders \
  -H "Content-Type: application/json" \
  -d '{"userId":1,"productName":"Laptop","quantity":1,"price":999.99}'

# Get all users
curl http://localhost:8080/api/users

# Get all orders
curl http://localhost:8081/api/orders
```

## 🔄 **CI/CD Pipeline**

### **Workflow Triggers**
- **Push to main**: Full build, test, security scan, and deploy
- **Pull Request**: Build, test, and security scan (no deploy)
- **Schedule**: Nightly security scans

### **Pipeline Steps**
1. **Build & Test** - Maven compile and unit tests
2. **Security Scan** - CodeQL analysis and dependency check
3. **Docker Build** - Multi-stage container builds
4. **Container Scan** - Trivy vulnerability scanning
5. **Azure Login** - Workload Identity Federation (no secrets!)
6. **Deploy to AKS** - Blue-green deployment strategy
7. **Health Check** - Verify deployment success

### **Blue-Green Deployment**
- **Blue**: Current production environment
- **Green**: New version deployment
- **Switch**: Traffic routing after health checks pass
- **Rollback**: Automatic on deployment failure

## 📊 **Monitoring**

### **Health Endpoints**
- User Service: `http://localhost:8080/actuator/health`
- Order Service: `http://localhost:8081/actuator/health`

### **Metrics**
- Prometheus metrics available at `/actuator/prometheus`
- Application metrics and JVM statistics
- Custom business metrics

## 🛠️ **Development**

### **Adding New Features**
1. Create feature branch
2. Implement changes
3. Add tests
4. Create pull request
5. Security scans run automatically
6. Merge triggers deployment

### **Running Tests**
```bash
# Unit tests
mvn test

# Integration tests
mvn verify

# Security tests
mvn dependency-check:check
```

### **Local Kubernetes Testing**
```bash
# Apply manifests
kubectl apply -f k8s/

# Port forward
kubectl port-forward service/user-service 8080:8080
kubectl port-forward service/order-service 8081:8081
```

## 🔧 **Configuration**

### **Environment Variables**
- `USER_SERVICE_URL`: URL for user service (default: http://user-service:8080)
- `SPRING_PROFILES_ACTIVE`: Active Spring profiles
- `JAVA_TOOL_OPTIONS`: JVM options for containers

### **Kubernetes ConfigMaps**
- Application properties
- Environment-specific configurations
- Feature flags

## 🚨 **Security Considerations**

### **Production Recommendations**
- ✅ Remove H2 console access
- ✅ Configure proper CORS policies
- ✅ Update vulnerable dependencies
- ✅ Implement authentication/authorization
- ✅ Enable HTTPS/TLS
- ✅ Network policies in Kubernetes

### **Monitoring Security**
- Dependabot alerts in GitHub
- CodeQL security alerts
- Container vulnerability reports
- Azure Security Center integration

## 📈 **Scaling**

### **Horizontal Scaling**
```bash
# Scale deployments
kubectl scale deployment user-service --replicas=3
kubectl scale deployment order-service --replicas=3
```

### **Auto-scaling**
- Horizontal Pod Autoscaler (HPA) configured
- CPU and memory-based scaling
- Custom metrics scaling support

## 🤝 **Contributing**

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- Spring Boot team for excellent framework
- GitHub Actions for powerful CI/CD
- Azure team for AKS and security features
- Open source community for tools and libraries

---

**🎯 Demo Highlights:**
- ✅ Complete microservices architecture
- ✅ Production-ready CI/CD pipeline  
- ✅ Advanced security scanning
- ✅ Blue-green deployment strategy
- ✅ Infrastructure as Code
- ✅ Comprehensive monitoring
- ✅ Intentional vulnerabilities for demo purposes