package com.facepanel.service;

import com.facepanel.model.Session;
import com.facepanel.repository.SessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class SessionService {
    private final SessionRepository sessionRepository;

    public Optional<Session> getActiveSession() {
        return sessionRepository.findByActiveTrue();
    }

    public Session startNewSession(String name) {
        // Завершаем старую, если есть
        sessionRepository.findByActiveTrue().ifPresent(s -> {
            s.setActive(false);
            s.setEndTime(LocalDateTime.now());
            sessionRepository.save(s);
        });

        // Создаём новую
        LocalDateTime now = LocalDateTime.now();
        Session newSession = Session.builder()
                .name(name)
                .startTime(now)
                .active(true)
                .build();

        return sessionRepository.save(newSession);
    }

    public void stopActiveSession() {
        sessionRepository.findByActiveTrue().ifPresent(s -> {
            LocalDateTime endTime = LocalDateTime.now();
            s.setActive(false);
            s.setEndTime(endTime);
            sessionRepository.save(s);
        });
    }
}
