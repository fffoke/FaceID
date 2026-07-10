package com.facepanel.controller;

import com.facepanel.model.Attendance;
import com.facepanel.model.Person;
import com.facepanel.model.Session;
import com.facepanel.service.AttendanceService;
import com.facepanel.service.PersonService;
import com.facepanel.service.SessionService;
import lombok.RequiredArgsConstructor;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.ss.util.CellRangeAddress;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import java.nio.charset.StandardCharsets;
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
        ).stream().filter(a -> a.getPerson() != null).collect(Collectors.toList());

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
    public ResponseEntity<byte[]> exportToExcel(
            @RequestParam(required = false) String period,
            @RequestParam(required = false) Long sessionId,
            @RequestParam(required = false) List<String> columns) {
        try {
            if (sessionId != null) {
                return buildSessionReport(sessionId);
            }
            return buildPeriodReport(period, columns);
        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.internalServerError().build();
        }
    }

    /**
     * Отчёт по мероприятию: ФИО / Группа / Должность / Пришёл (Да/Нет)
     * по всем персонам целевой аудитории мероприятия + общая статистика.
     */
    private ResponseEntity<byte[]> buildSessionReport(Long sessionId) throws IOException {
        Session session = sessionService.findById(sessionId).orElse(null);
        if (session == null) {
            return ResponseEntity.notFound().build();
        }

        List<Person> persons = new ArrayList<>(
                personService.filterByTargetType(personService.getAll(), session.getTargetType()));
        persons.sort(Comparator.comparing(
                p -> ((p.getLastName() != null ? p.getLastName() : "") + " " + p.getFirstName()).toLowerCase()));

        Map<Long, Boolean> status = attendanceService.getAttendanceStatusForSession(sessionId);
        long cameCount = persons.stream().filter(p -> Boolean.TRUE.equals(status.get(p.getId()))).count();

        DateTimeFormatter dtf = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm");

        try (XSSFWorkbook wb = new XSSFWorkbook(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            Sheet sheet = wb.createSheet("Отчёт");
            Styles st = new Styles(wb);
            int rowIdx = 0;

            rowIdx = addTitleRow(sheet, st, rowIdx, "Отчёт по мероприятию: " + session.getName(), 4);

            rowIdx = addInfoRow(sheet, st, rowIdx, "Начало", session.getStartTime() != null ? session.getStartTime().format(dtf) : "—");
            rowIdx = addInfoRow(sheet, st, rowIdx, "Окончание", session.getEndTime() != null ? session.getEndTime().format(dtf) : "не завершено");
            rowIdx = addInfoRow(sheet, st, rowIdx, "Аудитория",
                    "Student".equals(session.getTargetType()) ? "Студенты"
                            : "Employee".equals(session.getTargetType()) ? "Сотрудники" : "Все");
            rowIdx = addInfoRow(sheet, st, rowIdx, "Камера",
                    session.getCameraName() != null && !session.getCameraName().isBlank() ? session.getCameraName() : "Все камеры");
            rowIdx++;

            rowIdx = addTitleRow(sheet, st, rowIdx, "Общая статистика", 4);
            rowIdx = addInfoRow(sheet, st, rowIdx, "Всего участников", String.valueOf(persons.size()));
            rowIdx = addInfoRow(sheet, st, rowIdx, "Пришли", String.valueOf(cameCount));
            rowIdx = addInfoRow(sheet, st, rowIdx, "Не пришли", String.valueOf(persons.size() - cameCount));
            rowIdx = addInfoRow(sheet, st, rowIdx, "Посещаемость",
                    persons.isEmpty() ? "0%" : Math.round(cameCount * 100.0 / persons.size()) + "%");
            rowIdx++;

            Row header = sheet.createRow(rowIdx++);
            String[] headers = {"ФИО", "Группа", "Должность", "Пришёл"};
            for (int i = 0; i < headers.length; i++) {
                Cell cell = header.createCell(i);
                cell.setCellValue(headers[i]);
                cell.setCellStyle(st.header);
            }

            for (Person person : persons) {
                Row row = sheet.createRow(rowIdx++);
                boolean came = Boolean.TRUE.equals(status.get(person.getId()));

                String fio = (person.getLastName() != null ? person.getLastName() + " " : "")
                        + person.getFirstName()
                        + (person.getMiddleName() != null && !person.getMiddleName().isBlank() ? " " + person.getMiddleName() : "");

                createCell(row, 0, fio, st.cell);
                createCell(row, 1, person.getGroup() != null ? person.getGroup() : "", st.cell);
                createCell(row, 2, "Student".equals(person.getPosition()) ? "Студент"
                        : "Employee".equals(person.getPosition()) ? "Сотрудник"
                        : person.getPosition() != null ? person.getPosition() : "", st.cell);
                createCell(row, 3, came ? "Да" : "Нет", came ? st.yes : st.no);
            }

            autosize(sheet, 4);
            wb.write(out);

            return xlsxResponse(out.toByteArray(), "Отчёт " + session.getName() + ".xlsx");
        }
    }

    /**
     * Отчёт за период (сегодня/неделя/месяц/год) с выбором колонок + общая статистика.
     */
    private ResponseEntity<byte[]> buildPeriodReport(String period, List<String> columns) throws IOException {
        if (columns == null || columns.isEmpty()) {
            columns = Arrays.asList("date", "name", "group", "position", "arrival", "departure", "event");
        }

        LocalDate endDate = LocalDate.now();
        LocalDate startDate;
        if ("week".equals(period)) {
            startDate = endDate.minusWeeks(1);
        } else if ("month".equals(period)) {
            startDate = endDate.minusMonths(1);
        } else if ("year".equals(period)) {
            startDate = endDate.minusYears(1);
        } else {
            startDate = endDate;
        }

        List<Attendance> attendances = attendanceService.getAttendancesByDateRange(
                        startDate.atStartOfDay(), endDate.plusDays(1).atStartOfDay())
                .stream().filter(a -> a.getPerson() != null).collect(Collectors.toList());

        long uniquePersons = attendances.stream().map(a -> a.getPerson().getId()).distinct().count();
        long uniqueSessions = attendances.stream().filter(a -> a.getSession() != null)
                .map(a -> a.getSession().getId()).distinct().count();

        DateTimeFormatter dateFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy");
        DateTimeFormatter timeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss");

        try (XSSFWorkbook wb = new XSSFWorkbook(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            Sheet sheet = wb.createSheet("Посещаемость");
            Styles st = new Styles(wb);
            int rowIdx = 0;

            List<String> headerNames = new ArrayList<>();
            if (columns.contains("date")) headerNames.add("Дата");
            if (columns.contains("name")) headerNames.add("ФИО");
            if (columns.contains("group")) headerNames.add("Группа");
            if (columns.contains("position")) headerNames.add("Должность");
            if (columns.contains("arrival")) headerNames.add("Пришёл");
            if (columns.contains("departure")) headerNames.add("Ушёл");
            if (columns.contains("event")) headerNames.add("Мероприятие");
            int colCount = Math.max(headerNames.size(), 2);

            rowIdx = addTitleRow(sheet, st, rowIdx, "Отчёт о посещаемости", colCount);
            rowIdx = addInfoRow(sheet, st, rowIdx, "Период",
                    startDate.format(dateFormatter) + " — " + endDate.format(dateFormatter));
            rowIdx++;

            rowIdx = addTitleRow(sheet, st, rowIdx, "Общая статистика", colCount);
            rowIdx = addInfoRow(sheet, st, rowIdx, "Всего проходов", String.valueOf(attendances.size()));
            rowIdx = addInfoRow(sheet, st, rowIdx, "Уникальных людей", String.valueOf(uniquePersons));
            rowIdx = addInfoRow(sheet, st, rowIdx, "Мероприятий", String.valueOf(uniqueSessions));
            rowIdx++;

            Row header = sheet.createRow(rowIdx++);
            for (int i = 0; i < headerNames.size(); i++) {
                Cell cell = header.createCell(i);
                cell.setCellValue(headerNames.get(i));
                cell.setCellStyle(st.header);
            }

            // Группируем по дате и персоне: первый проход = пришёл, последний = ушёл
            Map<LocalDate, Map<Long, List<Attendance>>> grouped = attendances.stream()
                    .collect(Collectors.groupingBy(
                            a -> a.getTimestamp().toLocalDate(),
                            Collectors.groupingBy(a -> a.getPerson().getId())
                    ));

            List<LocalDate> sortedDates = new ArrayList<>(grouped.keySet());
            Collections.sort(sortedDates);

            for (LocalDate date : sortedDates) {
                List<Map.Entry<Long, List<Attendance>>> sortedPersons = new ArrayList<>(grouped.get(date).entrySet());
                sortedPersons.sort(Comparator.comparing(e -> {
                    Person p = e.getValue().get(0).getPerson();
                    return ((p.getLastName() != null ? p.getLastName() : "") + " " + p.getFirstName()).toLowerCase();
                }));

                for (Map.Entry<Long, List<Attendance>> entry : sortedPersons) {
                    List<Attendance> dayRecords = entry.getValue();
                    dayRecords.sort(Comparator.comparing(Attendance::getTimestamp));
                    Attendance first = dayRecords.get(0);
                    Attendance last = dayRecords.get(dayRecords.size() - 1);
                    Person person = first.getPerson();

                    Row row = sheet.createRow(rowIdx++);
                    int col = 0;
                    if (columns.contains("date")) createCell(row, col++, date.format(dateFormatter), st.cell);
                    if (columns.contains("name")) createCell(row, col++,
                            (person.getLastName() != null ? person.getLastName() + " " : "") + person.getFirstName(), st.cell);
                    if (columns.contains("group")) createCell(row, col++,
                            person.getGroup() != null ? person.getGroup() : "", st.cell);
                    if (columns.contains("position")) createCell(row, col++,
                            "Student".equals(person.getPosition()) ? "Студент"
                                    : "Employee".equals(person.getPosition()) ? "Сотрудник"
                                    : person.getPosition() != null ? person.getPosition() : "", st.cell);
                    if (columns.contains("arrival")) createCell(row, col++,
                            first.getTimestamp().toLocalTime().format(timeFormatter), st.cell);
                    if (columns.contains("departure")) createCell(row, col++,
                            dayRecords.size() > 1 ? last.getTimestamp().toLocalTime().format(timeFormatter) : "", st.cell);
                    if (columns.contains("event")) createCell(row, col++,
                            first.getSession() != null ? first.getSession().getName() : "", st.cell);
                }
            }

            autosize(sheet, colCount);
            wb.write(out);

            return xlsxResponse(out.toByteArray(),
                    "Посещаемость " + startDate.format(dateFormatter) + " - " + endDate.format(dateFormatter) + ".xlsx");
        }
    }

    // ===== Вспомогательные методы для Excel =====

    /** Стили книги: создаются один раз, переиспользуются во всех ячейках */
    private static class Styles {
        final CellStyle title;
        final CellStyle infoLabel;
        final CellStyle header;
        final CellStyle cell;
        final CellStyle yes;
        final CellStyle no;

        Styles(Workbook wb) {
            Font titleFont = wb.createFont();
            titleFont.setBold(true);
            titleFont.setFontHeightInPoints((short) 13);
            title = wb.createCellStyle();
            title.setFont(titleFont);

            Font boldFont = wb.createFont();
            boldFont.setBold(true);
            infoLabel = wb.createCellStyle();
            infoLabel.setFont(boldFont);

            Font headerFont = wb.createFont();
            headerFont.setBold(true);
            headerFont.setColor(IndexedColors.WHITE.getIndex());
            header = wb.createCellStyle();
            header.setFont(headerFont);
            header.setFillForegroundColor(IndexedColors.GREY_50_PERCENT.getIndex());
            header.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            header.setAlignment(HorizontalAlignment.CENTER);
            setBorders(header);

            cell = wb.createCellStyle();
            setBorders(cell);

            Font yesFont = wb.createFont();
            yesFont.setBold(true);
            yesFont.setColor(IndexedColors.GREEN.getIndex());
            yes = wb.createCellStyle();
            yes.setFont(yesFont);
            yes.setAlignment(HorizontalAlignment.CENTER);
            setBorders(yes);

            Font noFont = wb.createFont();
            noFont.setBold(true);
            noFont.setColor(IndexedColors.RED.getIndex());
            no = wb.createCellStyle();
            no.setFont(noFont);
            no.setAlignment(HorizontalAlignment.CENTER);
            setBorders(no);
        }

        private static void setBorders(CellStyle style) {
            style.setBorderTop(BorderStyle.THIN);
            style.setBorderBottom(BorderStyle.THIN);
            style.setBorderLeft(BorderStyle.THIN);
            style.setBorderRight(BorderStyle.THIN);
        }
    }

    private int addTitleRow(Sheet sheet, Styles st, int rowIdx, String text, int mergeCols) {
        Row row = sheet.createRow(rowIdx);
        Cell cell = row.createCell(0);
        cell.setCellValue(text);
        cell.setCellStyle(st.title);
        if (mergeCols > 1) {
            sheet.addMergedRegion(new CellRangeAddress(rowIdx, rowIdx, 0, mergeCols - 1));
        }
        return rowIdx + 1;
    }

    private int addInfoRow(Sheet sheet, Styles st, int rowIdx, String label, String value) {
        Row row = sheet.createRow(rowIdx);
        Cell labelCell = row.createCell(0);
        labelCell.setCellValue(label);
        labelCell.setCellStyle(st.infoLabel);
        row.createCell(1).setCellValue(value);
        return rowIdx + 1;
    }

    private void createCell(Row row, int col, String value, CellStyle style) {
        Cell cell = row.createCell(col);
        cell.setCellValue(value);
        cell.setCellStyle(style);
    }

    private void autosize(Sheet sheet, int colCount) {
        for (int i = 0; i < colCount; i++) {
            sheet.autoSizeColumn(i);
            // Запас ширины: autoSizeColumn считает кириллицу впритык
            sheet.setColumnWidth(i, Math.min(sheet.getColumnWidth(i) + 512, 255 * 256));
        }
    }

    private ResponseEntity<byte[]> xlsxResponse(byte[] bytes, String filename) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.parseMediaType(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"));
        headers.setContentDisposition(ContentDisposition.attachment()
                .filename(filename, StandardCharsets.UTF_8)
                .build());
        return ResponseEntity.ok().headers(headers).body(bytes);
    }
}
