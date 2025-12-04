#!/bin/bash

# SfMC Java Microservices Demo - Quick Deployment Script
# This script sets up Azure infrastructure and configures GitHub secrets

set -e  # Exit on any error

echo "🚀 SfMC Java Microservices Demo - Quick Deployment Setup"
echo "======================================================"

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v az >/dev/null 2>&1 || { echo "❌ Azure CLI is required but not installed. Aborting." >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl is required but not installed. Aborting." >&2; exit 1; }

# Check if logged in to Azure
az account show >/dev/null 2>&1 || { echo "❌ Please login to Azure CLI first: az login"; exit 1; }

echo "✅ Prerequisites check passed!"

# Set variables (you can modify these)
RESOURCE_GROUP="sfmc-javademo-rg"
LOCATION="eastus"
AKS_CLUSTER_NAME="sfmc-javamicroservices-aks"
ACR_NAME="sfmcjavademo$(date +%s)"
SP_NAME="sfmc-javamicroservices-github"

echo ""
echo "🏗️ Creating Azure Resources..."
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "AKS Cluster: $AKS_CLUSTER_NAME"
echo "Container Registry: $ACR_NAME"

# Create resource group
echo ""
echo "📦 Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output table

# Create Azure Container Registry
echo ""
echo "🐳 Creating Azure Container Registry..."
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --location "$LOCATION" \
  --output table

# Create AKS cluster
echo ""
echo "⚙️ Creating AKS cluster (this may take 5-10 minutes)..."
az aks create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AKS_CLUSTER_NAME" \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --enable-oidc-issuer \
  --enable-workload-identity \
  --attach-acr "$ACR_NAME" \
  --generate-ssh-keys \
  --location "$LOCATION" \
  --output table

# Get credentials
echo ""
echo "🔑 Configuring kubectl credentials..."
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$AKS_CLUSTER_NAME" --overwrite-existing

# Create service principal for GitHub Actions
echo ""
echo "👤 Creating service principal for GitHub Actions..."
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

SP_JSON=$(az ad sp create-for-rbac \
  --name "$SP_NAME" \
  --role contributor \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
  --json-auth)

# Extract values from service principal
CLIENT_ID=$(echo "$SP_JSON" | jq -r '.clientId')
TENANT_ID=$(echo "$SP_JSON" | jq -r '.tenantId')

echo ""
echo "🎉 Infrastructure setup complete!"
echo "================================="

echo ""
echo "📝 GitHub Repository Secrets Configuration"
echo "=========================================="
echo "Go to: https://github.com/ssamadda_microsoft/SfMC_Projects/settings/secrets/actions"
echo ""
echo "Add the following secrets:"
echo ""
echo "AZURE_CLIENT_ID: $CLIENT_ID"
echo "AZURE_TENANT_ID: $TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
echo "ACR_LOGIN_SERVER: $ACR_NAME.azurecr.io"
echo "AKS_RESOURCE_GROUP: $RESOURCE_GROUP"
echo "AKS_CLUSTER_NAME: $AKS_CLUSTER_NAME"

echo ""
echo "💾 Saving configuration to deployment_config.txt..."
cat > deployment_config.txt << EOF
# SfMC Java Microservices Demo - Deployment Configuration
# Generated on: $(date)

# Azure Resources
RESOURCE_GROUP=$RESOURCE_GROUP
LOCATION=$LOCATION
AKS_CLUSTER_NAME=$AKS_CLUSTER_NAME
ACR_NAME=$ACR_NAME
SUBSCRIPTION_ID=$SUBSCRIPTION_ID

# GitHub Secrets (add these to repository settings)
AZURE_CLIENT_ID=$CLIENT_ID
AZURE_TENANT_ID=$TENANT_ID
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
ACR_LOGIN_SERVER=$ACR_NAME.azurecr.io
AKS_RESOURCE_GROUP=$RESOURCE_GROUP
AKS_CLUSTER_NAME=$AKS_CLUSTER_NAME

# GitHub Repository URL
GITHUB_REPO=https://github.com/ssamadda_microsoft/SfMC_Projects
GITHUB_SECRETS_URL=https://github.com/ssamadda_microsoft/SfMC_Projects/settings/secrets/actions

# Service Principal JSON (for reference)
SERVICE_PRINCIPAL_JSON='$SP_JSON'
EOF

echo ""
echo "🚀 Next Steps:"
echo "1. Add the GitHub secrets shown above to your repository"
echo "2. Push changes to the JavaMicroservicesDemo folder to trigger the pipeline"
echo "3. Monitor the deployment at: https://github.com/ssamadda_microsoft/SfMC_Projects/actions"
echo ""
echo "📊 Test the deployment:"
echo "kubectl get svc  # Get service URLs"
echo "kubectl get pods # Check pod status"
echo ""
echo "Configuration saved to: deployment_config.txt"
echo "✅ Setup complete! Your Java Microservices demo is ready to deploy!"