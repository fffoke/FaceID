package com.facepanel.controller;

import com.facepanel.dto.RecognitionRequest;
import com.facepanel.dto.AttendanceDTO;
import com.facepanel.model.Attendance;
import com.facepanel.model.Session;
import com.facepanel.service.AttendanceService;
import com.facepanel.service.SessionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RequiredArgsConstructor
@RestController
@RequestMapping("/api/v1")
public class RecognitionRestController {

    private final AttendanceService attendanceService;
    private final SessionService sessionService;

    @GetMapping("/active-session")
    public ResponseEntity<?> getActiveSession() {
        return sessionService.getActiveSession()
                .map(session -> ResponseEntity.ok(Map.of(
                        "id", session.getId(),
                        "name", session.getName(),
                        "startTime", session.getStartTime()
                )))
                .orElse(ResponseEntity.ok(Map.of("active", false)));
    }

    @PostMapping("/recognitions")
    public ResponseEntity<?> receiveRecognition(@RequestBody RecognitionRequest req) {
        if ((req.getName() == null || req.getName().isBlank()) && (req.getExternalId() == null || req.getExternalId().isBlank())) {
            return ResponseEntity.badRequest().body("name or externalId required");
        }
        String nameToUse = req.getName() != null ? req.getName().trim() : req.getExternalId().trim();

        // Если sessionId не передан, используем активную сессию
        Long sessionId = req.getSessionId();
        if (sessionId == null) {
            sessionId = sessionService.getActiveSession()
                    .map(Session::getId)
                    .orElse(null);
        }

        Attendance saved = attendanceService.registerDetection(nameToUse, "DETECTED", sessionId, req.getConfidence(), req.getCameraName());
        if (saved == null) {
            return ResponseEntity.badRequest().body("person not found for provided name");
        }
        AttendanceDTO dto = AttendanceDTO.builder()
                .id(saved.getId())
                .personId(saved.getPerson() != null ? saved.getPerson().getId() : null)
                .personName(saved.getPerson() != null ? (saved.getPerson().getFirstName() + (saved.getPerson().getLastName() != null ? " " + saved.getPerson().getLastName() : "")) : nameToUse)
                .timestamp(saved.getTimestamp())
                .eventType(saved.getEventType())
                .cameraName(saved.getCameraName())
                .build();

        return ResponseEntity.ok(dto);
    }
}
