package com.facepanel.controller;

import com.facepanel.model.Attendance;
import com.facepanel.model.Person;
import com.facepanel.model.Session;
import com.facepanel.service.AttendanceService;
import com.facepanel.service.PersonService;
import com.facepanel.service.SessionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Controller
@RequestMapping("/statistics")
@RequiredArgsConstructor
public class StatisticsController {

    private final AttendanceService attendanceService;
    private final PersonService personService;
    private final SessionService sessionService;

    @GetMapping
    public String statistics(@RequestParam(required = false) String period, Model model) {
        // Определяем период для статистики
        LocalDate startDate;
        LocalDate endDate = LocalDate.now();
        
        if ("week".equals(period)) {
            startDate = endDate.minusWeeks(1);
        } else if ("month".equals(period)) {
            startDate = endDate.minusMonths(1);
        } else if ("year".equals(period)) {
            startDate = endDate.minusYears(1);
        } else {
            // По умолчанию - сегодня
            startDate = endDate;
        }

        // Получаем данные для статистики
        List<Attendance> attendances = attendanceService.getAttendancesByDateRange(
            startDate.atStartOfDay(), 
            endDate.plusDays(1).atStartOfDay()
        );

        // Статистика по дням (уникальные персоны)
        Map<String, Long> dailyStats = attendances.stream()
            .collect(Collectors.groupingBy(
                attendance -> attendance.getTimestamp().toLocalDate().toString(),
                Collectors.mapping(
                    attendance -> attendance.getPerson().getId(),
                    Collectors.toSet()
                )
            ))
            .entrySet().stream()
            .collect(Collectors.toMap(
                entry -> entry.getKey(),
                entry -> (long) entry.getValue().size()
            ));

        // Статистика по группам (уникальные персоны)
        Map<String, Long> groupStats = attendances.stream()
            .filter(attendance -> attendance.getPerson().getGroup() != null)
            .collect(Collectors.groupingBy(
                attendance -> attendance.getPerson().getGroup(),
                Collectors.mapping(
                    attendance -> attendance.getPerson().getId(),
                    Collectors.toSet()
                )
            ))
            .entrySet().stream()
            .collect(Collectors.toMap(
                entry -> entry.getKey(),
                entry -> (long) entry.getValue().size()
            ));

        // Статистика по мероприятиям (уникальные персоны)
        Map<String, Long> sessionStats = attendances.stream()
            .filter(attendance -> attendance.getSession() != null)
            .collect(Collectors.groupingBy(
                attendance -> attendance.getSession().getName(),
                Collectors.mapping(
                    attendance -> attendance.getPerson().getId(),
                    Collectors.toSet()
                )
            ))
            .entrySet().stream()
            .collect(Collectors.toMap(
                entry -> entry.getKey(),
                entry -> (long) entry.getValue().size()
            ));

        // Топ активных персон
        Map<String, Long> personStats = attendances.stream()
            .collect(Collectors.groupingBy(
                attendance -> attendance.getPerson().getFirstName() + " " + attendance.getPerson().getLastName(),
                Collectors.counting()
            ));

        // Общая статистика
        long totalAttendances = attendances.size();
        long uniquePersons = attendances.stream()
            .map(attendance -> attendance.getPerson().getId())
            .distinct()
            .count();
        long totalSessions = attendances.stream()
            .map(attendance -> attendance.getSession() != null ? attendance.getSession().getId() : 0L)
            .distinct()
            .count();

        // Передаем данные в модель
        model.addAttribute("dailyStats", dailyStats);
        model.addAttribute("groupStats", groupStats);
        model.addAttribute("sessionStats", sessionStats);
        model.addAttribute("personStats", personStats);
        model.addAttribute("totalAttendances", totalAttendances);
        model.addAttribute("uniquePersons", uniquePersons);
        model.addAttribute("totalSessions", totalSessions);
        model.addAttribute("startDate", startDate);
        model.addAttribute("endDate", endDate);
        model.addAttribute("period", period != null ? period : "today");
        
        // Добавляем отладочную информацию
        System.out.println("📊 Statistics for period: " + (period != null ? period : "today"));
        System.out.println("📊 Date range: " + startDate + " to " + endDate);
        System.out.println("📊 Total attendances found: " + totalAttendances);
        System.out.println("📊 Attendances list size: " + attendances.size());
        System.out.println("📊 Daily stats: " + dailyStats);
        System.out.println("📊 Group stats: " + groupStats);
        System.out.println("📊 Session stats: " + sessionStats);
        System.out.println("📊 Person stats: " + personStats);
        
        // Проверяем каждую запись посещения
        for (int i = 0; i < Math.min(5, attendances.size()); i++) {
            Attendance att = attendances.get(i);
            System.out.println("📊 Attendance " + i + ": " + att.getTimestamp() + " - " + 
                att.getPerson().getFirstName() + " " + att.getPerson().getLastName() + 
                " - " + (att.getSession() != null ? att.getSession().getName() : "No session"));
        }

        return "statistics";
    }

    @GetMapping("/export/excel")
    public ResponseEntity<byte[]> exportToExcel(@RequestParam(required = false) String period) {
        try {
            // Определяем период для экспорта
            LocalDate startDate;
            LocalDate endDate = LocalDate.now();
            
            if ("week".equals(period)) {
                startDate = endDate.minusWeeks(1);
            } else if ("month".equals(period)) {
                startDate = endDate.minusMonths(1);
            } else if ("year".equals(period)) {
                startDate = endDate.minusYears(1);
            } else {
                startDate = endDate;
            }

            // Получаем данные для экспорта
            List<Attendance> attendances = attendanceService.getAttendancesByDateRange(
                startDate.atStartOfDay(), 
                endDate.plusDays(1).atStartOfDay()
            );

            // Создаем Excel файл
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            createExcelFile(attendances, outputStream, startDate, endDate);

            byte[] excelBytes = outputStream.toByteArray();

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.parseMediaType("text/csv; charset=UTF-8"));
            headers.setContentDispositionFormData("attachment", 
                "attendance_report_" + startDate + "_to_" + endDate + ".csv");

            return ResponseEntity.ok()
                .headers(headers)
                .body(excelBytes);

        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.internalServerError().build();
        }
    }

    private void createExcelFile(List<Attendance> attendances, ByteArrayOutputStream outputStream, 
                                LocalDate startDate, LocalDate endDate) throws IOException {
        // Создаем CSV файл с правильной кодировкой
        StringBuilder csv = new StringBuilder();
        
        // BOM для правильного отображения кириллицы в Excel
        csv.append("\uFEFF");
        
        // Заголовки
        csv.append("Дата,Время,ФИО,Группа,Должность,Мероприятие,Тип события\n");
        
        // Данные
        DateTimeFormatter dateFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy");
        DateTimeFormatter timeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss");
        
        for (Attendance attendance : attendances) {
            Person person = attendance.getPerson();
            Session session = attendance.getSession();
            
            csv.append(attendance.getTimestamp().toLocalDate().format(dateFormatter)).append(",");
            csv.append(attendance.getTimestamp().toLocalTime().format(timeFormatter)).append(",");
            csv.append("\"").append(escapeCsv(person.getFirstName() + " " + person.getLastName())).append("\"").append(",");
            csv.append("\"").append(escapeCsv(person.getGroup() != null ? person.getGroup() : "")).append("\"").append(",");
            csv.append("\"").append(escapeCsv(person.getPosition() != null ? person.getPosition() : "")).append("\"").append(",");
            csv.append("\"").append(escapeCsv(session != null ? session.getName() : "Без мероприятия")).append("\"").append(",");
            csv.append(escapeCsv(attendance.getEventType())).append("\n");
        }
        
        // Записываем как CSV с UTF-8 кодировкой
        outputStream.write(csv.toString().getBytes("UTF-8"));
    }
    
    private String escapeCsv(String value) {
        if (value == null) return "";
        // Экранируем кавычки и запятые
        return value.replace("\"", "\"\"").replace("\n", " ").replace("\r", " ");
    }
}
