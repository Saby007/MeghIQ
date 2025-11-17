using Microsoft.EntityFrameworkCore;
using MonitoringDemo.Data;
using MonitoringDemo.Models;

namespace MonitoringDemo.Services
{
    public interface IDatabaseService
    {
        Task<DemoEntity> CreateEntityAsync(string name);
        Task<IEnumerable<DemoEntity>> GetAllEntitiesAsync();
        Task<long> GetEntityCountAsync();
        Task<bool> IsHealthyAsync();
    }
    
    public class DatabaseService : IDatabaseService
    {
        private readonly ApplicationDbContext _context;
        private readonly ILogger<DatabaseService> _logger;
        
        public DatabaseService(ApplicationDbContext context, ILogger<DatabaseService> logger)
        {
            _context = context;
            _logger = logger;
        }
        
        public async Task<DemoEntity> CreateEntityAsync(string name)
        {
            try
            {
                var entity = new DemoEntity 
                { 
                    Name = name,
                    CreatedAt = DateTime.UtcNow
                };
                
                _context.Entities.Add(entity);
                await _context.SaveChangesAsync();
                
                _logger.LogInformation("Created entity: {EntityName} with ID: {EntityId}", name, entity.Id);
                return entity;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to create entity: {EntityName}", name);
                throw;
            }
        }
        
        public async Task<IEnumerable<DemoEntity>> GetAllEntitiesAsync()
        {
            try
            {
                return await _context.Entities.OrderBy(e => e.Id).ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to retrieve entities");
                throw;
            }
        }
        
        public async Task<long> GetEntityCountAsync()
        {
            try
            {
                return await _context.Entities.CountAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to get entity count");
                throw;
            }
        }
        
        public async Task<bool> IsHealthyAsync()
        {
            try
            {
                // Simple connectivity test
                await _context.Database.CanConnectAsync();
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Database health check failed");
                return false;
            }
        }
    }
}