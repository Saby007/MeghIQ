# Deployment script for .NET Monitoring Demo Application

param(
    [string]$ResourceGroup = "monitoring-demo-1763185446530-rg",
    [string]$WebAppName = "dotnet-monitoring-demo-1763185446530",
    [string]$PublishPath = "./MonitoringDemo/publish"
)

Write-Host "🚀 Starting deployment of .NET Monitoring Demo Application" -ForegroundColor Green

# Set Application Insights connection string
Write-Host "📊 Configuring Application Insights..." -ForegroundColor Blue
$connectionString = "InstrumentationKey=5f4ae330-4022-4dbb-b87b-4b8078b2597a;IngestionEndpoint=https://centralus-0.in.applicationinsights.azure.com/;LiveEndpoint=https://centralus.livediagnostics.monitor.azure.com/;ApplicationId=138b28df-8cfa-4b50-9382-b02a7099b570"

try {
    az webapp config appsettings set `
        --name $WebAppName `
        --resource-group $ResourceGroup `
        --settings "APPLICATIONINSIGHTS_CONNECTION_STRING=$connectionString"
    
    Write-Host "✅ Application Insights configured successfully" -ForegroundColor Green
}
catch {
    Write-Host "⚠️ Warning: Application Insights configuration may have failed" -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor Yellow
}

# Deploy the application
Write-Host "📦 Deploying application..." -ForegroundColor Blue
try {
    # Create zip file for deployment
    $zipPath = "./MonitoringDemo/monitoring-demo.zip"
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    
    # Compress the published files
    Compress-Archive -Path "$PublishPath\*" -DestinationPath $zipPath -Force
    
    # Deploy using az webapp deployment
    az webapp deployment source config-zip `
        --name $WebAppName `
        --resource-group $ResourceGroup `
        --src $zipPath
    
    Write-Host "✅ Application deployed successfully!" -ForegroundColor Green
    Write-Host "🌐 App URL: https://$WebAppName.azurewebsites.net" -ForegroundColor Cyan
    Write-Host "📊 Dashboard: https://$WebAppName.azurewebsites.net/api/dashboard" -ForegroundColor Cyan
    Write-Host "🔧 Health: https://$WebAppName.azurewebsites.net/api/test/health" -ForegroundColor Cyan
}
catch {
    Write-Host "❌ Deployment failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}