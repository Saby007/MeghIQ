using Microsoft.EntityFrameworkCore;
using Microsoft.ApplicationInsights;
using Microsoft.ApplicationInsights.Extensibility;
using MonitoringDemo.Data;
using MonitoringDemo.Services;

var builder = WebApplication.CreateBuilder(args);

// Add Application Insights
builder.Services.AddApplicationInsightsTelemetry();

// Add Entity Framework with In-Memory database
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseInMemoryDatabase("MonitoringDemoDB"));

// Add custom services
builder.Services.AddScoped<IDatabaseService, DatabaseService>();
builder.Services.AddHttpClient<IExternalApiService, ExternalApiService>();
builder.Services.AddSingleton<TelemetryClient>();

// Add background service
builder.Services.AddHostedService<BackgroundJobService>();

// Add controllers
builder.Services.AddControllers();

// Add Swagger/OpenAPI
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new Microsoft.OpenApi.Models.OpenApiInfo
    {
        Title = "Monitoring Demo API",
        Version = "v1.0",
        Description = ".NET Monitoring Demo with Application Insights"
    });
});

// Add CORS for dashboard
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

var app = builder.Build();

// Ensure database is created and seeded
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    dbContext.Database.EnsureCreated();
    
    // Seed some initial data
    var dbService = scope.ServiceProvider.GetRequiredService<IDatabaseService>();
    await dbService.CreateEntityAsync("Initial-Entity-1");
    await dbService.CreateEntityAsync("Initial-Entity-2");
    await dbService.CreateEntityAsync("Startup-Entity");
}

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(c =>
    {
        c.SwaggerEndpoint("/swagger/v1/swagger.json", "Monitoring Demo API v1.0");
        c.RoutePrefix = "swagger";
    });
}

app.UseCors();

app.UseHttpsRedirection();

// Explicitly disable static files to prevent interference
// app.UseStaticFiles(); // Commented out to prevent static file serving

app.UseAuthorization();

// Map controllers
app.MapControllers();

// Add root endpoint
app.MapGet("/", () => Results.Redirect("/api/dashboard"));

Console.WriteLine("🚀 .NET Monitoring Demo Application Starting...");
Console.WriteLine("📊 Dashboard: /api/dashboard");
Console.WriteLine("🔧 Test Endpoints: /api/test/*");
Console.WriteLine("📋 Swagger UI: /swagger");
Console.WriteLine("❤️ Health Check: /api/test/health");

app.Run();
