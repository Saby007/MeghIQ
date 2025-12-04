package com.demo.user.config;

import com.demo.user.model.User;
import com.demo.user.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class DataInitializer implements CommandLineRunner {

    @Autowired
    private UserRepository userRepository;

    @Override
    public void run(String... args) throws Exception {
        // Initialize with sample data for CI/CD demo
        if (userRepository.count() == 0) {
            userRepository.save(new User("John Doe", "john.doe@company.com", "Engineering"));
            userRepository.save(new User("Jane Smith", "jane.smith@company.com", "Marketing"));
            userRepository.save(new User("Mike Johnson", "mike.johnson@company.com", "Engineering"));
            userRepository.save(new User("Sarah Wilson", "sarah.wilson@company.com", "Sales"));
            userRepository.save(new User("David Brown", "david.brown@company.com", "HR"));
            userRepository.save(new User("Emily Davis", "emily.davis@company.com", "Engineering"));
            
            System.out.println("Sample user data initialized for CI/CD demo!");
        }
    }
}