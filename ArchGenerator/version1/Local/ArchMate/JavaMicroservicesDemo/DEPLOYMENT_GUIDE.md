# Java Microservices CI/CD Demo - Deployment Guide

## 🚀 Overview
This comprehensive guide will help you deploy the Java Microservices demo with complete CI/CD pipeline, security scanning, and Azure Kubernetes Service (AKS) deployment from your SfMC_Projects repository.

## ✅ Prerequisites
- Azure CLI installed and authenticated
- GitHub CLI (optional, for easier secret management)
- kubectl installed
- Java 21+ and Maven 3.9+ (for local testing)
- Docker (for local container testing)

## 🏗️ Infrastructure Setup

### Step 1: Create Azure Resources

```bash
# Set variables
RESOURCE_GROUP="sfmc-javademo-rg"
LOCATION="eastus"
AKS_CLUSTER_NAME="sfmc-javamicroservices-aks"
ACR_NAME="sfmcjavademo$(date +%s)"  # Unique name with timestamp

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --location $LOCATION

# Create AKS cluster with workload identity
az aks create \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_CLUSTER_NAME \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --enable-oidc-issuer \
  --enable-workload-identity \
  --attach-acr $ACR_NAME \
  --generate-ssh-keys \
  --location $LOCATION

# Get AKS credentials
az aks get-credentials --resource-group $RESOURCE_GROUP --name $AKS_CLUSTER_NAME
```

### Step 2: Create Azure Service Principal for GitHub Actions

```bash
# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

# Create service principal
az ad sp create-for-rbac \
  --name "sfmc-javamicroservices-github" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --json-auth

# Note: Save the JSON output for GitHub secrets
```

### Step 3: Configure GitHub Repository Secrets

Go to your GitHub repository: `https://github.com/ssamadda_microsoft/SfMC_Projects/settings/secrets/actions`

Add the following secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `AZURE_CLIENT_ID` | From service principal JSON | Client ID from step 2 |
| `AZURE_TENANT_ID` | From service principal JSON | Tenant ID from step 2 |
| `AZURE_SUBSCRIPTION_ID` | Your subscription ID | Azure subscription ID |
| `ACR_LOGIN_SERVER` | `$ACR_NAME.azurecr.io` | Container registry server |
| `AKS_RESOURCE_GROUP` | `sfmc-javademo-rg` | Resource group name |
| `AKS_CLUSTER_NAME` | `sfmc-javamicroservices-aks` | AKS cluster name |

## 🔧 CI/CD Pipeline Configuration

The pipeline includes:
- ✅ **Security Scanning**: CodeQL analysis, Dependabot alerts
- ✅ **Build & Test**: Maven builds with JUnit testing
- ✅ **Container Security**: Trivy vulnerability scanning
- ✅ **Blue-Green Deployment**: Zero-downtime AKS deployment
- ✅ **Advanced Features**: Matrix builds, artifact management, comprehensive reporting

### Workflow Triggers
- Push to `main` branch (only for JavaMicroservicesDemo folder changes)
- Pull requests to `main` branch (only for JavaMicroservicesDemo folder changes)

## 📋 Deployment Steps

### Option 1: Automatic Deployment (Recommended)
1. Push changes to the `main` branch in the JavaMicroservicesDemo folder
2. GitHub Actions will automatically:
   - Run security scans and tests
   - Build container images
   - Deploy to AKS cluster
   - Run smoke tests

### Option 2: Manual Deployment
```bash
# Navigate to the JavaMicroservicesDemo folder
cd JavaMicroservicesDemo

# Build the applications
mvn clean package

# Build and push container images
docker build -t $ACR_NAME.azurecr.io/user-service:latest ./user-service
docker build -t $ACR_NAME.azurecr.io/order-service:latest ./order-service

# Login to ACR and push
az acr login --name $ACR_NAME
docker push $ACR_NAME.azurecr.io/user-service:latest
docker push $ACR_NAME.azurecr.io/order-service:latest

# Update Kubernetes manifests
sed -i "s/PLACEHOLDER_ACR_SERVER/$ACR_NAME.azurecr.io/g" k8s/*.yaml
sed -i "s/PLACEHOLDER_IMAGE_TAG/latest/g" k8s/*.yaml

# Deploy to AKS
kubectl apply -f k8s/
```

## 🧪 Testing the Deployment

### Health Checks
```bash
# Get service URLs
kubectl get svc

# Test health endpoints
USER_SERVICE_IP=$(kubectl get svc user-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
ORDER_SERVICE_IP=$(kubectl get svc order-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

curl http://$USER_SERVICE_IP:8080/actuator/health
curl http://$ORDER_SERVICE_IP:8081/actuator/health
```

### API Testing
```bash
# Test User Service (Version 2.0 features)
curl http://$USER_SERVICE_IP:8080/api/users
curl http://$USER_SERVICE_IP:8080/api/users/department/Engineering
curl http://$USER_SERVICE_IP:8080/actuator/health/v2

# Test Order Service (Version 2.0 features)  
curl http://$ORDER_SERVICE_IP:8081/api/orders
curl http://$ORDER_SERVICE_IP:8081/api/orders/user/1
curl http://$ORDER_SERVICE_IP:8081/api/orders/summary
curl http://$ORDER_SERVICE_IP:8081/actuator/health/v2
```

## 🔍 Monitoring and Troubleshooting

### View Deployment Status
```bash
# Check pod status
kubectl get pods -o wide

# View pod logs
kubectl logs -l app=user-service
kubectl logs -l app=order-service

# Check service status
kubectl get svc
kubectl describe svc user-service order-service
```

### GitHub Actions Monitoring
- **Actions Tab**: https://github.com/ssamadda_microsoft/SfMC_Projects/actions
- **Security Tab**: https://github.com/ssamadda_microsoft/SfMC_Projects/security
- **Dependabot**: https://github.com/ssamadda_microsoft/SfMC_Projects/security/dependabot

## 📊 Features Demonstrated

### CI/CD Pipeline Features
- ✅ **Matrix Builds**: Parallel service builds
- ✅ **Security Integration**: CodeQL, OWASP dependency check, Trivy scanning
- ✅ **Test Reporting**: JUnit test results with detailed reporting
- ✅ **Artifact Management**: Build artifacts preservation and deployment
- ✅ **Blue-Green Deployment**: Zero-downtime rolling deployments

### Application Features (Version 2.0)
- ✅ **Sample Data**: Pre-loaded users and orders for testing
- ✅ **Enhanced APIs**: Department filtering, order summaries, user relationships
- ✅ **Health Checks**: Version 2.0 health endpoints with detailed status
- ✅ **Microservice Communication**: Order service calls User service
- ✅ **Spring Boot Features**: Actuator endpoints, JPA repositories, REST controllers

### Security Features
- ✅ **Dependabot**: Automatic dependency updates
- ✅ **CodeQL Analysis**: Static code analysis for security vulnerabilities
- ✅ **Container Scanning**: Trivy vulnerability assessment
- ✅ **Workload Identity**: Azure authentication without storing credentials

## 🚨 Common Issues and Solutions

### Pipeline Failures
- **Build Failures**: Check Maven dependencies and Java version compatibility
- **Container Push Failures**: Verify ACR authentication and permissions
- **Deployment Failures**: Check AKS cluster status and kubectl connectivity

### Service Access Issues
- **502/503 Errors**: Services may still be starting (wait 2-3 minutes)
- **Connection Timeouts**: Check if LoadBalancer services have external IPs assigned
- **DNS Issues**: Ensure proper service names and ports in manifests

## 🎯 Success Metrics

A successful deployment will show:
- ✅ All GitHub Actions workflows completing successfully
- ✅ Two running pods (user-service, order-service) in AKS
- ✅ LoadBalancer services with external IP addresses
- ✅ Health endpoints returning HTTP 200 status
- ✅ API endpoints returning sample data
- ✅ Security scans completed without critical vulnerabilities

## 📚 Additional Resources

- [Spring Boot Documentation](https://spring.io/projects/spring-boot)
- [Azure AKS Documentation](https://docs.microsoft.com/en-us/azure/aks/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Maven Documentation](https://maven.apache.org/guides/)

---

**Project**: Java Microservices CI/CD Demo  
**Repository**: https://github.com/ssamadda_microsoft/SfMC_Projects  
**Location**: JavaMicroservicesDemo/  
**Version**: 2.0 with enhanced features and comprehensive CI/CD