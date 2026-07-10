package com.facepanel.service;

import com.facepanel.model.Person;
import com.facepanel.util.TransliterationUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Единый сервис для работы с файлами фотографий персон.
 * Содержит логику генерации имён файлов, транслитерации и сохранения —
 * используется как PersonController, так и BulkImportService.
 */
@Service
public class PhotoService {

    @Value("${app.faces.directory:faces}")
    private String facesDirectory;

    /**
     * Сохраняет байты фото в директорию faces/.
     * Имя файла генерируется на основе ФИО персоны с транслитерацией.
     * При коллизии добавляет суффикс _1, _2 и т.д.
     *
     * @param person    персона (используется для генерации имени файла)
     * @param bytes     байты изображения
     * @param extension расширение включая точку, например ".jpg"
     * @return имя файла БЕЗ расширения (для хранения в Person.photoFilename)
     */
    public String savePhoto(Person person, byte[] bytes, String extension) throws IOException {
        ensureFacesDirectoryExists();

        String baseName = generatePhotoFilename(person);
        String filenameWithoutExt = baseName;
        Path filePath = Paths.get(facesDirectory).resolve(baseName + extension);

        int counter = 1;
        while (Files.exists(filePath)) {
            filenameWithoutExt = baseName + "_" + counter;
            filePath = Paths.get(facesDirectory).resolve(filenameWithoutExt + extension);
            counter++;
        }

        Files.write(filePath, bytes);
        return filenameWithoutExt;
    }

    /**
     * Перегрузка для MultipartFile — используется в PersonController.
     */
    public String savePhoto(Person person, InputStream in, String extension) throws IOException {
        ensureFacesDirectoryExists();

        String baseName = generatePhotoFilename(person);
        String filenameWithoutExt = baseName;
        Path filePath = Paths.get(facesDirectory).resolve(baseName + extension);

        int counter = 1;
        while (Files.exists(filePath)) {
            filenameWithoutExt = baseName + "_" + counter;
            filePath = Paths.get(facesDirectory).resolve(filenameWithoutExt + extension);
            counter++;
        }

        Files.copy(in, filePath);
        return filenameWithoutExt;
    }

    /**
     * Генерирует транслитерированное базовое имя файла из ФИО персоны.
     * Формат: Фамилия_Имя_Отчество (если есть отчество) или Имя_Фамилия.
     */
    public String generatePhotoFilename(Person person) {
        String personName;

        if (person.getMiddleName() != null && !person.getMiddleName().trim().isEmpty()) {
            personName = person.getFirstName();
            if (person.getLastName() != null && !person.getLastName().trim().isEmpty()) {
                personName = person.getLastName() + "_" + personName;
            }
            personName += "_" + person.getMiddleName();
        } else {
            personName = person.getFirstName();
            if (person.getLastName() != null && !person.getLastName().trim().isEmpty()) {
                personName += "_" + person.getLastName();
            }
        }

        return TransliterationUtil.cleanFilename(personName);
    }

    /**
     * Возвращает расширение файла (с точкой) по MIME-типу.
     * По умолчанию возвращает ".jpg".
     */
    public String extensionFromMime(String contentType) {
        if (contentType == null) return ".jpg";
        return switch (contentType.toLowerCase()) {
            case "image/png"  -> ".png";
            case "image/gif"  -> ".gif";
            case "image/jpeg" -> ".jpeg";
            default           -> ".jpg";
        };
    }

    private void ensureFacesDirectoryExists() throws IOException {
        Path facesPath = Paths.get(facesDirectory);
        if (!Files.exists(facesPath)) {
            Files.createDirectories(facesPath);
        }
    }
}
