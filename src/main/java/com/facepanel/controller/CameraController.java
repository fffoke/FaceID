package com.facepanel.controller;

import com.facepanel.model.Camera;
import com.facepanel.repository.CameraRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Controller
@RequiredArgsConstructor
public class CameraController {

    private final CameraRepository cameraRepository;

    // ===== Страница управления камерами =====

    @GetMapping("/cameras")
    public String view(Model model) {
        List<Camera> cameras = cameraRepository.findAllByOrderByBuildingAscNameAsc();
        model.addAttribute("cameras", cameras);
        return "cameras";
    }

    @PostMapping("/cameras/add")
    public String add(@RequestParam String name,
                      @RequestParam(required = false) String building,
                      @RequestParam(required = false) String cameraUrl,
                      @RequestParam(required = false) String espUrl,
                      @RequestParam(required = false) String streamUrl) {
        String trimmedName = name.trim();
        if (trimmedName.isEmpty() || cameraRepository.findByNameIgnoreCase(trimmedName).isPresent()) {
            return "redirect:/cameras?error=duplicate";
        }

        Camera camera = Camera.builder()
                .name(trimmedName)
                .building(building != null ? building.trim() : null)
                .cameraUrl(cameraUrl != null ? cameraUrl.trim() : null)
                .espUrl(espUrl != null ? espUrl.trim() : null)
                .streamUrl(streamUrl != null ? streamUrl.trim() : null)
                .build();
        cameraRepository.save(camera);

        return "redirect:/cameras";
    }

    @PostMapping("/cameras/delete/{id}")
    public String delete(@PathVariable Long id) {
        cameraRepository.deleteById(id);
        return "redirect:/cameras";
    }

    // ===== REST API для Python-клиентов (/api/v1/cameras) =====

    @GetMapping("/api/v1/cameras")
    @ResponseBody
    public List<Map<String, Object>> apiList() {
        return cameraRepository.findAllByOrderByBuildingAscNameAsc().stream()
                .map(this::toApiMap)
                .collect(Collectors.toList());
    }

    // Python-клиент получает свою конфигурацию (camera_url, esp_url) по имени камеры
    @GetMapping("/api/v1/cameras/{name}")
    @ResponseBody
    public ResponseEntity<?> apiByName(@PathVariable String name) {
        return cameraRepository.findByNameIgnoreCase(name)
                .map(camera -> ResponseEntity.ok(toApiMap(camera)))
                .orElse(ResponseEntity.notFound().build());
    }

    private Map<String, Object> toApiMap(Camera camera) {
        Map<String, Object> map = new java.util.HashMap<>();
        map.put("id", camera.getId());
        map.put("name", camera.getName());
        map.put("building", camera.getBuilding());
        map.put("cameraUrl", camera.getCameraUrl());
        map.put("espUrl", camera.getEspUrl());
        map.put("streamUrl", camera.getStreamUrl());
        return map;
    }
}
