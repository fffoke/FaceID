package com.facepanel.controller;

import com.facepanel.model.Person;
import com.facepanel.model.Attendance;
import com.facepanel.service.AttendanceService;
import com.facepanel.service.PersonService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Comparator;

@Controller
@RequiredArgsConstructor
public class DashboardController {

    private final PersonService personService;
    private final AttendanceService attendanceService;

    @GetMapping("/")
    public String dashboard(Model model) {
        // Получаем логи распознаваний за сегодня
        LocalDate today = LocalDate.now();
        LocalDateTime start = today.atStartOfDay();
        LocalDateTime end = today.plusDays(1).atStartOfDay();
        
        List<Attendance> todayLogs = attendanceService.getAttendancesByDateRange(start, end);
        
        // Сортируем по времени - новые сверху (по убыванию)
        todayLogs.sort(Comparator.comparing(Attendance::getTimestamp).reversed());
        
        model.addAttribute("logs", todayLogs);
        model.addAttribute("personService", personService);
        return "dashboard";
    }
}
