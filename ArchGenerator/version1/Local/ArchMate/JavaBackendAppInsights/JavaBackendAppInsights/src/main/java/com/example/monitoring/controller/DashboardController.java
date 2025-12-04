package com.example.monitoring.controller;

import com.example.monitoring.service.BackgroundJobService;
import com.example.monitoring.service.DatabaseService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class DashboardController {
    
    private static final Logger logger = LoggerFactory.getLogger(DashboardController.class);
    
    @Autowired
    private BackgroundJobService backgroundJobService;
    
    @Autowired
    private DatabaseService databaseService;
    
    @GetMapping("/")
    public String home(Model model) {
        logger.info("Serving home page - redirecting to dashboard");
        return "redirect:/dashboard";
    }
    
    @GetMapping("/dashboard")
    public String dashboard(Model model) {
        logger.info("Serving test dashboard");
        
        // Get real-time statistics
        long totalJobs = backgroundJobService.getJobCount();
        long successJobs = backgroundJobService.getSuccessCount();
        long failedJobs = backgroundJobService.getErrorCount();
        long entityCount = databaseService.getEntityCount();
        
        model.addAttribute("title", "ARO Application Insights Demo");
        model.addAttribute("appName", "monitoring-demo");
        model.addAttribute("version", "3.5.7");
        model.addAttribute("timestamp", System.currentTimeMillis());
        model.addAttribute("totalJobs", totalJobs);
        model.addAttribute("successJobs", successJobs);
        model.addAttribute("failedJobs", failedJobs);
        model.addAttribute("entityCount", entityCount);
        
        return "test-dashboard";
    }
    
    @GetMapping("/health")
    public String health(Model model) {
        logger.info("Health check requested");
        
        model.addAttribute("status", "UP");
        model.addAttribute("timestamp", System.currentTimeMillis());
        model.addAttribute("service", "ARO Demo Application");
        
        return "health";
    }
    
    @GetMapping("/analytics")
    public String analyticsPage() {
        logger.info("Displaying live analytics dashboard");
        return "analytics-dashboard";
    }
}