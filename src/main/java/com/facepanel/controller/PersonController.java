package com.facepanel.controller;

import com.facepanel.model.Person;
import com.facepanel.service.PersonService;
import com.facepanel.util.TransliterationUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Controller
@RequiredArgsConstructor
@RequestMapping("/persons")
public class PersonController {

    private final PersonService personService;
    
    @Value("${app.faces.directory:faces}")
    private String facesDirectory;

    @GetMapping
    public String list(Model model, 
                      @RequestParam(required = false) String group,
                      @RequestParam(required = false) String position,
                      @RequestParam(required = false) String dateFrom,
                      @RequestParam(required = false) String dateTo) {
        
        // Получаем всех персон с фильтрацией
        List<Person> allPersons = personService.getAll();
        
        // Применяем фильтры
        List<Person> filteredPersons = personService.getFilteredPersons(allPersons, group, position, dateFrom, dateTo);
        
        // Группируем персон
        Map<String, List<Person>> groupedPersons = personService.groupPersonsByGroup(filteredPersons);
        
        // Получаем статистику
        Map<String, Object> stats = personService.getPersonStats(allPersons);
        
        model.addAttribute("persons", filteredPersons);
        model.addAttribute("groupedPersons", groupedPersons);
        model.addAttribute("stats", stats);
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
            
            // Обрабатываем загрузку нового файла
            if (photoFile != null && !photoFile.isEmpty()) {
                String filename = savePhotoFile(photoFile, person);
                person.setPhotoFilename(filename);
                
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
                    } else {
                        // Имя файла не изменилось, сохраняем старое
                        person.setPhotoFilename(existingPerson.getPhotoFilename());
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
        
        // Создаем папку faces, если её нет
        Path facesPath = Paths.get(facesDirectory);
        if (!Files.exists(facesPath)) {
            Files.createDirectories(facesPath);
        }
        
        // Генерируем имя файла на основе имени персоны
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
        
        // Создаем имя файла на основе имени персоны с транслитерацией
        String personName = person.getFirstName();
        if (person.getLastName() != null && !person.getLastName().trim().isEmpty()) {
            personName += "_" + person.getLastName();
        }
        
        // Транслитерируем и очищаем имя от недопустимых символов
        personName = TransliterationUtil.cleanFilename(personName);
        
        // Добавляем UUID для уникальности, если файл с таким именем уже существует
        String filename = personName + extension;
        String filenameWithoutExt = personName;
        
        // Проверяем, существует ли файл с таким именем
        Path filePath = facesPath.resolve(filename);
        int counter = 1;
        while (Files.exists(filePath)) {
            filename = personName + "_" + counter + extension;
            filenameWithoutExt = personName + "_" + counter;
            filePath = facesPath.resolve(filename);
            counter++;
        }
        
        // Сохраняем файл
        Files.copy(file.getInputStream(), filePath);
        
        return filenameWithoutExt;
    }
    
    private String generatePhotoFilename(Person person) {
        // Создаем имя файла на основе имени персоны с транслитерацией
        String personName;
        
        // Если есть отчество - используем формат "Фамилия_Имя_Отчество"
        if (person.getMiddleName() != null && !person.getMiddleName().trim().isEmpty()) {
            personName = person.getFirstName();
            if (person.getLastName() != null && !person.getLastName().trim().isEmpty()) {
                personName = person.getLastName() + "_" + personName;
            }
            personName += "_" + person.getMiddleName();
        } else {
            // Если нет отчества - используем формат "Имя_Фамилия"
            personName = person.getFirstName();
            if (person.getLastName() != null && !person.getLastName().trim().isEmpty()) {
                personName += "_" + person.getLastName();
            }
        }
        
        // Транслитерируем и очищаем имя от недопустимых символов
        personName = TransliterationUtil.cleanFilename(personName);
        
        return personName;
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
        // Получаем персону перед удалением, чтобы удалить файл фотографии
        Person person = personService.findById(id).orElse(null);
        if (person != null && person.getPhotoFilename() != null && !person.getPhotoFilename().isEmpty()) {
            deleteOldPhotoFile(person.getPhotoFilename());
        }
        
        personService.delete(id);
        return "redirect:/persons";
    }
}
