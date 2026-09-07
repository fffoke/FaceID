package com.facepanel.repository;

import com.facepanel.model.Attendance;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface AttendanceRepository extends JpaRepository<Attendance, Long> {

    /**
     * Переносит журнал на новое имя камеры при её переименовании в панели.
     * Без этого история осталась бы на старом имени и выпала бы из фильтров.
     */
    @Modifying
    @Query("update Attendance a set a.cameraName = :newName where lower(a.cameraName) = lower(:oldName)")
    int renameCamera(@Param("oldName") String oldName, @Param("newName") String newName);

    List<Attendance> findBySessionId(Long sessionId);
    List<Attendance> findByPersonId(Long personId);
    List<Attendance> findByTimestampBetween(LocalDateTime start, LocalDateTime end);
    
    @Query("SELECT a FROM Attendance a WHERE a.session.id = :sessionId ORDER BY a.timestamp DESC")
    List<Attendance> findBySessionIdOrderByTimestampDesc(@Param("sessionId") Long sessionId);
    
    @Query("SELECT a FROM Attendance a WHERE a.timestamp BETWEEN :start AND :end ORDER BY a.timestamp DESC")
    List<Attendance> findByTimestampBetweenOrderByTimestampDesc(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
}
