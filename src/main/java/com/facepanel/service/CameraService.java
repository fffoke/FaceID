package com.facepanel.service;

import com.facepanel.model.Camera;
import com.facepanel.repository.AttendanceRepository;
import com.facepanel.repository.CameraRepository;
import com.facepanel.repository.SessionRepository;
import com.facepanel.util.TransliterationUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class CameraService {

    /** Первый порт MJPEG-стрима. Каждой следующей камере достаётся следующий свободный. */
    public static final int FIRST_STREAM_PORT = 8090;

    private final CameraRepository cameraRepository;
    private final AttendanceRepository attendanceRepository;
    private final SessionRepository sessionRepository;

    public List<Camera> findAll() {
        return cameraRepository.findAllByOrderByBuildingAscNameAsc();
    }

    /**
     * Имя камеры -> корпус. В журнале посещений хранится только имя камеры,
     * поэтому корпус для строки лога подтягивается через эту таблицу.
     */
    public Map<String, String> buildingByCameraName() {
        Map<String, String> map = new LinkedHashMap<>();
        for (Camera camera : findAll()) {
            if (camera.getBuilding() != null && !camera.getBuilding().isBlank()) {
                map.put(camera.getName(), camera.getBuilding());
            }
        }
        return map;
    }

    /** Список корпусов без повторов — для выпадающего фильтра. */
    public Set<String> buildings() {
        Set<String> set = new LinkedHashSet<>();
        for (Camera camera : findAll()) {
            if (camera.getBuilding() != null && !camera.getBuilding().isBlank()) {
                set.add(camera.getBuilding());
            }
        }
        return set;
    }

    /**
     * Ищет камеру по slug либо по отображаемому имени.
     * Python-клиент стартует со slug (кириллица в имени systemd-юнита не живёт),
     * а человек в адресной строке или в мероприятии может указать имя как есть.
     */
    public Optional<Camera> find(String key) {
        if (key == null || key.isBlank()) {
            return Optional.empty();
        }
        String trimmed = key.trim();
        Optional<Camera> bySlug = cameraRepository.findBySlugIgnoreCase(trimmed);
        return bySlug.isPresent() ? bySlug : cameraRepository.findByNameIgnoreCase(trimmed);
    }

    /**
     * Строит латинский slug из имени. «Главный вход» -> glavnyy_vhod.
     * При совпадении добавляет числовой суффикс, чтобы slug оставался уникальным.
     */
    public String buildSlug(String name, Long excludeId) {
        String base = TransliterationUtil.cleanFilename(name);
        if (base == null || base.isBlank() || "unknown".equals(base)) {
            base = "camera";
        }
        String candidate = base;
        int suffix = 2;
        while (isSlugTaken(candidate, excludeId)) {
            candidate = base + "_" + suffix++;
        }
        return candidate;
    }

    private boolean isSlugTaken(String slug, Long excludeId) {
        return cameraRepository.findBySlugIgnoreCase(slug)
                .filter(c -> excludeId == null || !c.getId().equals(excludeId))
                .isPresent();
    }

    /** Занято ли имя другой камерой. */
    public boolean isNameTaken(String name, Long excludeId) {
        return cameraRepository.findByNameIgnoreCase(name)
                .filter(c -> excludeId == null || !c.getId().equals(excludeId))
                .isPresent();
    }

    /** Наименьший свободный порт начиная с 8090 — два процесса на одном порту не уживаются. */
    public int nextFreeStreamPort() {
        List<Camera> all = cameraRepository.findAll();
        int port = FIRST_STREAM_PORT;
        boolean busy = true;
        while (busy) {
            final int candidate = port;
            busy = all.stream().anyMatch(c -> c.getStreamPort() != null && c.getStreamPort() == candidate);
            if (busy) {
                port++;
            }
        }
        return port;
    }

    public Camera create(String name, String building, String cameraUrl, String espUrl, String streamUrl) {
        Camera camera = Camera.builder()
                .name(name.trim())
                .slug(buildSlug(name, null))
                .building(trimToNull(building))
                .cameraUrl(trimToNull(cameraUrl))
                .espUrl(trimToNull(espUrl))
                .streamUrl(trimToNull(streamUrl))
                .streamPort(nextFreeStreamPort())
                .build();
        return cameraRepository.save(camera);
    }

    @Transactional
    public Camera update(Camera camera, String name, String building, String cameraUrl, String espUrl, String streamUrl) {
        String newName = name.trim();
        // slug пересобираем только при смене имени: он зашит в имя systemd-юнита,
        // и его смена на ровном месте означала бы остановку старого юнита и запуск нового
        if (!newName.equals(camera.getName())) {
            String oldName = camera.getName();
            camera.setName(newName);
            camera.setSlug(buildSlug(newName, camera.getId()));

            // Имя камеры лежит в журнале посещений и в привязке мероприятий.
            // Без переноса история осталась бы на старом имени: старые записи
            // выпали бы из фильтра по камере, а мероприятие перестало бы её узнавать.
            int movedLogs = attendanceRepository.renameCamera(oldName, newName);
            int movedSessions = sessionRepository.renameCamera(oldName, newName);
            System.out.println("📷 Камера '" + oldName + "' -> '" + newName
                    + "': перенесено записей журнала " + movedLogs + ", мероприятий " + movedSessions);
        }
        camera.setBuilding(trimToNull(building));
        camera.setCameraUrl(trimToNull(cameraUrl));
        camera.setEspUrl(trimToNull(espUrl));
        camera.setStreamUrl(trimToNull(streamUrl));
        if (camera.getStreamPort() == null) {
            camera.setStreamPort(nextFreeStreamPort());
        }
        camera.setUpdatedAt(LocalDateTime.now());
        return cameraRepository.save(camera);
    }

    public void delete(Long id) {
        cameraRepository.deleteById(id);
    }

    private String trimToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
