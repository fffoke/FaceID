package com.facepanel.repository;

import com.facepanel.model.Camera;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface CameraRepository extends JpaRepository<Camera, Long> {
    Optional<Camera> findByNameIgnoreCase(String name);
    Optional<Camera> findBySlugIgnoreCase(String slug);
    Optional<Camera> findByPreviousSlugIgnoreCase(String previousSlug);
    List<Camera> findAllByOrderByBuildingAscNameAsc();
    List<Camera> findAllByOrderByNameAsc();
}
