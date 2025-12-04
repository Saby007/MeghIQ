using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using MonitoringDemo.Models;

namespace MonitoringDemo.Data
{
    public class ApplicationDbContext : DbContext
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options) : base(options)
        {
        }
        
        public DbSet<DemoEntity> Entities { get; set; }
        
        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);
            
            // Configure DemoEntity with automatic key generation  
            modelBuilder.Entity<DemoEntity>()
                .HasKey(e => e.Id);
                
            modelBuilder.Entity<DemoEntity>()
                .Property(e => e.Id)
                .ValueGeneratedOnAdd();
        }
    }
}