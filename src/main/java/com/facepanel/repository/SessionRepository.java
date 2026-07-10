package com.facepanel.repository;

import com.facepanel.model.Session;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SessionRepository extends JpaRepository<Session, Long> {
    Optional<Session> findByActiveTrue();
    List<Session> findAllByOrderByStartTimeDesc();
}
