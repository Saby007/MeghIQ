package com.demo.user.service;

import com.demo.user.model.User;
import com.demo.user.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class UserService {

    @Autowired
    private UserRepository userRepository;

    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    public Optional<User> getUserById(Long id) {
        return userRepository.findById(id);
    }

    public Optional<User> getUserByEmail(String email) {
        return userRepository.findByEmail(email);
    }

    public User createUser(User user) {
        return userRepository.save(user);
    }

    public User updateUser(Long id, User userDetails) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found with id: " + id));

        user.setName(userDetails.getName());
        user.setEmail(userDetails.getEmail());
        user.setDepartment(userDetails.getDepartment());

        return userRepository.save(user);
    }

    public void deleteUser(Long id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found with id: " + id));
        userRepository.delete(user);
    }

    public List<User> searchUsers(String query) {
        // Simple search implementation
        return userRepository.findAll().stream()
                .filter(user -> user.getName().toLowerCase().contains(query.toLowerCase()) ||
                               user.getEmail().toLowerCase().contains(query.toLowerCase()) ||
                               user.getDepartment().toLowerCase().contains(query.toLowerCase()))
                .toList();
    }

    public List<User> getUsersByDepartment(String department) {
        return userRepository.findAll().stream()
                .filter(user -> user.getDepartment().equalsIgnoreCase(department))
                .toList();
    }
}