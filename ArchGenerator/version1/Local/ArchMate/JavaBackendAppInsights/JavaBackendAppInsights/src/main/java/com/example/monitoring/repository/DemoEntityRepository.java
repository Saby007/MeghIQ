package com.example.monitoring.repository;

import com.example.monitoring.model.DemoEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface DemoEntityRepository extends JpaRepository<DemoEntity, Integer> {
    
    List<DemoEntity> findByNameContainingIgnoreCase(String name);
    
    @Query("SELECT d FROM DemoEntity d WHERE d.name LIKE %?1%")
    List<DemoEntity> findByNameLike(String name);
    
    // This query will be used to simulate database errors
    @Query(value = "SELECT * FROM Table1 WHERE id = ?1 AND 1/0 = 1", nativeQuery = true)
    DemoEntity findWithError(Integer id);
}