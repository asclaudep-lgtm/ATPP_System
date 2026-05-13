@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ============================================================
rem  ATPP_System v7 — оффлайн-установка для Windows
rem ------------------------------------------------------------
rem  Требуется: Python 3.12 (x64), установленный с галкой
rem             "Add Python to PATH" во время установки.
rem  Что делает скрипт:
rem   1. Проверяет наличие Python 3.12.
rem   2. Создаёт виртуальное окружение .venv рядом со скриптом.
rem   3. Устанавливает все зависимости ИЗ ЛОКАЛЬНОЙ ПАПКИ wheels/
rem      (интернет не нужен).
rem   4. Сообщает, что можно запускать run_app.bat.
rem ============================================================

echo.
echo ============================================================
echo   ATPP_System v7  -  Windows offline installer
echo ============================================================
echo.

rem --- Проверка Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH.
    echo.
    echo Установите Python 3.12 ^(64-bit^) с https://www.python.org/downloads/
    echo Во время установки обязательно поставьте галку "Add Python to PATH".
    echo Затем запустите этот скрипт ещё раз.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Найдена Python !PYVER!

echo !PYVER! | findstr /b "3.12" >nul
if errorlevel 1 (
    echo [ВНИМАНИЕ] Скрипт собран для Python 3.12, у вас !PYVER!.
    echo Колёса в папке wheels\ могут не подойти.
    echo Если установка прервётся, поставьте Python 3.12 рядом и запустите снова.
    echo.
    set /p CONTINUE="Продолжить? (y/n): "
    if /i not "!CONTINUE!"=="y" exit /b 1
)

rem --- Создание .venv ---
if exist .venv (
    echo [INFO] Папка .venv уже существует. Удаляю и пересоздаю.
    rmdir /s /q .venv
)

echo [STEP] Создаю виртуальное окружение .venv ...
python -m venv .venv
if errorlevel 1 (
    echo [ОШИБКА] Не удалось создать .venv.
    pause
    exit /b 1
)

rem --- Активация и установка ---
echo [STEP] Активирую .venv и обновляю pip ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet --no-warn-script-location

echo [STEP] Устанавливаю зависимости из локальной папки wheels\ ...
pip install --no-index --find-links=wheels -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Установка зависимостей провалилась. См. сообщения выше.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   УСПЕХ! Установка завершена.
echo ------------------------------------------------------------
echo   Для запуска приложения дважды кликните: run_app.bat
echo   Или вручную:
echo     call .venv\Scripts\activate
echo     python launcher.py
echo ============================================================
echo.
pause
