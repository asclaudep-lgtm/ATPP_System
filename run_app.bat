@echo off
chcp 65001 >nul

rem ============================================================
rem  ATPP_System — запуск приложения
rem  Требуется, чтобы install_windows.bat уже отработал.
rem ============================================================

if not exist .venv\Scripts\python.exe (
    echo [ОШИБКА] Виртуальное окружение .venv не найдено.
    echo Сначала запустите install_windows.bat.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python launcher.py
if errorlevel 1 (
    echo.
    echo Приложение завершилось с ошибкой. См. сообщения выше.
    pause
)
