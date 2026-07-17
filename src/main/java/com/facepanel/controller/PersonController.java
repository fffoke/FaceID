package com.facepanel.controller;

import com.facepanel.model.Person;
import com.facepanel.service.PersonService;
import com.facepanel.service.PhotoService;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import org.springframework.http.ResponseEntity;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

@Controller
@RequiredArgsConstructor
@RequestMapping("/persons")
public class PersonController {

    private final PersonService personService;
    private final PhotoService photoService;

    @Value("${app.faces.directory:faces}")
    private String facesDirectory;

    @GetMapping
    public String list(Model model,
                      @RequestParam(required = false) String search,
                      @RequestParam(required = false) String group,
                      @RequestParam(required = false) String position,
                      @RequestParam(required = false) String dateFrom,
                      @RequestParam(required = false) String dateTo) {

        // Получаем всех персон с фильтрацией
        List<Person> allPersons = personService.getAll();

        // Применяем фильтры
        List<Person> filteredPersons = personService.getFilteredPersons(allPersons, search, group, position, dateFrom, dateTo);
        
        // Группируем персон
        Map<String, List<Person>> groupedPersons = personService.groupPersonsByGroup(filteredPersons);
        
        // Получаем статистику
        Map<String, Object> stats = personService.getPersonStats(allPersons);
        
        model.addAttribute("persons", filteredPersons);
        model.addAttribute("groupedPersons", groupedPersons);
        model.addAttribute("stats", stats);
        model.addAttribute("selectedSearch", search);
        model.addAttribute("selectedGroup", group);
        model.addAttribute("selectedPosition", position);
        model.addAttribute("selectedDateFrom", dateFrom);
        model.addAttribute("selectedDateTo", dateTo);
        model.addAttribute("personService", personService); // Добавляем сервис для доступа к методам
        
        return "persons";
    }

    @GetMapping("/new")
    public String newForm(Model model) {
        model.addAttribute("person", new Person());
        return "person_form";
    }

    @GetMapping("/edit/{id}")
    public String editForm(@PathVariable Long id, Model model) {
        Person person = personService.findById(id)
                .orElseThrow(() -> new RuntimeException("Персона не найдена"));
        model.addAttribute("person", person);
        model.addAttribute("personService", personService);
        return "person_form";
    }

    @PostMapping("/save")
    public String save(Person person, @RequestParam(value = "photoFile", required = false) MultipartFile photoFile) {
        try {
            // Обрабатываем загрузку файла
            if (photoFile != null && !photoFile.isEmpty()) {
                String filename = savePhotoFile(photoFile, person);
                person.setPhotoFilename(filename);
            }
            
            personService.save(person);
            return "redirect:/persons";
        } catch (IllegalArgumentException e) {
            // Ошибка валидации файла
            return "redirect:/persons/new?error=invalid_file";
        } catch (IOException e) {
            // Ошибка сохранения файла
            return "redirect:/persons/new?error=save_failed";
        } catch (Exception e) {
            // Общая ошибка
            return "redirect:/persons/new?error=unknown_error";
        }
    }

    @PostMapping("/update")
    public String update(Person person, @RequestParam(value = "photoFile", required = false) MultipartFile photoFile) {
        try {
            // Получаем существующую персону из базы данных
            Person existingPerson = personService.findById(person.getId())
                    .orElseThrow(() -> new RuntimeException("Персона не найдена"));

            // Служебные скрытые поля — не приходят из формы, сохраняем из БД
            if (person.getGender() == null || person.getGender().isBlank()) {
                person.setGender(existingPerson.getGender());
            }
            person.setHiddenForIsmal(existingPerson.isHiddenForIsmal());

            // Обрабатываем загрузку нового файла
            if (photoFile != null && !photoFile.isEmpty()) {
                String filename = savePhotoFile(photoFile, person);
                person.setPhotoFilename(filename);
                // Сбрасываем эмбеддинг — Python пересчитает автоматически
                person.setFaceEmbedding(null);

                // Удаляем старый файл, если он существует
                if (existingPerson.getPhotoFilename() != null && !existingPerson.getPhotoFilename().isEmpty()) {
                    deleteOldPhotoFile(existingPerson.getPhotoFilename());
                }
            } else {
                // Если новый файл не загружен, проверяем нужно ли переименовать существующий файл
                if (existingPerson.getPhotoFilename() != null && !existingPerson.getPhotoFilename().isEmpty()) {
                    String newFilename = generatePhotoFilename(person);
                    if (!newFilename.equals(existingPerson.getPhotoFilename())) {
                        // Переименовываем файл
                        renamePhotoFile(existingPerson.getPhotoFilename(), newFilename);
                        person.setPhotoFilename(newFilename);
                        // Сбрасываем эмбеддинг — Python пересчитает с новым именем
                        person.setFaceEmbedding(null);
                    } else {
                        // Имя файла не изменилось, сохраняем старое
                        person.setPhotoFilename(existingPerson.getPhotoFilename());
                        person.setFaceEmbedding(existingPerson.getFaceEmbedding());
                    }
                }
            }
            
            personService.save(person);
            return "redirect:/persons";
        } catch (IllegalArgumentException e) {
            // Ошибка валидации файла
            return "redirect:/persons/edit/" + person.getId() + "?error=invalid_file";
        } catch (IOException e) {
            // Ошибка сохранения файла
            return "redirect:/persons/edit/" + person.getId() + "?error=save_failed";
        } catch (Exception e) {
            // Общая ошибка
            return "redirect:/persons/edit/" + person.getId() + "?error=unknown_error";
        }
    }
    
    private String savePhotoFile(MultipartFile file, Person person) throws IOException {
        // Проверяем тип файла
        String contentType = file.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            throw new IllegalArgumentException("Выберите изображение (JPG, PNG, GIF)");
        }

        // Проверяем размер файла (максимум 5MB)
        if (file.getSize() > 5 * 1024 * 1024) {
            throw new IllegalArgumentException("Размер файла не должен превышать 5MB");
        }

        String extension = photoService.extensionFromMime(contentType);
        return photoService.savePhoto(person, file.getInputStream(), extension);
    }

    private String generatePhotoFilename(Person person) {
        return photoService.generatePhotoFilename(person);
    }
    
    private void renamePhotoFile(String oldFilename, String newFilename) throws IOException {
        if (oldFilename == null || oldFilename.isEmpty() || newFilename == null || newFilename.isEmpty()) {
            return;
        }
        
        Path facesPath = Paths.get(facesDirectory);
        
        // Ищем старый файл с любым расширением
        Path oldFilePath = null;
        String[] extensions = {".jpg", ".jpeg", ".png", ".gif"};
        
        for (String ext : extensions) {
            Path testPath = facesPath.resolve(oldFilename + ext);
            if (Files.exists(testPath)) {
                oldFilePath = testPath;
                break;
            }
        }
        
        if (oldFilePath != null) {
            // Определяем расширение старого файла
            String extension = getFileExtension(oldFilePath.getFileName().toString());
            
            // Создаем путь для нового файла с тем же расширением
            Path newFilePath = facesPath.resolve(newFilename + extension);
            
            // Если новый файл уже существует, удаляем его
            if (Files.exists(newFilePath)) {
                Files.delete(newFilePath);
            }
            
            // Переименовываем файл
            Files.move(oldFilePath, newFilePath);
        }
    }
    
    private String getFileExtension(String filename) {
        int lastDotIndex = filename.lastIndexOf('.');
        if (lastDotIndex > 0 && lastDotIndex < filename.length() - 1) {
            return filename.substring(lastDotIndex);
        }
        return ".jpg"; // По умолчанию
    }
    
    private void deleteOldPhotoFile(String filename) {
        if (filename == null || filename.isEmpty()) {
            return;
        }
        
        try {
            Path facesPath = Paths.get(facesDirectory);
            
            // Ищем файл с любым расширением
            String[] extensions = {".jpg", ".jpeg", ".png", ".gif"};
            
            for (String ext : extensions) {
                Path filePath = facesPath.resolve(filename + ext);
                if (Files.exists(filePath)) {
                    Files.delete(filePath);
                    break; // Удаляем только первый найденный файл
                }
            }
        } catch (IOException e) {
            // Логируем ошибку, но не прерываем выполнение
            System.err.println("Ошибка при удалении старого файла: " + e.getMessage());
        }
    }

    @GetMapping("/delete/{id}")
    public String delete(@PathVariable Long id) {
        Person person = personService.findById(id).orElse(null);
        if (person != null && person.getPhotoFilename() != null && !person.getPhotoFilename().isEmpty()) {
            deleteOldPhotoFile(person.getPhotoFilename());
        }
        personService.delete(id);
        return "redirect:/persons";
    }

    @PostMapping("/delete-bulk")
    @ResponseBody
    public ResponseEntity<?> deleteBulk(@RequestBody List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return ResponseEntity.badRequest().body("Список ID пуст");
        }
        for (Long id : ids) {
            Person person = personService.findById(id).orElse(null);
            if (person != null) {
                if (person.getPhotoFilename() != null && !person.getPhotoFilename().isEmpty()) {
                    deleteOldPhotoFile(person.getPhotoFilename());
                }
                personService.delete(id);
            }
        }
        return ResponseEntity.ok().build();
    }
}
