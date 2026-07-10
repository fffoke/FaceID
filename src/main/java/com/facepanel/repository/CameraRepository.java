package com.facepanel.repository;

import com.facepanel.model.Camera;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface CameraRepository extends JpaRepository<Camera, Long> {
    Optional<Camera> findByNameIgnoreCase(String name);
    List<Camera> findAllByOrderByBuildingAscNameAsc();
}
