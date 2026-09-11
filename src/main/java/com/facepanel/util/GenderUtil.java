package com.facepanel.util;

import java.util.Set;

/**
 * Автоопределение пола по отчеству.
 * Казахские: -ұлы/-улы = мужчина, -қызы/-кызы = женщина.
 * Русские: -вич/-ич = мужчина, -вна/-чна = женщина.
 * Без отчества — по фамилии (-ова/-ов), затем по имени (только женские).
 * Если ничего не распознано — null (пол не определён).
 */
public final class GenderUtil {

    public static final String MALE = "MALE";
    public static final String FEMALE = "FEMALE";

    // Женские окончания проверяем первыми (ни одно из них не пересекается с мужскими)
    private static final String[] FEMALE_ENDINGS = {"қызы", "кызы", "гызы", "kyzy", "вна", "чна", "vna"};
    private static final String[] MALE_ENDINGS = {"ұлы", "улы", "оглы", "uly", "вич", "ич", "vich"};

    private static final String[] FEMALE_SURNAME_ENDINGS = {"ова", "ева", "ёва", "ина", "ына", "ская", "цкая", "ova", "eva", "ina"};
    private static final String[] MALE_SURNAME_ENDINGS = {"ов", "ев", "ёв", "ин", "ын", "ский", "цкий", "ov", "ev"};

    // Женские имена без типичного окончания -а/-я (казахские и др.)
    private static final Set<String> FEMALE_FIRST_NAMES = Set.of(
            "айгерим", "аяулым", "анель", "дильназ", "сезім", "сезим", "әсем", "асем",
            "жібек", "жибек", "назерке", "аружан", "нурай", "нұрай", "інжу", "инжу");
    private static final String[] FEMALE_FIRST_NAME_ENDINGS = {"гүл", "гуль", "гул"};
    // Мужские имена на -а/-я — исключения из правила «-а/-я = женщина»
    private static final Set<String> MALE_FIRST_NAMES_A = Set.of(
            "никита", "илья", "кузьма", "фома", "гриша", "дима", "миша", "лёша", "леша",
            "паша", "ваня", "коля", "толя", "вова", "федя", "мұса", "муса", "иса", "ыса", "мирза");
    // Имена, по которым пол не понять
    private static final Set<String> UNISEX_FIRST_NAMES = Set.of(
            "саша", "женя", "валя", "сағыныш", "сагыныш", "нұрбота", "нурбота");

    private GenderUtil() {
    }

    /**
     * Последний вариант — по имени: -а/-я и известные женские имена = женщина.
     * Мужчину по имени не определяем (слишком много вариантов) — только женщину.
     */
    public static String detectByFirstName(String firstName) {
        if (firstName == null) return null;
        String fn = firstName.trim().toLowerCase();
        if (fn.length() < 3 || UNISEX_FIRST_NAMES.contains(fn) || MALE_FIRST_NAMES_A.contains(fn)) return null;

        if (FEMALE_FIRST_NAMES.contains(fn)) return FEMALE;
        for (String ending : FEMALE_FIRST_NAME_ENDINGS) {
            if (fn.endsWith(ending)) return FEMALE;
        }
        if (fn.endsWith("а") || fn.endsWith("я")) return FEMALE;
        return null;
    }

    public static String detectByMiddleName(String middleName) {
        if (middleName == null) return null;
        String mn = middleName.trim().toLowerCase();
        if (mn.isEmpty()) return null;

        for (String ending : FEMALE_ENDINGS) {
            if (mn.endsWith(ending)) return FEMALE;
        }
        for (String ending : MALE_ENDINGS) {
            if (mn.endsWith(ending)) return MALE;
        }
        return null;
    }

    /**
     * Запасной вариант, когда отчества нет (импорт «Фамилия Имя»):
     * русские/казахские фамилии -ова/-ева/-ина = женщина, -ов/-ев/-ин = мужчина.
     */
    public static String detectBySurname(String lastName) {
        if (lastName == null) return null;
        String ln = lastName.trim().toLowerCase();
        if (ln.isEmpty()) return null;

        for (String ending : FEMALE_SURNAME_ENDINGS) {
            if (ln.endsWith(ending)) return FEMALE;
        }
        for (String ending : MALE_SURNAME_ENDINGS) {
            if (ln.endsWith(ending)) return MALE;
        }
        return null;
    }

    /**
     * Определение по всем трём полям ФИО — на случай, если отчество
     * попало в поле имени или фамилии (встречается в данных).
     * Если отчество не найдено нигде — пробуем по фамилии.
     */
    public static String detect(String lastName, String firstName, String middleName) {
        String gender = detectByMiddleName(middleName);
        if (gender == null) gender = detectByMiddleName(firstName);
        if (gender == null) gender = detectByMiddleName(lastName);
        if (gender == null) gender = detectBySurname(lastName);
        if (gender == null) gender = detectByFirstName(firstName);
        return gender;
    }
}
