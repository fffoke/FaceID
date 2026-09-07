package com.facepanel.service;

import com.facepanel.model.Camera;
import com.facepanel.repository.CameraRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.net.URI;

/**
 * Досыпает slug и streamPort камерам, заведённым до появления этих полей.
 * Порт по возможности берётся из уже указанного stream_url, чтобы у работающих
 * камер он не поехал: 8090 в базе должен остаться 8090 и у systemd-юнита.
 */
@Component
@RequiredArgsConstructor
public class CameraMigration implements ApplicationRunner {

    private final CameraRepository cameraRepository;
    private final CameraService cameraService;

    @Override
    public void run(ApplicationArguments args) {
        for (Camera camera : cameraRepository.findAllByOrderByNameAsc()) {
            boolean changed = false;

            if (camera.getSlug() == null || camera.getSlug().isBlank()) {
                camera.setSlug(cameraService.buildSlug(camera.getName(), camera.getId()));
                changed = true;
            }

            if (camera.getStreamPort() == null) {
                Integer fromUrl = portFromUrl(camera.getStreamUrl());
                camera.setStreamPort(fromUrl != null ? fromUrl : cameraService.nextFreeStreamPort());
                changed = true;
            }

            if (camera.getUpdatedAt() == null) {
                camera.setUpdatedAt(camera.getCreatedAt());
                changed = true;
            }

            if (changed) {
                cameraRepository.save(camera);
                System.out.println("📷 Камера '" + camera.getName() + "': slug=" + camera.getSlug()
                        + ", streamPort=" + camera.getStreamPort());
            }
        }
    }

    private Integer portFromUrl(String url) {
        if (url == null || url.isBlank()) return null;
        try {
            int port = URI.create(url.trim()).getPort();
            return port > 0 ? port : null;
        } catch (Exception e) {
            return null;
        }
    }
}
