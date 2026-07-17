package com.facepanel.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "person")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Person {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "first_name")
    private String firstName;
    
    @Column(name = "last_name")
    private String lastName;
    
    @Column(name = "middle_name")
    private String middleName;
    
    @Column(name = "position")
    private String position;
    
    @Column(name = "person_group")
    private String group;
    
    @Column(name = "photo_filename")
    private String photoFilename;

    @Column(name = "face_embedding", columnDefinition = "bytea")
    private byte[] faceEmbedding;

    // Отправлять уведомление в Telegram при распознавании этого человека
    @Column(name = "notify_telegram", columnDefinition = "boolean not null default false")
    @Builder.Default
    private boolean notifyTelegram = false;

    // Пол (MALE/FEMALE), скрытое служебное поле — в UI не отображается
    @Column(name = "gender")
    private String gender;

    // Скрыт на странице /for_ismal (нажат крестик) — больше не показывается там
    @Column(name = "hidden_for_ismal", columnDefinition = "boolean not null default false")
    @Builder.Default
    private boolean hiddenForIsmal = false;

    @Column(nullable = false, updatable = false)
    @Builder.Default
    private LocalDateTime createdAt = LocalDateTime.now();

    @Column(name = "updated_at")
    @Builder.Default
    private LocalDateTime updatedAt = LocalDateTime.now();

    @PrePersist
    public void onCreate() {
        autoDetectGender();
    }

    @PreUpdate
    public void onUpdate() {
        this.updatedAt = LocalDateTime.now();
        autoDetectGender();
    }

    private void autoDetectGender() {
        if (gender == null || gender.isBlank()) {
            gender = com.facepanel.util.GenderUtil.detect(lastName, firstName, middleName);
        }
    }
}
