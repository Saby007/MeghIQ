# SfMC Java Microservices Demo - Quick Deployment Script (PowerShell)
# This script sets up Azure infrastructure and configures GitHub secrets

param(
    [string]$ResourceGroup = "sfmc-javademo-rg",
    [string]$Location = "eastus",
    [string]$AksClusterName = "sfmc-javamicroservices-aks",
    [string]$ServicePrincipalName = "sfmc-javamicroservices-github"
)

Write-Host "🚀 SfMC Java Microservices Demo - Quick Deployment Setup" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green

# Check prerequisites
Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow

try {
    az account show | Out-Null
    Write-Host "✅ Azure CLI authenticated" -ForegroundColor Green
} catch {
    Write-Host "❌ Please login to Azure CLI first: az login" -ForegroundColor Red
    exit 1
}

try {
    kubectl version --client | Out-Null
    Write-Host "✅ kubectl available" -ForegroundColor Green
} catch {
    Write-Host "❌ kubectl is required but not installed" -ForegroundColor Red
    exit 1
}

# Generate unique ACR name
$timestamp = [int][double]::Parse((Get-Date -UFormat %s))
$AcrName = "sfmcjavademo$timestamp"

Write-Host ""
Write-Host "🏗️ Creating Azure Resources..." -ForegroundColor Cyan
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "Location: $Location" -ForegroundColor White
Write-Host "AKS Cluster: $AksClusterName" -ForegroundColor White
Write-Host "Container Registry: $AcrName" -ForegroundColor White

# Create resource group
Write-Host ""
Write-Host "📦 Creating resource group..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output table

# Create Azure Container Registry
Write-Host ""
Write-Host "🐳 Creating Azure Container Registry..." -ForegroundColor Yellow
az acr create `
  --resource-group $ResourceGroup `
  --name $AcrName `
  --sku Basic `
  --location $Location `
  --output table

# Create AKS cluster
Write-Host ""
Write-Host "⚙️ Creating AKS cluster (this may take 5-10 minutes)..." -ForegroundColor Yellow
az aks create `
  --resource-group $ResourceGroup `
  --name $AksClusterName `
  --node-count 2 `
  --node-vm-size Standard_B2s `
  --enable-oidc-issuer `
  --enable-workload-identity `
  --attach-acr $AcrName `
  --generate-ssh-keys `
  --location $Location `
  --output table

# Get credentials
Write-Host ""
Write-Host "🔑 Configuring kubectl credentials..." -ForegroundColor Yellow
az aks get-credentials --resource-group $ResourceGroup --name $AksClusterName --overwrite-existing

# Create service principal for GitHub Actions
Write-Host ""
Write-Host "👤 Creating service principal for GitHub Actions..." -ForegroundColor Yellow
$SubscriptionId = az account show --query "id" -o tsv

$SpJson = az ad sp create-for-rbac `
  --name $ServicePrincipalName `
  --role contributor `
  --scopes "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup" `
  --json-auth | ConvertFrom-Json

Write-Host ""
Write-Host "🎉 Infrastructure setup complete!" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

Write-Host ""
Write-Host "📝 GitHub Repository Secrets Configuration" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Go to: https://github.com/ssamadda_microsoft/SfMC_Projects/settings/secrets/actions" -ForegroundColor Blue
Write-Host ""
Write-Host "Add the following secrets:" -ForegroundColor White
Write-Host ""
Write-Host "AZURE_CLIENT_ID: $($SpJson.clientId)" -ForegroundColor Yellow
Write-Host "AZURE_TENANT_ID: $($SpJson.tenantId)" -ForegroundColor Yellow  
Write-Host "AZURE_SUBSCRIPTION_ID: $SubscriptionId" -ForegroundColor Yellow
Write-Host "ACR_LOGIN_SERVER: $AcrName.azurecr.io" -ForegroundColor Yellow
Write-Host "AKS_RESOURCE_GROUP: $ResourceGroup" -ForegroundColor Yellow
Write-Host "AKS_CLUSTER_NAME: $AksClusterName" -ForegroundColor Yellow

Write-Host ""
Write-Host "💾 Saving configuration to deployment_config.txt..." -ForegroundColor Yellow

$configContent = @"
# SfMC Java Microservices Demo - Deployment Configuration
# Generated on: $(Get-Date)

# Azure Resources
RESOURCE_GROUP=$ResourceGroup
LOCATION=$Location
AKS_CLUSTER_NAME=$AksClusterName
ACR_NAME=$AcrName
SUBSCRIPTION_ID=$SubscriptionId

# GitHub Secrets (add these to repository settings)
AZURE_CLIENT_ID=$($SpJson.clientId)
AZURE_TENANT_ID=$($SpJson.tenantId)
AZURE_SUBSCRIPTION_ID=$SubscriptionId
ACR_LOGIN_SERVER=$AcrName.azurecr.io
AKS_RESOURCE_GROUP=$ResourceGroup
AKS_CLUSTER_NAME=$AksClusterName

# GitHub Repository URL
GITHUB_REPO=https://github.com/ssamadda_microsoft/SfMC_Projects
GITHUB_SECRETS_URL=https://github.com/ssamadda_microsoft/SfMC_Projects/settings/secrets/actions

# Service Principal JSON (for reference)
SERVICE_PRINCIPAL_JSON='$($SpJson | ConvertTo-Json -Compress)'
"@

$configContent | Out-File -FilePath "deployment_config.txt" -Encoding UTF8

Write-Host ""
Write-Host "🚀 Next Steps:" -ForegroundColor Green
Write-Host "1. Add the GitHub secrets shown above to your repository" -ForegroundColor White
Write-Host "2. Push changes to the JavaMicroservicesDemo folder to trigger the pipeline" -ForegroundColor White
Write-Host "3. Monitor the deployment at: https://github.com/ssamadda_microsoft/SfMC_Projects/actions" -ForegroundColor Blue
Write-Host ""
Write-Host "📊 Test the deployment:" -ForegroundColor Cyan
Write-Host "kubectl get svc  # Get service URLs" -ForegroundColor White
Write-Host "kubectl get pods # Check pod status" -ForegroundColor White
Write-Host ""
Write-Host "Configuration saved to: deployment_config.txt" -ForegroundColor Yellow
Write-Host "✅ Setup complete! Your Java Microservices demo is ready to deploy!" -ForegroundColor Green