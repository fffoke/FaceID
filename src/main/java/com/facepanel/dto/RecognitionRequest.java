package com.facepanel.dto;

import lombok.Data;

@Data
public class RecognitionRequest {
    // или name (имя из базы), или externalId (идентификатор)
    private String name;
    private String externalId;
    private Double confidence;
    private String timestamp; // optional ISO string
    private Long sessionId; // optional
    private String cameraName; // optional идентификатор камеры (например KPP1)
}
