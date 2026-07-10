package com.facepanel.controller;

import com.facepanel.util.TransliterationUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Controller
@RequestMapping("/upload")
public class FileUploadController {

    @Value("${app.faces.directory:faces}")
    private String facesDirectory;

    @PostMapping("/photo")
    @ResponseBody
    public ResponseEntity<Map<String, Object>> uploadPhoto(@RequestParam("file") MultipartFile file) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            // Проверяем, что файл не пустой
            if (file.isEmpty()) {
                response.put("success", false);
                response.put("message", "Файл не выбран");
                return ResponseEntity.badRequest().body(response);
            }
            
            // Проверяем тип файла
            String contentType = file.getContentType();
            if (contentType == null || !contentType.startsWith("image/")) {
                response.put("success", false);
                response.put("message", "Выберите изображение (JPG, PNG, GIF)");
                return ResponseEntity.badRequest().body(response);
            }
            
            // Проверяем размер файла (максимум 5MB)
            if (file.getSize() > 5 * 1024 * 1024) {
                response.put("success", false);
                response.put("message", "Размер файла не должен превышать 5MB");
                return ResponseEntity.badRequest().body(response);
            }
            
            // Создаем папку faces, если её нет
            Path facesPath = Paths.get(facesDirectory);
            if (!Files.exists(facesPath)) {
                Files.createDirectories(facesPath);
            }
            
            // Генерируем имя файла на основе оригинального имени
            String originalFilename = file.getOriginalFilename();
            
            // Определяем расширение на основе MIME типа
            String extension = ".jpg"; // По умолчанию jpg
            if (contentType != null) {
                switch (contentType.toLowerCase()) {
                    case "image/png":
                        extension = ".png";
                        break;
                    case "image/gif":
                        extension = ".gif";
                        break;
                case "image/jpeg":
                    extension = ".jpeg";
                    break;
                case "image/jpg":
                default:
                    extension = ".jpg";
                    break;
                }
            }
            
            // Создаем имя файла на основе оригинального имени с транслитерацией
            String baseName = "photo";
            if (originalFilename != null && originalFilename.contains(".")) {
                baseName = originalFilename.substring(0, originalFilename.lastIndexOf("."));
            }
            
            // Транслитерируем и очищаем имя от недопустимых символов
            baseName = TransliterationUtil.cleanFilename(baseName);
            
            // Добавляем UUID для уникальности (один общий UUID для имени и расширения)
            String uniqueSuffix = UUID.randomUUID().toString().substring(0, 8);
            String filename = baseName + "_" + uniqueSuffix + extension;
            String filenameWithoutExt = baseName + "_" + uniqueSuffix;
            
            // Сохраняем файл
            Path filePath = facesPath.resolve(filename);
            Files.copy(file.getInputStream(), filePath);
            
            // Возвращаем информацию о файле
            response.put("success", true);
            response.put("filename", filenameWithoutExt);
            response.put("originalName", originalFilename);
            response.put("size", file.getSize());
            response.put("contentType", contentType);
            
            return ResponseEntity.ok(response);
            
        } catch (IOException e) {
            response.put("success", false);
            response.put("message", "Ошибка при сохранении файла: " + e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }
    
    @GetMapping("/faces/{filename}")
    @ResponseBody
    public ResponseEntity<byte[]> getFaceImage(@PathVariable String filename) {
        try {
            Path filePath = Paths.get(facesDirectory, filename);
            
            if (!Files.exists(filePath)) {
                return ResponseEntity.notFound().build();
            }
            
            byte[] imageBytes = Files.readAllBytes(filePath);
            String contentType = Files.probeContentType(filePath);
            
            if (contentType == null) {
                contentType = "image/jpeg"; // По умолчанию
            }
            
            return ResponseEntity.ok()
                    .header("Content-Type", contentType)
                    .body(imageBytes);
                    
        } catch (IOException e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
