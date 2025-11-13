package com.facepanel.service;

import com.facepanel.model.Person;
import com.facepanel.repository.PersonRepository;
import lombok.RequiredArgsConstructor;
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
    private final SimpMessagingTemplate messagingTemplate;

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
    
    public void delete(Long id) { 
        personRepository.deleteById(id);
        notifyPersonUpdate("PERSON_DELETED", Map.of("id", id));
    }
    
    public List<Person> getFilteredPersons(List<Person> persons, String group, String position, String dateFrom, String dateTo) {
        return persons.stream()
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
            grouped.put("Управление образования Карагандинской области", singlePersons);
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
            File file = new File("faces/" + photoFilename + ext);
            if (file.exists()) {
                return ext;
            }
        }
        
        // По умолчанию возвращаем .jpg
        return ".jpg";
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
