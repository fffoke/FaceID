@echo off
chcp 65001 >nul
title FacePanel Launcher

REM Переходим в директорию скрипта
cd /d "%~dp0"

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден!
    echo Убедитесь, что Python установлен и добавлен в PATH.
    pause
    exit /b 1
)

REM Запускаем лаунчер
python launcher.py

if errorlevel 1 (
    echo.
    echo Ошибка при запуске лаунчера!
    pause
)
