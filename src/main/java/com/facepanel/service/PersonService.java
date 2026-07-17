package com.facepanel.service;

import com.facepanel.model.Attendance;
import com.facepanel.model.Person;
import com.facepanel.repository.AttendanceRepository;
import com.facepanel.repository.PersonRepository;
import com.facepanel.util.GenderUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.io.File;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class PersonService {
    private final PersonRepository personRepository;
    private final AttendanceRepository attendanceRepository;
    private final SimpMessagingTemplate messagingTemplate;

    @Value("${app.faces.directory:faces}")
    private String facesDirectory;

    public List<Person> getAll() { 
        return personRepository.findAll().stream()
                .sorted((p1, p2) -> p2.getCreatedAt().compareTo(p1.getCreatedAt()))
                .collect(java.util.stream.Collectors.toList());
    }
    
    public Person save(Person p) { 
        Person saved = personRepository.save(p);
        notifyPersonUpdate("PERSON_ADDED", saved);
        return saved;
    }
    
    public Optional<Person> findById(Long id) { return personRepository.findById(id); }

    // Одноразовый бэкфилл пола по отчеству для уже существующих персон (идемпотентно)
    @EventListener(ApplicationReadyEvent.class)
    public void backfillGenders() {
        List<Person> withoutGender = personRepository.findByGenderIsNull();
        List<Person> detected = new ArrayList<>();
        for (Person p : withoutGender) {
            String gender = GenderUtil.detect(p.getLastName(), p.getFirstName(), p.getMiddleName());
            if (gender != null) {
                p.setGender(gender);
                detected.add(p);
            }
        }
        if (!detected.isEmpty()) {
            personRepository.saveAll(detected);
        }
        System.out.println("👤 Gender backfill: определено " + detected.size()
                + " из " + withoutGender.size() + " персон без пола");
    }
    
    public void delete(Long id) {
        // Обнуляем ссылку на персону в истории посещаемости (историю сохраняем)
        List<Attendance> attendances = attendanceRepository.findByPersonId(id);
        attendances.forEach(a -> a.setPerson(null));
        attendanceRepository.saveAll(attendances);

        personRepository.deleteById(id);
        notifyPersonUpdate("PERSON_DELETED", Map.of("id", id));
    }
    
    public List<Person> getFilteredPersons(List<Person> persons, String search, String group, String position, String dateFrom, String dateTo) {
        return persons.stream()
                .filter(person -> {
                    if (search == null || search.isBlank()) return true;
                    String q = search.trim().toLowerCase();
                    String fio = ((person.getLastName()   != null ? person.getLastName()   : "") + " "
                               + (person.getFirstName()  != null ? person.getFirstName()  : "") + " "
                               + (person.getMiddleName() != null ? person.getMiddleName() : "")).toLowerCase();
                    return fio.contains(q);
                })
                .filter(person -> group == null || group.isEmpty() || (person.getGroup() != null && person.getGroup().equals(group)))
                .filter(person -> position == null || position.isEmpty() || (person.getPosition() != null && person.getPosition().equals(position)))
                .filter(person -> {
                    if (dateFrom == null || dateFrom.isEmpty()) return true;
                    try {
                        LocalDate fromDate = LocalDate.parse(dateFrom);
                        return person.getCreatedAt().toLocalDate().isAfter(fromDate) || person.getCreatedAt().toLocalDate().isEqual(fromDate);
                    } catch (Exception e) {
                        return true;
                    }
                })
                .filter(person -> {
                    if (dateTo == null || dateTo.isEmpty()) return true;
                    try {
                        LocalDate toDate = LocalDate.parse(dateTo);
                        return person.getCreatedAt().toLocalDate().isBefore(toDate) || person.getCreatedAt().toLocalDate().isEqual(toDate);
                    } catch (Exception e) {
                        return true;
                    }
                })
                .collect(Collectors.toList());
    }

    // targetType: "ALL" / null / "" — все персоны; "Student" / "Employee" — только указанная категория
    public List<Person> filterByTargetType(List<Person> persons, String targetType) {
        if (targetType == null || targetType.isEmpty() || "ALL".equals(targetType)) {
            return persons;
        }
        return persons.stream()
                .filter(p -> targetType.equals(p.getPosition()))
                .collect(Collectors.toList());
    }

    public Map<String, List<Person>> groupPersonsByGroup(List<Person> persons) {
        Map<String, List<Person>> grouped = new LinkedHashMap<>();
        
        // Группируем по группам
        Map<String, List<Person>> groupMap = persons.stream()
                .filter(person -> person.getGroup() != null && !person.getGroup().trim().isEmpty())
                .collect(Collectors.groupingBy(Person::getGroup, LinkedHashMap::new, Collectors.toList()));
        
        // Добавляем группы с несколькими участниками
        groupMap.entrySet().stream()
                .filter(entry -> entry.getValue().size() > 1)
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> grouped.put(entry.getKey(), entry.getValue()));
        
        // Добавляем одиночные группы в категорию "Одиночные"
        List<Person> singlePersons = groupMap.entrySet().stream()
                .filter(entry -> entry.getValue().size() == 1)
                .map(Map.Entry::getValue)
                .flatMap(List::stream)
                .collect(Collectors.toList());
        
        if (!singlePersons.isEmpty()) {
            grouped.put("Одиночные", singlePersons);
        }
        
        // Добавляем персон без группы
        List<Person> noGroupPersons = persons.stream()
                .filter(person -> person.getGroup() == null || person.getGroup().trim().isEmpty())
                .collect(Collectors.toList());
        
        if (!noGroupPersons.isEmpty()) {
            grouped.put("Без группы", noGroupPersons);
        }
        
        return grouped;
    }

    public Map<String, Object> getPersonStats(List<Person> persons) {
        Map<String, Object> stats = new HashMap<>();
        
        // Общее количество
        stats.put("total", persons.size());
        
        // По должностям
        Map<String, Long> byPosition = persons.stream()
                .collect(Collectors.groupingBy(
                    person -> person.getPosition() != null ? person.getPosition() : "Не указана",
                    Collectors.counting()
                ));
        stats.put("byPosition", byPosition);
        
        // По группам (только группы с несколькими участниками)
        Map<String, Long> byGroup = persons.stream()
                .filter(person -> person.getGroup() != null && !person.getGroup().trim().isEmpty())
                .collect(Collectors.groupingBy(Person::getGroup, Collectors.counting()))
                .entrySet().stream()
                .filter(entry -> entry.getValue() > 1)
                .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
        stats.put("byGroup", byGroup);
        
        // Количество одиночных
        long singleCount = persons.stream()
                .filter(person -> person.getGroup() != null && !person.getGroup().trim().isEmpty())
                .collect(Collectors.groupingBy(Person::getGroup, Collectors.counting()))
                .values().stream()
                .mapToLong(count -> count == 1 ? 1 : 0)
                .sum();
        stats.put("singleCount", singleCount);
        
        // Количество без группы
        long noGroupCount = persons.stream()
                .filter(person -> person.getGroup() == null || person.getGroup().trim().isEmpty())
                .count();
        stats.put("noGroupCount", noGroupCount);
        
        return stats;
    }

    /**
     * Определяет правильное расширение файла для отображения
     */
    public String getPhotoExtension(String photoFilename) {
        if (photoFilename == null || photoFilename.isEmpty()) {
            return ".jpg";
        }
        
        // Проверяем, какие файлы существуют в папке faces
        String[] extensions = {".jpeg", ".jpg", ".png", ".gif"};
        for (String ext : extensions) {
            File file = new File(facesDirectory + "/" + photoFilename + ext);
            if (file.exists()) {
                return ext;
            }
        }
        
        // По умолчанию возвращаем .jpg
        return ".jpg";
    }

    public void notifyBulkImport(int count) {
        notifyPersonUpdate("BULK_IMPORT", Map.of("count", count));
    }

    private void notifyPersonUpdate(String action, Object data) {
        Map<String, Object> payload = Map.of(
            "action", action,
            "data", data,
            "timestamp", System.currentTimeMillis()
        );
        messagingTemplate.convertAndSend("/topic/persons", payload);
        System.out.println("📡 Person update notification sent: " + action);
    }
}
