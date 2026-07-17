package com.facepanel.util;

/**
 * Автоопределение пола по отчеству.
 * Казахские: -ұлы/-улы = мужчина, -қызы/-кызы = женщина.
 * Русские: -вич/-ич = мужчина, -вна/-чна = женщина.
 * Если окончание не распознано — null (пол не определён).
 */
public final class GenderUtil {

    public static final String MALE = "MALE";
    public static final String FEMALE = "FEMALE";

    // Женские окончания проверяем первыми (ни одно из них не пересекается с мужскими)
    private static final String[] FEMALE_ENDINGS = {"қызы", "кызы", "гызы", "kyzy", "вна", "чна", "vna"};
    private static final String[] MALE_ENDINGS = {"ұлы", "улы", "оглы", "uly", "вич", "ич", "vich"};

    private GenderUtil() {
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
     * Определение по всем трём полям ФИО — на случай, если отчество
     * попало в поле имени или фамилии (встречается в данных).
     */
    public static String detect(String lastName, String firstName, String middleName) {
        String gender = detectByMiddleName(middleName);
        if (gender == null) gender = detectByMiddleName(firstName);
        if (gender == null) gender = detectByMiddleName(lastName);
        return gender;
    }
}
