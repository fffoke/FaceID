package com.facepanel.controller;

import com.facepanel.model.Camera;
import com.facepanel.repository.CameraRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

@Controller
@RequiredArgsConstructor
public class KppController {

    private final CameraRepository cameraRepository;

    @GetMapping("/login")
    public String login() {
        return "login";
    }

    @GetMapping("/kpp")
    public String kpp(Model model) {
        model.addAttribute("cameras", cameraRepository.findAllByOrderByBuildingAscNameAsc());
        return "kpp";
    }

    // Полноэкранный монитор одной камеры (как прежние /kpp1, /kpp2)
    @GetMapping("/kpp/{name}")
    public String kppCamera(@PathVariable String name, Model model) {
        Camera camera = cameraRepository.findByNameIgnoreCase(name).orElse(null);
        model.addAttribute("cameraName", camera != null ? camera.getName() : name);
        model.addAttribute("building", camera != null ? camera.getBuilding() : null);
        model.addAttribute("streamUrl", camera != null ? camera.getStreamUrl() : null);
        return "kpp_camera";
    }

    // Старые адреса КПП-экранов ведут на общую страницу (на мониторах могли остаться закладки)
    @GetMapping({"/kpp1", "/kpp2"})
    public String kppLegacy() {
        return "redirect:/kpp";
    }
}
