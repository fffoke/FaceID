package com.facepanel.repository;

import com.facepanel.model.Session;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface SessionRepository extends JpaRepository<Session, Long> {

    /** Мероприятия, привязанные к камере, должны пережить её переименование. */
    @Modifying
    @Query("update Session s set s.cameraName = :newName where lower(s.cameraName) = lower(:oldName)")
    int renameCamera(@Param("oldName") String oldName, @Param("newName") String newName);

    Optional<Session> findByActiveTrue();
    List<Session> findAllByOrderByStartTimeDesc();
}
