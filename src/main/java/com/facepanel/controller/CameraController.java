package com.facepanel.controller;

import com.facepanel.model.Camera;
import com.facepanel.service.CameraService;
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

    private final CameraService cameraService;

    // ===== Страница управления камерами =====

    @GetMapping("/cameras")
    public String view(@RequestParam(required = false) Long edit, Model model) {
        model.addAttribute("cameras", cameraService.findAll());
        model.addAttribute("editing", edit != null
                ? cameraService.findAll().stream().filter(c -> c.getId().equals(edit)).findFirst().orElse(null)
                : null);
        return "cameras";
    }

    @PostMapping("/cameras/add")
    public String add(@RequestParam String name,
                      @RequestParam(required = false) String building,
                      @RequestParam(required = false) String cameraUrl,
                      @RequestParam(required = false) String espUrl,
                      @RequestParam(required = false) String streamUrl) {
        if (name == null || name.trim().isEmpty()) {
            return "redirect:/cameras?error=empty";
        }
        if (cameraService.isNameTaken(name.trim(), null)) {
            return "redirect:/cameras?error=duplicate";
        }
        cameraService.create(name, building, cameraUrl, espUrl, streamUrl);
        return "redirect:/cameras?ok=added";
    }

    @PostMapping("/cameras/edit/{id}")
    public String edit(@PathVariable Long id,
                       @RequestParam String name,
                       @RequestParam(required = false) String building,
                       @RequestParam(required = false) String cameraUrl,
                       @RequestParam(required = false) String espUrl,
                       @RequestParam(required = false) String streamUrl) {
        Camera camera = cameraService.findAll().stream()
                .filter(c -> c.getId().equals(id)).findFirst().orElse(null);
        if (camera == null) {
            return "redirect:/cameras?error=notfound";
        }
        if (name == null || name.trim().isEmpty()) {
            return "redirect:/cameras?edit=" + id + "&error=empty";
        }
        if (cameraService.isNameTaken(name.trim(), id)) {
            return "redirect:/cameras?edit=" + id + "&error=duplicate";
        }
        cameraService.update(camera, name, building, cameraUrl, espUrl, streamUrl);
        // updatedAt изменился — супервизор увидит это и перезапустит процесс камеры
        return "redirect:/cameras?ok=saved";
    }

    @PostMapping("/cameras/delete/{id}")
    public String delete(@PathVariable Long id) {
        cameraService.delete(id);
        return "redirect:/cameras?ok=deleted";
    }

    // ===== REST API для Python-клиентов и супервизора (/api/v1/cameras) =====

    @GetMapping("/api/v1/cameras")
    @ResponseBody
    public List<Map<String, Object>> apiList() {
        return cameraService.findAll().stream()
                .map(this::toApiMap)
                .collect(Collectors.toList());
    }

    /**
     * Конфигурация одной камеры. Ключ — slug (так стартует Python-клиент)
     * либо отображаемое имя.
     */
    @GetMapping("/api/v1/cameras/{key}")
    @ResponseBody
    public ResponseEntity<?> apiByKey(@PathVariable String key) {
        return cameraService.find(key)
                .map(camera -> ResponseEntity.ok(toApiMap(camera)))
                .orElse(ResponseEntity.notFound().build());
    }

    private Map<String, Object> toApiMap(Camera camera) {
        Map<String, Object> map = new java.util.HashMap<>();
        map.put("id", camera.getId());
        map.put("name", camera.getName());
        map.put("slug", camera.getSlug());
        map.put("previousSlug", camera.getPreviousSlug());
        map.put("building", camera.getBuilding());
        map.put("cameraUrl", camera.getCameraUrl());
        map.put("espUrl", camera.getEspUrl());
        map.put("streamPort", camera.getStreamPort());
        map.put("streamUrl", camera.resolveStreamUrl());
        map.put("updatedAt", camera.getUpdatedAt() != null ? camera.getUpdatedAt().toString() : null);
        return map;
    }
}
