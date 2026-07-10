package com.facepanel.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "camera")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Camera {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Уникальное имя камеры — его же отправляет Python-клиент в cameraName (например KPP1)
    @Column(name = "name", nullable = false, unique = true)
    private String name;

    // Корпус, к которому относится камера
    @Column(name = "building")
    private String building;

    // RTSP/HTTP URL видеопотока
    @Column(name = "camera_url")
    private String cameraUrl;

    // URL ESP-контроллера турникета (GET-запрос открывает турникет)
    @Column(name = "esp_url")
    private String espUrl;

    // URL MJPEG-потока Python-клиента для просмотра распознавания в браузере
    @Column(name = "stream_url")
    private String streamUrl;

    @Column(nullable = false, updatable = false)
    @Builder.Default
    private LocalDateTime createdAt = LocalDateTime.now();
}
