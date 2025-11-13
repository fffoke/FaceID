package com.facepanel.util;

import java.util.HashMap;
import java.util.Map;

public class TransliterationUtil {
    
    private static final Map<Character, String> CYRILLIC_TO_LATIN = new HashMap<>();
    
    static {
        // Строчные буквы
        CYRILLIC_TO_LATIN.put('а', "a");
        CYRILLIC_TO_LATIN.put('б', "b");
        CYRILLIC_TO_LATIN.put('в', "v");
        CYRILLIC_TO_LATIN.put('г', "g");
        CYRILLIC_TO_LATIN.put('д', "d");
        CYRILLIC_TO_LATIN.put('е', "e");
        CYRILLIC_TO_LATIN.put('ё', "yo");
        CYRILLIC_TO_LATIN.put('ж', "zh");
        CYRILLIC_TO_LATIN.put('з', "z");
        CYRILLIC_TO_LATIN.put('и', "i");
        CYRILLIC_TO_LATIN.put('й', "y");
        CYRILLIC_TO_LATIN.put('к', "k");
        CYRILLIC_TO_LATIN.put('л', "l");
        CYRILLIC_TO_LATIN.put('м', "m");
        CYRILLIC_TO_LATIN.put('н', "n");
        CYRILLIC_TO_LATIN.put('о', "o");
        CYRILLIC_TO_LATIN.put('п', "p");
        CYRILLIC_TO_LATIN.put('р', "r");
        CYRILLIC_TO_LATIN.put('с', "s");
        CYRILLIC_TO_LATIN.put('т', "t");
        CYRILLIC_TO_LATIN.put('у', "u");
        CYRILLIC_TO_LATIN.put('ф', "f");
        CYRILLIC_TO_LATIN.put('х', "h");
        CYRILLIC_TO_LATIN.put('ц', "ts");
        CYRILLIC_TO_LATIN.put('ч', "ch");
        CYRILLIC_TO_LATIN.put('ш', "sh");
        CYRILLIC_TO_LATIN.put('щ', "sch");
        CYRILLIC_TO_LATIN.put('ъ', "");
        CYRILLIC_TO_LATIN.put('ы', "y");
        CYRILLIC_TO_LATIN.put('ь', "");
        CYRILLIC_TO_LATIN.put('э', "e");
        CYRILLIC_TO_LATIN.put('ю', "yu");
        CYRILLIC_TO_LATIN.put('я', "ya");
        
        // Заглавные буквы
        CYRILLIC_TO_LATIN.put('А', "A");
        CYRILLIC_TO_LATIN.put('Б', "B");
        CYRILLIC_TO_LATIN.put('В', "V");
        CYRILLIC_TO_LATIN.put('Г', "G");
        CYRILLIC_TO_LATIN.put('Д', "D");
        CYRILLIC_TO_LATIN.put('Е', "E");
        CYRILLIC_TO_LATIN.put('Ё', "Yo");
        CYRILLIC_TO_LATIN.put('Ж', "Zh");
        CYRILLIC_TO_LATIN.put('З', "Z");
        CYRILLIC_TO_LATIN.put('И', "I");
        CYRILLIC_TO_LATIN.put('Й', "Y");
        CYRILLIC_TO_LATIN.put('К', "K");
        CYRILLIC_TO_LATIN.put('Л', "L");
        CYRILLIC_TO_LATIN.put('М', "M");
        CYRILLIC_TO_LATIN.put('Н', "N");
        CYRILLIC_TO_LATIN.put('О', "O");
        CYRILLIC_TO_LATIN.put('П', "P");
        CYRILLIC_TO_LATIN.put('Р', "R");
        CYRILLIC_TO_LATIN.put('С', "S");
        CYRILLIC_TO_LATIN.put('Т', "T");
        CYRILLIC_TO_LATIN.put('У', "U");
        CYRILLIC_TO_LATIN.put('Ф', "F");
        CYRILLIC_TO_LATIN.put('Х', "H");
        CYRILLIC_TO_LATIN.put('Ц', "Ts");
        CYRILLIC_TO_LATIN.put('Ч', "Ch");
        CYRILLIC_TO_LATIN.put('Ш', "Sh");
        CYRILLIC_TO_LATIN.put('Щ', "Sch");
        CYRILLIC_TO_LATIN.put('Ъ', "");
        CYRILLIC_TO_LATIN.put('Ы', "Y");
        CYRILLIC_TO_LATIN.put('Ь', "");
        CYRILLIC_TO_LATIN.put('Э', "E");
        CYRILLIC_TO_LATIN.put('Ю', "Yu");
        CYRILLIC_TO_LATIN.put('Я', "Ya");
    }
    
    /**
     * Транслитерирует кириллический текст в латиницу
     */
    public static String transliterate(String text) {
        if (text == null || text.isEmpty()) {
            return text;
        }
        
        StringBuilder result = new StringBuilder();
        for (char c : text.toCharArray()) {
            if (CYRILLIC_TO_LATIN.containsKey(c)) {
                result.append(CYRILLIC_TO_LATIN.get(c));
            } else {
                result.append(c);
            }
        }
        
        return result.toString();
    }
    
    /**
     * Очищает имя файла от недопустимых символов и транслитерирует
     */
    public static String cleanFilename(String text) {
        if (text == null || text.isEmpty()) {
            return "unknown";
        }
        
        // Транслитерация
        String transliterated = transliterate(text);
        
        // Удаление недопустимых символов, оставляем только буквы, цифры, точки, дефисы и подчеркивания
        String cleaned = transliterated.replaceAll("[^a-zA-Z0-9._-]", "_");
        
        // Удаление множественных подчеркиваний
        cleaned = cleaned.replaceAll("_{2,}", "_");
        
        // Удаление подчеркиваний в начале и конце
        cleaned = cleaned.replaceAll("^_+|_+$", "");
        
        // Если после очистки строка пустая, возвращаем "unknown"
        if (cleaned.isEmpty()) {
            return "unknown";
        }
        
        return cleaned.toLowerCase();
    }
}
