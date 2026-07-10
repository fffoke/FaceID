package com.facepanel.controller;

import com.facepanel.dto.BulkImportResultDTO;
import com.facepanel.service.BulkImportService;
import com.facepanel.service.PersonService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Set;
import java.util.zip.ZipException;

@Controller
@RequiredArgsConstructor
@RequestMapping("/persons/import")
public class BulkImportController {

    private final BulkImportService bulkImportService;
    private final PersonService personService;

    private static final Set<String> ALLOWED_POSITIONS = Set.of("Student", "Employee");

    /**
     * POST /persons/import
     * Принимает ZIP-архив и категорию, возвращает JSON с итогами импорта.
     */
    @PostMapping
    @ResponseBody
    public ResponseEntity<?> importZip(
            @RequestParam("file") MultipartFile file,
            @RequestParam("position") String position) {

        if (file.isEmpty()) {
            return ResponseEntity.badRequest().body("Файл не выбран");
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || !originalFilename.toLowerCase().endsWith(".zip")) {
            return ResponseEntity.badRequest().body("Допускаются только ZIP-архивы");
        }

        if (!ALLOWED_POSITIONS.contains(position)) {
            return ResponseEntity.badRequest().body("Недопустимая категория: " + position);
        }

        try {
            BulkImportResultDTO result = bulkImportService.processZip(file.getInputStream(), position);

            if (result.getSuccessCount() > 0) {
                personService.notifyBulkImport(result.getSuccessCount());
            }

            return ResponseEntity.ok(result);

        } catch (ZipException e) {
            return ResponseEntity.badRequest().body("Файл не является корректным ZIP-архивом");
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body("Ошибка обработки архива: " + e.getMessage());
        }
    }
}
