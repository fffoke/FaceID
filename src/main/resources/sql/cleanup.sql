-- Скрипт для очистки таблиц (если нужно)
-- ВНИМАНИЕ: Это удалит все данные!

-- Удаляем внешние ключи
ALTER TABLE attendance DROP CONSTRAINT IF EXISTS FK_attendance_person;
ALTER TABLE attendance DROP CONSTRAINT IF EXISTS FK_attendance_session;

-- Удаляем таблицы в обратном порядке
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS session;
DROP TABLE IF EXISTS person;

-- Удаляем старую таблицу person если она существует с неправильной структурой
DROP TABLE IF EXISTS person CASCADE;
