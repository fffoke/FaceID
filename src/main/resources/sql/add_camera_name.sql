-- Добавление поля camera_name для хранения идентификатора камеры
ALTER TABLE attendance
    ADD COLUMN IF NOT EXISTS camera_name VARCHAR(255);






