package com.facepanel.controller;

import com.facepanel.model.Attendance;
import com.facepanel.model.Camera;
import com.facepanel.repository.CameraRepository;
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
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Controller
@RequestMapping("/attendance")
@RequiredArgsConstructor
public class AttendanceController {

    private final AttendanceService attendanceService;
    private final PersonService personService;
    private final CameraRepository cameraRepository;

    @GetMapping
    public String history(Model model,
                         @RequestParam(required = false) String date,
                         @RequestParam(required = false) Long sessionId,
                         @RequestParam(required = false) String search,
                         @RequestParam(required = false) String camera,
                         @RequestParam(required = false) String building) {

        LocalDate targetDate = date != null ? LocalDate.parse(date) : LocalDate.now();
        LocalDateTime start = targetDate.atStartOfDay();
        LocalDateTime end = targetDate.plusDays(1).atStartOfDay();

        List<Attendance> attendances;
        if (sessionId != null) {
            attendances = attendanceService.getSessionRecords(sessionId);
        } else {
            attendances = attendanceService.getAttendancesByDateRange(start, end);
        }
        attendances = attendances.stream().filter(a -> a.getPerson() != null).collect(Collectors.toList());

        // Поиск по ФИО
        if (search != null && !search.isBlank()) {
            String q = search.trim().toLowerCase();
            attendances = attendances.stream()
                    .filter(a -> {
                        String fio = ((a.getPerson().getLastName()   != null ? a.getPerson().getLastName()   : "") + " "
                                   + (a.getPerson().getFirstName()  != null ? a.getPerson().getFirstName()  : "") + " "
                                   + (a.getPerson().getMiddleName() != null ? a.getPerson().getMiddleName() : "")).toLowerCase();
                        return fio.contains(q);
                    })
                    .collect(Collectors.toList());
        }

        // Фильтр по камере
        if (camera != null && !camera.isBlank()) {
            attendances = attendances.stream()
                    .filter(a -> camera.equalsIgnoreCase(a.getCameraName()))
                    .collect(Collectors.toList());
        }

        // Фильтр по корпусу — через реестр камер (cameraName -> building)
        List<Camera> allCameras = cameraRepository.findAllByOrderByBuildingAscNameAsc();
        if (building != null && !building.isBlank()) {
            Set<String> buildingCameras = allCameras.stream()
                    .filter(c -> building.equals(c.getBuilding()))
                    .map(c -> c.getName().toLowerCase())
                    .collect(Collectors.toSet());
            attendances = attendances.stream()
                    .filter(a -> a.getCameraName() != null && buildingCameras.contains(a.getCameraName().toLowerCase()))
                    .collect(Collectors.toList());
        }

        // Список корпусов для селекта
        List<String> buildings = allCameras.stream()
                .map(Camera::getBuilding)
                .filter(b -> b != null && !b.isBlank())
                .distinct()
                .sorted()
                .collect(Collectors.toList());

        model.addAttribute("attendances", attendances);
        model.addAttribute("selectedDate", targetDate);
        model.addAttribute("selectedSessionId", sessionId);
        model.addAttribute("search", search);
        model.addAttribute("selectedCamera", camera);
        model.addAttribute("selectedBuilding", building);
        model.addAttribute("cameras", allCameras);
        model.addAttribute("buildings", buildings);
        model.addAttribute("personService", personService);

        return "attendance";
    }
}
