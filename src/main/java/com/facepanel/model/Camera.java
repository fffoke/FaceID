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

    // Отображаемое имя. Может быть на кириллице («Главный вход»).
    // Его же Python-клиент присылает в cameraName, поэтому оно попадает в журнал посещений.
    @Column(name = "name", nullable = false, unique = true)
    private String name;

    // Латинский идентификатор, выведенный из name. Используется там, где кириллица ломается:
    // в URL (/kpp/{slug}) и в имени systemd-юнита (face@{slug}.service).
    @Column(name = "slug", unique = true)
    private String slug;

    // Корпус, к которому относится камера
    @Column(name = "building")
    private String building;

    // RTSP/HTTP URL видеопотока
    @Column(name = "camera_url")
    private String cameraUrl;

    // URL ESP-контроллера турникета (GET-запрос открывает турникет)
    @Column(name = "esp_url")
    private String espUrl;

    // Порт MJPEG-стрима Python-клиента. Назначается автоматически (8090, 8091, ...),
    // потому что два процесса на одном порту не уживаются.
    @Column(name = "stream_port")
    private Integer streamPort;

    // Явный URL стрима. Пусто в обычном случае — тогда адрес собирается из streamPort.
    // Заполняется руками, только если Python-клиент живёт не на этой машине.
    @Column(name = "stream_url")
    private String streamUrl;

    @Column(nullable = false, updatable = false)
    @Builder.Default
    private LocalDateTime createdAt = LocalDateTime.now();

    // Меняется при любом редактировании — по нему супервизор понимает,
    // что процесс камеры пора перезапустить с новыми параметрами.
    @Column(name = "updated_at")
    @Builder.Default
    private LocalDateTime updatedAt = LocalDateTime.now();

    /** Адрес, по которому панель забирает MJPEG у Python-клиента. */
    @Transient
    public String resolveStreamUrl() {
        if (streamUrl != null && !streamUrl.isBlank()) {
            return streamUrl.trim();
        }
        if (streamPort != null && streamPort > 0) {
            return "http://127.0.0.1:" + streamPort + "/stream";
        }
        return null;
    }
}
