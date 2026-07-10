# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FacePanel — a face recognition and attendance tracking system. Two-component architecture:
- **Spring Boot backend** (this repo's main code) — web UI, REST API, WebSocket notifications, PostgreSQL persistence
- **Python OpenCV client** (`OpenCVRework/`) — captures video from IP cameras, recognizes faces, sends detections to the backend

## Build & Run Commands

```bash
# Build (Java 21 required)
./mvnw package                    # produces JAR in target/
./mvnw spring-boot:run            # run in dev mode

# Run from JAR
java -jar target/operator-panel-0.0.1-SNAPSHOT.jar

# Tests
./mvnw test

# Python face recognition (requires venv in OpenCVRework/venv)
cd OpenCVRework
python face.py --camera-url <RTSP_URL> --camera-name KPP1
python face.py --camera-index 0 --camera-name KPP1   # webcam test
```

There is also a PyQt6 launcher (`launcher.py`) that manages all processes via GUI.

## Tech Stack

- **Java 21**, Spring Boot 3.5.6, Maven (wrapper included)
- **PostgreSQL** (db: `app_db`, configured in `application.properties`)
- **JPA/Hibernate** with `ddl-auto=update` — schema auto-managed
- **Thymeleaf** for server-side HTML rendering (templates in `src/main/resources/templates/`)
- **WebSocket + STOMP** (SockJS) for real-time UI updates
- **Lombok** for boilerplate reduction (`@Data`, `@Builder`, etc.)
- **Python 3** with OpenCV, requests, face_recognition for the camera client

## Architecture

### Package structure: `com.facepanel`

- `model/` — JPA entities: **Person**, **Session**, **Attendance**
- `repository/` — Spring Data JPA interfaces
- `service/` — Business logic: PersonService, SessionService, AttendanceService
- `controller/` — MVC controllers (Thymeleaf pages) + REST controllers
- `dto/` — RecognitionRequest (inbound from Python), AttendanceDTO (outbound)
- `config/` — WebSocketConfig (STOMP on `/ws`, topics: `/topic/attendance`, `/topic/persons`)
- `util/` — TransliterationUtil (Cyrillic→Latin for photo filenames)

### Key data flow

1. Python client POSTs face detection to `POST /api/v1/recognitions` with photo filename + confidence
2. `AttendanceService.registerDetection()` matches filename to Person's `photoFilename`, creates Attendance record linked to active Session
3. WebSocket broadcast on `/topic/attendance` pushes real-time update to all connected browsers
4. If no active session exists, recognition still records but against no session

### REST API (`/api/v1`)

- `GET /active-session` — current session info
- `POST /recognitions` — receive face detection (used by Python client)

### Web pages

- `/` — Dashboard with live attendance logs
- `/session` — Session management (start/stop events)
- `/session/history/{id}` — Past session details
- `/persons` — Person CRUD with photo management
- `/attendance` — Attendance history with date filtering
- `/statistics` — Analytics with CSV export
- `/kpp1`, `/kpp2` — Checkpoint camera display pages

### Photo management

- Photos stored in `faces/` directory (configurable via `app.faces.directory`)
- Filenames are transliterated from Cyrillic names (e.g., "Иван Петров" → `ivan_petrov.jpg`)
- Person lookup during recognition matches by `photoFilename` field (case-insensitive, extension-stripped)
- Upload endpoint: `POST /upload/photo`, retrieval: `GET /upload/faces/{filename}`

## Database

PostgreSQL with three tables: `person`, `session`, `attendance`. Relationships:
- Person → Attendance (one-to-many)
- Session → Attendance (one-to-many)
- Attendance stores: person_id, session_id, timestamp, cameraName, eventType (DETECTED/ENTER/LEAVE)

## Important Notes

- The project UI and comments are primarily in **Russian**
- `server.address=0.0.0.0` — binds to all interfaces by default
- `spring.jpa.open-in-view=false` — no lazy loading outside transactions
- WebSocket config allows all origins (`setAllowedOriginPatterns("*")`)
- Multi-camera support: each camera process sends its `cameraName` (KPP1, KPP2) with recognitions
