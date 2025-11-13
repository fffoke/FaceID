package com.facepanel.repository;

import com.facepanel.model.Attendance;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface AttendanceRepository extends JpaRepository<Attendance, Long> {
    List<Attendance> findBySessionId(Long sessionId);
    List<Attendance> findByTimestampBetween(LocalDateTime start, LocalDateTime end);
    
    @Query("SELECT a FROM Attendance a WHERE a.session.id = :sessionId ORDER BY a.timestamp DESC")
    List<Attendance> findBySessionIdOrderByTimestampDesc(@Param("sessionId") Long sessionId);
    
    @Query("SELECT a FROM Attendance a WHERE a.timestamp BETWEEN :start AND :end ORDER BY a.timestamp DESC")
    List<Attendance> findByTimestampBetweenOrderByTimestampDesc(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
}
