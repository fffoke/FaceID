-- Создание таблиц в правильном порядке
-- Сначала создаем таблицы без внешних ключей

-- Таблица person
CREATE TABLE IF NOT EXISTS person (
    id BIGSERIAL PRIMARY KEY,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    position VARCHAR(255),
    person_group VARCHAR(255),
    photo_filename VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица session
CREATE TABLE IF NOT EXISTS session (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    active BOOLEAN DEFAULT FALSE
);

-- Таблица attendance (с внешними ключами)
CREATE TABLE IF NOT EXISTS attendance (
    id BIGSERIAL PRIMARY KEY,
    person_id BIGINT,
    session_id BIGINT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    camera_name VARCHAR(255),
    event_type VARCHAR(50)
);

-- Добавляем внешние ключи после создания всех таблиц
ALTER TABLE attendance 
ADD CONSTRAINT FK_attendance_person 
FOREIGN KEY (person_id) REFERENCES person(id);

ALTER TABLE attendance 
ADD CONSTRAINT FK_attendance_session 
FOREIGN KEY (session_id) REFERENCES session(id);

-- Создаем индексы для улучшения производительности
CREATE INDEX IF NOT EXISTS idx_attendance_person_id ON attendance(person_id);
CREATE INDEX IF NOT EXISTS idx_attendance_session_id ON attendance(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance(timestamp);
CREATE INDEX IF NOT EXISTS idx_session_active ON session(active);
