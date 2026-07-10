package com.facepanel.controller;

import com.facepanel.dto.RecognitionRequest;
import com.facepanel.model.Attendance;
import com.facepanel.service.AttendanceService;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.stereotype.Controller;

@Controller
@RequiredArgsConstructor
public class WebSocketController {

    private final AttendanceService attendanceService;

    @MessageMapping("/recognition")
    public void fromSocket(RecognitionRequest msg) {
        if (msg == null) return;
        String name = msg.getName() != null ? msg.getName() : msg.getExternalId();
        if (name == null || name.isBlank()) return;
        attendanceService.registerDetection(name.trim(), "DETECTED", msg.getSessionId(), msg.getConfidence(), msg.getCameraName());
    }
}
