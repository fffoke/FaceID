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
python face_2.py --camera-name kpp1 --no-window       # slug from the camera registry
python face_2.py --camera-index 0 --camera-name kpp1  # webcam test
```

`--camera-name` takes the camera's **slug** from the registry (same as the systemd
unit `face@kpp1`). RTSP URL, ESP turnstile URL and MJPEG stream port all come from
the server, so they are edited on `/cameras` rather than in files.

`launcher.py` (PyQt6 GUI) is legacy — it still points at `face_kpp1.py` / `face_kpp2.py`,
which no longer exist. Production runs under systemd (see `deploy/`).

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

- `model/` — JPA entities: **Person**, **Session**, **Attendance**, **Camera**
- `repository/` — Spring Data JPA interfaces
- `service/` — Business logic: PersonService, SessionService, AttendanceService, CameraService
- `controller/` — MVC controllers (Thymeleaf pages) + REST controllers
- `dto/` — RecognitionRequest (inbound from Python), AttendanceDTO (outbound)
- `config/` — WebSocketConfig (STOMP on `/ws`, topics: `/topic/attendance`, `/topic/persons`)
- `util/` — TransliterationUtil (Cyrillic→Latin for photo filenames)

### Key data flow

1. Python client POSTs face detection to `POST /api/v1/recognitions` with photo filename + confidence
2. `AttendanceService.registerDetection()` matches filename to Person's `photoFilename`, creates Attendance record linked to active Session
3. WebSocket broadcast on `/topic/attendance` pushes real-time update to all connected browsers
4. If no active session exists, recognition still records but against no session

### Camera registry

Cameras are rows in the `camera` table, managed at `/cameras` (full CRUD).

- `name` — display name, **may be Cyrillic**; this is what the Python client reports
  as `cameraName`, so it is what lands in attendance records
- `slug` — latin identifier derived from `name` via `TransliterationUtil.cleanFilename`.
  Used where Cyrillic breaks: URLs (`/kpp/{slug}`) and systemd units (`face@{slug}`)
- `streamPort` — assigned automatically starting at 8090; two processes cannot share a port
- `updatedAt` — bumped on every edit; the supervisor restarts the camera process when it changes

`Camera.resolveStreamUrl()` builds `http://127.0.0.1:<streamPort>/stream` unless an
explicit `streamUrl` is set (only needed when the Python client runs on another machine).

### Process lifecycle

The panel never spawns processes. `OpenCVRework/supervisor.py` (unit `face-supervisor`)
polls `/api/v1/cameras` every 30s and reconciles: new camera → `systemctl enable --now
face@<slug>`, deleted → `disable --now`, edited (`updatedAt` changed) → `restart`.
Units live in `deploy/systemd/`.

### REST API (`/api/v1`)

- `GET /active-session` — current session info
- `POST /recognitions` — receive face detection (used by Python client)
- `GET /cameras` — camera registry (used by the Python client and the supervisor)
- `GET /cameras/{key}` — one camera by slug or name

### Web pages

- `/` — Dashboard with live attendance logs
- `/session` — Session management (start/stop events)
- `/session/history/{id}` — Past session details
- `/persons` — Person CRUD with photo management
- `/attendance` — Attendance history with date filtering
- `/statistics` — Analytics with CSV export
- `/cameras` — Camera registry CRUD
- `/kpp` — Checkpoint index; `/kpp/{slug}` — single camera screen
- `/kpp/stream/{slug}` — MJPEG proxied from the Python client, so only port 8080
  needs to be reachable from tablets

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
- Multi-camera support: each camera process sends its `cameraName` with recognitions
- Python client is split into `OpenCVRework/facecore/`: `config`, `models`, `faces_db`,
  `capture`, `stream`, `esp`, `backend`, `pipeline`. `face_2.py` is just the entry point
- RTSP capture uses FFmpeg low-delay options (`probesize`/`analyzeduration`/`nobuffer`).
  Do not restore `CAP_PROP_BUFFERSIZE` — the FFMPEG backend silently ignores it
- ESP turnstile calls retry within a 4s budget behind a lock; HTTP 429 means the relay
  did **not** fire and must be retried
