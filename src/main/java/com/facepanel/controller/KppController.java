package com.facepanel.controller;

import com.facepanel.model.Camera;
import com.facepanel.service.CameraService;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.net.URLConnection;

@Controller
@RequiredArgsConstructor
public class KppController {

    private final CameraService cameraService;

    @GetMapping("/login")
    public String login() {
        return "login";
    }

    @GetMapping("/kpp")
    public String kpp(Model model) {
        model.addAttribute("cameras", cameraService.findAll());
        return "kpp";
    }

    // Полноэкранный монитор одной камеры (как прежние /kpp1, /kpp2)
    @GetMapping("/kpp/{key}")
    public String kppCamera(@PathVariable String key, Model model) {
        Camera camera = cameraService.find(key).orElse(null);
        // В URL и в стриме ходит slug, на экране — отображаемое имя (может быть кириллицей)
        model.addAttribute("cameraName", camera != null ? camera.getName() : key);
        model.addAttribute("cameraKey", camera != null ? camera.getSlug() : key);
        model.addAttribute("building", camera != null ? camera.getBuilding() : null);
        model.addAttribute("hasStream", camera != null && camera.resolveStreamUrl() != null);
        // Все камеры — для переключателя между КПП
        model.addAttribute("cameras", cameraService.findAll());
        return "kpp_camera";
    }

    /**
     * Прокси MJPEG-стрима через панель: браузеру достаточно доступа к порту 8080,
     * порты Python-клиентов (8090/8091) наружу открывать не нужно.
     */
    @GetMapping("/kpp/stream/{key}")
    public void proxyStream(@PathVariable String key, HttpServletResponse response) throws IOException {
        Camera camera = cameraService.find(key).orElse(null);
        String streamUrl = camera != null ? camera.resolveStreamUrl() : null;
        if (streamUrl == null) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            return;
        }

        URLConnection upstream = new URL(streamUrl).openConnection();
        upstream.setConnectTimeout(3000);
        upstream.setReadTimeout(15000);

        try (InputStream in = upstream.getInputStream()) {
            String contentType = upstream.getContentType();
            response.setContentType(contentType != null ? contentType : "multipart/x-mixed-replace; boundary=frame");
            response.setHeader("Cache-Control", "no-cache, private");

            OutputStream out = response.getOutputStream();
            byte[] buffer = new byte[16384];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
                out.flush();
            }
        } catch (IOException e) {
            // Зритель закрыл страницу или Python-клиент недоступен — это нормальное завершение
        }
    }

    // Старые адреса КПП-экранов ведут на общую страницу (на мониторах могли остаться закладки)
    @GetMapping({"/kpp1", "/kpp2"})
    public String kppLegacy() {
        return "redirect:/kpp";
    }
}
