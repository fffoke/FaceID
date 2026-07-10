package com.facepanel.service;

import com.facepanel.dto.BulkImportResultDTO;
import com.facepanel.dto.BulkImportResultDTO.ImportEntryLog;
import com.facepanel.dto.BulkImportResultDTO.Status;
import com.facepanel.model.Person;
import com.facepanel.repository.PersonRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

@Service
@RequiredArgsConstructor
public class BulkImportService {

    private final PersonRepository personRepository;
    private final PhotoService photoService;

    private static final Set<String> SUPPORTED_EXT = Set.of(".jpg", ".jpeg", ".png", ".gif");
    /** Максимальный размер одной записи в архиве — защита от zip-bomb */
    private static final int MAX_ENTRY_BYTES = 15 * 1024 * 1024;

    /**
     * Обрабатывает ZIP-архив и создаёт персоны.
     * Стримит записи архива без буферизации всего файла в память.
     *
     * @param zipIn    поток ZIP-архива
     * @param position категория ("Student" или "Employee")
     * @return итоги импорта + детальный лог
     */
    public BulkImportResultDTO processZip(InputStream zipIn, String position) throws IOException {
        List<ImportEntryLog> log = new ArrayList<>();
        int total = 0;
        int success = 0;
        int skipped = 0;
        int errors = 0;

        // CP866 — кодировка имён файлов в ZIP-архивах Windows.
        // Если в записи выставлен флаг UTF-8 (современные архиваторы),
        // Java игнорирует charset и читает UTF-8 автоматически.
        try (ZipInputStream zis = new ZipInputStream(zipIn, Charset.forName("CP866"))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                String entryName = entry.getName();

                if (shouldSkipSilently(entryName)) {
                    zis.closeEntry();
                    continue;
                }

                total++;

                String ext = extractExtension(entryName);
                if (ext == null) {
                    log.add(errorLog(entryName, "Неподдерживаемый тип файла"));
                    errors++;
                    zis.closeEntry();
                    continue;
                }

                String baseName = extractBaseName(entryName);
                String[] fio = parseFio(baseName);
                if (fio == null) {
                    log.add(errorLog(entryName, "Неверный формат имени (ожидается «Фамилия Имя» или «Фамилия Имя Отчество»)"));
                    errors++;
                    zis.closeEntry();
                    continue;
                }

                // fio = [lastName, firstName, middleName], middleName может быть ""
                String lastName   = fio[0];
                String firstName  = fio[1];
                String middleName = fio[2];
                String group      = extractGroupName(entryName);

                // Проверка дублей с учётом необязательного отчества
                boolean duplicate = middleName.isEmpty()
                        ? personRepository.findByFirstNameAndLastName(firstName, lastName).isPresent()
                        : personRepository.findByFirstNameAndLastNameAndMiddleName(firstName, lastName, middleName).isPresent();
                if (duplicate) {
                    log.add(skippedLog(entryName, "Персона уже существует"));
                    skipped++;
                    zis.closeEntry();
                    continue;
                }

                byte[] bytes;
                try {
                    bytes = readEntryBytes(zis);
                } catch (IOException e) {
                    log.add(errorLog(entryName, "Файл слишком большой (более 15 МБ)"));
                    errors++;
                    zis.closeEntry();
                    continue;
                }

                Person person = Person.builder()
                        .lastName(lastName)
                        .firstName(firstName)
                        .middleName(middleName.isEmpty() ? null : middleName)
                        .position(position)
                        .group(group)
                        .build();

                try {
                    String filename = photoService.savePhoto(person, bytes, ext);
                    person.setPhotoFilename(filename);
                    personRepository.save(person);
                    log.add(successLog(entryName));
                    success++;
                } catch (IOException e) {
                    log.add(errorLog(entryName, "Ошибка сохранения файла: " + e.getMessage()));
                    errors++;
                } catch (Exception e) {
                    log.add(errorLog(entryName, "Ошибка базы данных: " + e.getMessage()));
                    errors++;
                }

                zis.closeEntry();
            }
        }

        return BulkImportResultDTO.builder()
                .totalFiles(total)
                .successCount(success)
                .skippedCount(skipped)
                .errorCount(errors)
                .log(log)
                .build();
    }

    /**
     * Возвращает true для записей, которые нужно молча пропустить:
     * директории, служебные файлы macOS, path traversal.
     */
    private boolean shouldSkipSilently(String name) {
        if (name == null) return true;
        if (name.contains("..")) return true;
        if (name.endsWith("/")) return true;
        if (name.startsWith("__MACOSX/")) return true;
        String lower = name.toLowerCase();
        if (lower.endsWith(".ds_store")) return true;
        return false;
    }

    /**
     * Возвращает расширение (строчные, с точкой) если оно поддерживается, иначе null.
     */
    private String extractExtension(String entryName) {
        int dot = entryName.lastIndexOf('.');
        if (dot < 0) return null;
        String ext = entryName.substring(dot).toLowerCase();
        return SUPPORTED_EXT.contains(ext) ? ext : null;
    }

    /**
     * Извлекает имя файла без расширения и без пути.
     * Например "faces_data/ИКТ-22-1/Иванов Иван Иванович.jpg" → "Иванов Иван Иванович"
     */
    private String extractBaseName(String entryName) {
        int slash = entryName.lastIndexOf('/');
        String filename = (slash >= 0) ? entryName.substring(slash + 1) : entryName;
        int dot = filename.lastIndexOf('.');
        return (dot > 0) ? filename.substring(0, dot) : filename;
    }

    /**
     * Парсит ФИО из имени файла.
     * Принимает 2 части (Фамилия Имя) или 3 части (Фамилия Имя Отчество).
     *
     * @return [lastName, firstName, middleName] где middleName может быть "" — или null если формат неверный
     */
    private String[] parseFio(String baseName) {
        if (baseName == null || baseName.isBlank()) return null;
        String[] parts = baseName.trim().split("\\s+");
        if (parts.length == 2) {
            return new String[]{parts[0], parts[1], ""};
        } else if (parts.length == 3) {
            return parts; // [Фамилия, Имя, Отчество]
        }
        return null; // 1 слово или > 3 слов
    }

    /**
     * Извлекает имя группы/кафедры — предпоследний сегмент пути.
     * Например "faces_data/ИКТ-22-1/Иванов Иван Иванович.jpg" → "ИКТ-22-1"
     * Если структура папок отсутствует — возвращает "Без группы".
     */
    private String extractGroupName(String entryPath) {
        String[] segments = entryPath.split("/");
        // segments[last] — имя файла, segments[last-1] — папка группы
        // нужно минимум 2 сегмента (папка + файл)
        if (segments.length >= 2) {
            String folder = segments[segments.length - 2];
            if (!folder.isBlank()) return folder;
        }
        return "Без группы";
    }

    /**
     * Читает байты текущей записи ZIP без закрытия потока.
     * Ограничивает размер записи MAX_ENTRY_BYTES.
     */
    private byte[] readEntryBytes(ZipInputStream zis) throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] chunk = new byte[8192];
        int totalRead = 0;
        int len;
        while ((len = zis.read(chunk)) != -1) {
            totalRead += len;
            if (totalRead > MAX_ENTRY_BYTES) {
                throw new IOException("Превышен допустимый размер файла");
            }
            buffer.write(chunk, 0, len);
        }
        return buffer.toByteArray();
    }

    private ImportEntryLog successLog(String filename) {
        return ImportEntryLog.builder().filename(filename).status(Status.SUCCESS).build();
    }

    private ImportEntryLog skippedLog(String filename, String reason) {
        return ImportEntryLog.builder().filename(filename).status(Status.SKIPPED).reason(reason).build();
    }

    private ImportEntryLog errorLog(String filename, String reason) {
        return ImportEntryLog.builder().filename(filename).status(Status.ERROR).reason(reason).build();
    }
}
