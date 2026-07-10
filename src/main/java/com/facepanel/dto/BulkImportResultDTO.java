package com.facepanel.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BulkImportResultDTO {

    private int totalFiles;
    private int successCount;
    private int skippedCount;
    private int errorCount;
    private List<ImportEntryLog> log;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ImportEntryLog {
        /** Путь внутри архива, например "ИКТ-22-1/Иванов Иван Иванович.jpg" */
        private String filename;
        private Status status;
        /** Причина пропуска или ошибки (null при SUCCESS) */
        private String reason;
    }

    public enum Status {
        SUCCESS,
        SKIPPED,
        ERROR
    }
}
