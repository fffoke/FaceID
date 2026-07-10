package com.facepanel.service;

import com.facepanel.model.Attendance;
import com.facepanel.model.Person;
import com.facepanel.model.Session;
import com.facepanel.repository.AttendanceRepository;
import com.facepanel.repository.PersonRepository;
import com.facepanel.repository.SessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.time.*;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AttendanceService {
    private final AttendanceRepository attendanceRepository;
    private final PersonRepository personRepository;
    private final SessionRepository sessionRepository;
    private final SimpMessagingTemplate messagingTemplate;
    private final PersonService personService;

    /**
     * Сохранить факт распознавания.
     * Возвращает сохранённую запись.
     */
    public Attendance registerDetection(String name, String eventType, Long sessionId, Double confidence, String cameraName) {
        System.out.println("🔍 Registering detection for: " + name + ", sessionId: " + sessionId);
        
        // find Person by photoFilename (name from Python is filename without extension)
        Person person = personRepository.findAll().stream()
                .filter(p -> {
                    if (p.getPhotoFilename() == null) return false;
                    String filename = p.getPhotoFilename().toLowerCase();
                    String nameWithoutExt = filename.replace(".jpg", "").replace(".jpeg", "").replace(".png", "");
                    return nameWithoutExt.equals(name.toLowerCase());
                })
                .findFirst()
                .orElse(null);
        
        if (person == null) {
            System.out.println("❌ Person not found for filename: " + name);
            return null; // Не создаем запись, если персона не найдена
        }
        
        System.out.println("👤 Found person: " + person.getFirstName() + " (ID: " + person.getId() + ")");

        // determine session: if sessionId provided — используем; иначе активная или null
        Session session = null;
        if (sessionId != null) {
            session = sessionRepository.findById(sessionId).orElse(null);
            System.out.println("📅 Using provided sessionId: " + sessionId + " -> " + (session != null ? session.getName() : "NOT FOUND"));
        }
        if (session == null) {
            session = sessionRepository.findByActiveTrue().orElse(null);
            if (session != null) {
                System.out.println("📅 Using active session: " + session.getName() + " (ID: " + session.getId() + ")");
            } else {
                System.out.println("📅 No active session found - will show as 'Без мероприятия'");
            }
        }

        // Если мероприятие привязано к конкретной камере — события с других камер не попадают в него
        if (session != null && session.getCameraName() != null && !session.getCameraName().isBlank()
                && !session.getCameraName().equalsIgnoreCase(cameraName)) {
            System.out.println("📷 Camera '" + cameraName + "' не привязана к мероприятию '" + session.getName()
                    + "' (ожидается '" + session.getCameraName() + "') — запись без мероприятия");
            session = null;
        }

        // Debounce: если у этого пользователя уже есть запись в последние X секунд — можно опционально игнорировать.
        // (Для простоты здесь не игнорируем; при необходимости добавим проверку.)

        Attendance att = Attendance.builder()
                .person(person)
                .session(session)
                .timestamp(LocalDateTime.now())
                .eventType(eventType)
                .cameraName(cameraName)
                .build();

        Attendance saved = attendanceRepository.save(att);
        System.out.println("✅ Attendance saved: ID=" + saved.getId() + ", Person=" + person.getFirstName() + ", Session=" + (session != null ? session.getName() : "Без мероприятия"));

        // compose payload for WebSocket (minimal)
        Map<String, Object> payload = new HashMap<>();
        payload.put("id", saved.getId());
        payload.put("personId", person.getId());
        payload.put("personName", person.getFirstName() + (person.getLastName() != null ? " " + person.getLastName() : ""));
        payload.put("personGroup", person.getGroup() != null ? person.getGroup() : "Без группы");
        payload.put("personPhotoFilename", person.getPhotoFilename());
        payload.put("personPhotoExtension", personService.getPhotoExtension(person.getPhotoFilename()));
        payload.put("timestamp", saved.getTimestamp().toString());
        payload.put("eventType", saved.getEventType());
        payload.put("sessionId", session != null ? session.getId() : null);
        payload.put("sessionName", session != null ? session.getName() : "Без мероприятия");
        payload.put("cameraName", saved.getCameraName());


        // broadcast to topic
        messagingTemplate.convertAndSend("/topic/attendance", payload);
        System.out.println("📡 WebSocket message sent to /topic/attendance");

        return saved;
    }

    public List<Attendance> getAll() {
        return attendanceRepository.findAll().stream()
                .sorted((a1, a2) -> a2.getTimestamp().compareTo(a1.getTimestamp()))
                .collect(java.util.stream.Collectors.toList());
    }

    public List<Attendance> getSessionRecords(Long sessionId) {
        return attendanceRepository.findBySessionIdOrderByTimestampDesc(sessionId);
    }

    public List<Attendance> getAttendancesByDateRange(LocalDateTime start, LocalDateTime end) {
        return attendanceRepository.findByTimestampBetweenOrderByTimestampDesc(start, end);
    }

    /**
     * Возвращает map personId -> время последнего появления сегодня (формат строки)
     */
    public Map<Long, String> getLastSeenMapForToday() {
        LocalDate today = LocalDate.now();
        LocalDateTime start = today.atStartOfDay();
        LocalDateTime end = today.plusDays(1).atStartOfDay();

        List<Attendance> list = attendanceRepository.findByTimestampBetween(start, end);
        // keep latest per person
        Map<Long, Attendance> latest = new HashMap<>();
        for (Attendance a : list) {
            if (a.getPerson() == null) continue;
            Long pid = a.getPerson().getId();
            if (!latest.containsKey(pid) || a.getTimestamp().isAfter(latest.get(pid).getTimestamp())) {
                latest.put(pid, a);
            }
        }
        return latest.entrySet().stream()
                .collect(Collectors.toMap(Map.Entry::getKey, e -> e.getValue().getTimestamp().toLocalTime().toString()));
    }

    /**
     * Возвращает map personId -> true/false (пришел ли на сессию)
     */
    public Map<Long, Boolean> getAttendanceStatusForSession(Long sessionId) {
        List<Attendance> sessionAttendances = attendanceRepository.findBySessionId(sessionId);
        return sessionAttendances.stream()
                .filter(a -> a.getPerson() != null)
                .collect(Collectors.toMap(
                    a -> a.getPerson().getId(),
                    a -> true,
                    (existing, replacement) -> true // если несколько записей, считаем что пришел
                ));
    }

    /**
     * Возвращает map personId -> время прихода (LocalDateTime)
     */
    public Map<Long, LocalDateTime> getAttendanceTimesForSession(Long sessionId) {
        List<Attendance> sessionAttendances = attendanceRepository.findBySessionId(sessionId);
        return sessionAttendances.stream()
                .filter(a -> a.getPerson() != null)
                .collect(Collectors.toMap(
                    a -> a.getPerson().getId(),
                    a -> a.getTimestamp(),
                    (existing, replacement) -> existing.isBefore(replacement) ? existing : replacement
                ));
    }
}
