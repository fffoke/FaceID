package com.facepanel.controller;

import com.facepanel.model.Session;
import com.facepanel.model.Person;
import com.facepanel.repository.SessionRepository;
import com.facepanel.service.PersonService;
import com.facepanel.service.AttendanceService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Controller
@RequiredArgsConstructor
@RequestMapping("/session")
public class SessionController {

    private final SessionRepository sessionRepository;
    private final PersonService personService;
    private final AttendanceService attendanceService;

    @GetMapping
    public String view(Model model) {
        Optional<Session> active = sessionRepository.findByActiveTrue();
        List<Session> allSessions = sessionRepository.findAllByOrderByStartTimeDesc();
        
        // Если есть активная сессия, получаем список персон и их статус посещения
        if (active.isPresent()) {
            List<Person> allPersons = personService.getAll();
            Map<Long, Boolean> attendanceStatus = attendanceService.getAttendanceStatusForSession(active.get().getId());
            Map<Long, LocalDateTime> attendanceTimes = attendanceService.getAttendanceTimesForSession(active.get().getId());
            
            model.addAttribute("persons", allPersons);
            model.addAttribute("attendanceStatus", attendanceStatus);
            model.addAttribute("attendanceTimes", attendanceTimes);
        }
        
        model.addAttribute("active", active.orElse(null));
        model.addAttribute("sessions", allSessions);
        return "session";
    }

    @PostMapping("/start")
    public String start(@RequestParam String name) {
        // Завершаем старую, если есть
        sessionRepository.findByActiveTrue().ifPresent(s -> {
            s.setActive(false);
            s.setEndTime(LocalDateTime.now());
            sessionRepository.save(s);
        });

        // Создаём новую
        Session newSession = Session.builder()
                .name(name)
                .startTime(LocalDateTime.now())
                .active(true)
                .build();
        sessionRepository.save(newSession);

        return "redirect:/session";
    }

    @PostMapping("/stop")
    public String stop() {
        sessionRepository.findByActiveTrue().ifPresent(active -> {
            active.setActive(false);
            active.setEndTime(LocalDateTime.now());
            sessionRepository.save(active);
        });
        return "redirect:/session";
    }

    @GetMapping("/persons-data")
    @ResponseBody
    public Map<String, Object> getPersonsData() {
        Map<String, Object> response = new HashMap<>();
        
        Optional<Session> active = sessionRepository.findByActiveTrue();
        if (active.isPresent()) {
            List<Person> allPersons = personService.getAll();
            Map<Long, Boolean> attendanceStatus = attendanceService.getAttendanceStatusForSession(active.get().getId());
            Map<Long, LocalDateTime> attendanceTimes = attendanceService.getAttendanceTimesForSession(active.get().getId());
            
            response.put("persons", allPersons);
            response.put("attendanceStatus", attendanceStatus);
            response.put("attendanceTimes", attendanceTimes);
            response.put("active", true);
        } else {
            response.put("persons", List.of());
            response.put("attendanceStatus", Map.of());
            response.put("attendanceTimes", Map.of());
            response.put("active", false);
        }
        
        return response;
    }

    @GetMapping("/history/{id}")
    public String viewHistory(@PathVariable Long id, Model model) {
        Optional<Session> sessionOpt = sessionRepository.findById(id);
        if (sessionOpt.isEmpty()) {
            return "redirect:/session";
        }

        Session session = sessionOpt.get();

        List<Person> allPersons = personService.getAll();
        Map<Long, Boolean> attendanceStatus = attendanceService.getAttendanceStatusForSession(id);
        Map<Long, LocalDateTime> attendanceTimes = attendanceService.getAttendanceTimesForSession(id);
        
        model.addAttribute("sessionData", session);
        model.addAttribute("persons", allPersons);
        model.addAttribute("attendanceStatus", attendanceStatus);
        model.addAttribute("attendanceTimes", attendanceTimes);
        model.addAttribute("personService", personService);
        
        return "session_history";
    }
    
}
