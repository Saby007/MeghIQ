using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace MonitoringDemo.Models
{
    [Table("Table1")]
    public class DemoEntity
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int Id { get; set; }
        
        [Column("Name")]
        public string Name { get; set; } = string.Empty;
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        public override string ToString()
        {
            return $"DemoEntity{{ Id={Id}, Name='{Name}', CreatedAt={CreatedAt:yyyy-MM-dd HH:mm:ss} }}";
        }
    }
}