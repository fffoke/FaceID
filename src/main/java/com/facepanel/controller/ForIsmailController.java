package com.facepanel.controller;

import com.facepanel.model.Person;
import com.facepanel.repository.PersonRepository;
import com.facepanel.service.PersonService;
import com.facepanel.util.GenderUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Скрытая страница — навигация только по прямому URL /for_ismail.
 * Ссылок на неё в меню нет.
 */
@Controller
@RequiredArgsConstructor
@RequestMapping("/for_ismail")
public class ForIsmailController {

    private final PersonRepository personRepository;
    private final PersonService personService;

    private static final Map<String, String> POSITION_BY_TYPE = Map.of(
            "student", "Student",
            "employee", "Employee"
    );

    @GetMapping
    public String deck(@RequestParam(defaultValue = "all") String type, Model model) {
        String position = POSITION_BY_TYPE.get(type);
        if (position == null) {
            type = "all";
        }

        List<Person> all = personRepository.findByGenderAndHiddenForIsmalFalse(GenderUtil.FEMALE)
                .stream()
                .filter(p -> p.getPhotoFilename() != null && !p.getPhotoFilename().isEmpty())
                .collect(Collectors.toList());

        List<Person> girls = all.stream()
                .filter(p -> position == null || position.equals(p.getPosition()))
                .collect(Collectors.toList());
        Collections.shuffle(girls);

        model.addAttribute("type", type);
        model.addAttribute("countAll", all.size());
        model.addAttribute("countStudent", all.stream().filter(p -> "Student".equals(p.getPosition())).count());
        model.addAttribute("countEmployee", all.stream().filter(p -> "Employee".equals(p.getPosition())).count());

        List<Map<String, Object>> cards = girls.stream()
                .map(p -> Map.<String, Object>of(
                        "id", p.getId(),
                        "name", fullName(p),
                        "group", p.getGroup() != null ? p.getGroup() : "",
                        "photoUrl", photoUrl(p)
                ))
                .collect(Collectors.toList());

        model.addAttribute("cards", cards);
        return "for_ismail";
    }

    @GetMapping("/{id}")
    public String personDetails(@PathVariable Long id,
                                @RequestParam(defaultValue = "all") String type,
                                Model model) {
        Person person = personRepository.findById(id)
                .filter(p -> GenderUtil.FEMALE.equals(p.getGender()))
                .orElse(null);
        if (person == null) {
            return "redirect:/for_ismail";
        }
        model.addAttribute("type", POSITION_BY_TYPE.containsKey(type) ? type : "all");
        model.addAttribute("person", person);
        model.addAttribute("photoUrl", photoUrl(person));
        return "for_ismail_person";
    }

    @PostMapping("/hide/{id}")
    @ResponseBody
    public ResponseEntity<?> hide(@PathVariable Long id) {
        return personRepository.findById(id)
                .map(p -> {
                    p.setHiddenForIsmal(true);
                    personRepository.save(p);
                    return ResponseEntity.ok().build();
                })
                .orElse(ResponseEntity.notFound().build());
    }

    private String fullName(Person p) {
        return ((p.getFirstName() != null ? p.getFirstName() : "") + " "
                + (p.getLastName() != null ? p.getLastName() : "")).trim();
    }

    private String photoUrl(Person p) {
        if (p.getPhotoFilename() == null || p.getPhotoFilename().isEmpty()) {
            return "";
        }
        return "/upload/faces/" + p.getPhotoFilename() + personService.getPhotoExtension(p.getPhotoFilename());
    }
}
