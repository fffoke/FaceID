package com.facepanel.dto;

import lombok.*;
import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class AttendanceDTO {
    private Long id;
    private Long personId;
    private String personName;
    private LocalDateTime timestamp;
    private String eventType;
}
