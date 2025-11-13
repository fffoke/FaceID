package com.facepanel.controller;

import com.facepanel.model.Attendance;
import com.facepanel.service.AttendanceService;
import com.facepanel.service.PersonService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@Controller
@RequestMapping("/attendance")
@RequiredArgsConstructor
public class AttendanceController {

    private final AttendanceService attendanceService;
    private final PersonService personService;

    @GetMapping
    public String history(Model model, 
                         @RequestParam(required = false) String date,
                         @RequestParam(required = false) Long sessionId) {
        
        LocalDate targetDate = date != null ? LocalDate.parse(date) : LocalDate.now();
        LocalDateTime start = targetDate.atStartOfDay();
        LocalDateTime end = targetDate.plusDays(1).atStartOfDay();
        
        List<Attendance> attendances;
        if (sessionId != null) {
            attendances = attendanceService.getSessionRecords(sessionId);
        } else {
            attendances = attendanceService.getAttendancesByDateRange(start, end);
        }
        
        model.addAttribute("attendances", attendances);
        model.addAttribute("selectedDate", targetDate);
        model.addAttribute("selectedSessionId", sessionId);
        model.addAttribute("personService", personService);
        
        return "attendance";
    }
}
