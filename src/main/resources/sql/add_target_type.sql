-- Добавление поля target_type для указания аудитории мероприятия (ALL / Student / Employee)
ALTER TABLE session
    ADD COLUMN IF NOT EXISTS target_type VARCHAR(255);
