package com.facepanel.controller;

import com.facepanel.model.Person;
import com.facepanel.repository.PersonRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.*;

@RequiredArgsConstructor
@RestController
@RequestMapping("/api/v1/embeddings")
public class EmbeddingRestController {

    private final PersonRepository personRepository;

    /**
     * Возвращает все персоны с эмбеддингами (для загрузки в Python при старте).
     * Эмбеддинг передаётся как Base64 строка.
     */
    @GetMapping
    public ResponseEntity<List<Map<String, Object>>> getAllEmbeddings() {
        List<Person> persons = personRepository.findAll();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Person p : persons) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("id", p.getId());
            entry.put("photoFilename", p.getPhotoFilename());
            entry.put("firstName", p.getFirstName());
            entry.put("lastName", p.getLastName());
            if (p.getFaceEmbedding() != null) {
                entry.put("embedding", Base64.getEncoder().encodeToString(p.getFaceEmbedding()));
            } else {
                entry.put("embedding", null);
            }
            result.add(entry);
        }
        return ResponseEntity.ok(result);
    }

    /**
     * Возвращает персоны без эмбеддингов (новые, которым нужно вычислить вектор).
     */
    @GetMapping("/pending")
    public ResponseEntity<List<Map<String, Object>>> getPending() {
        List<Person> persons = personRepository.findByFaceEmbeddingIsNull();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Person p : persons) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("id", p.getId());
            entry.put("photoFilename", p.getPhotoFilename());
            entry.put("firstName", p.getFirstName());
            entry.put("lastName", p.getLastName());
            result.add(entry);
        }
        return ResponseEntity.ok(result);
    }

    /**
     * Сохраняет эмбеддинг для персоны. Python вычисляет вектор и отправляет сюда.
     */
    @PutMapping("/{personId}")
    public ResponseEntity<?> saveEmbedding(@PathVariable Long personId,
                                           @RequestBody Map<String, String> body) {
        String embeddingBase64 = body.get("embedding");
        if (embeddingBase64 == null || embeddingBase64.isBlank()) {
            return ResponseEntity.badRequest().body("embedding is required");
        }

        return personRepository.findById(personId)
                .map(person -> {
                    person.setFaceEmbedding(Base64.getDecoder().decode(embeddingBase64));
                    person.setUpdatedAt(LocalDateTime.now());
                    personRepository.save(person);
                    return ResponseEntity.ok(Map.of("status", "ok", "personId", personId));
                })
                .orElse(ResponseEntity.notFound().build());
    }
}
