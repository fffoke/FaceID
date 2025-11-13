-- Проверка существования базы данных
SELECT current_database();

-- Проверка существующих таблиц
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';

-- Создание базы данных если не существует (выполнить в postgres)
-- CREATE DATABASE attendance_db;
