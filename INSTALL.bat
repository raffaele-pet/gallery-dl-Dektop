@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title gallery-dl Desktop - Installation and updates
color 0F

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_GDL=%VENV_DIR%\Scripts\gallery-dl.exe"
set "VENV_YTDLP=%VENV_DIR%\Scripts\yt-dlp.exe"
set "CHECK_ONLY=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo ================================================================
echo                    gallery-dl Desktop INSTALLER
echo ================================================================
echo Project folder: %PROJECT_DIR%
echo.

if not exist "%PROJECT_DIR%app.py" (
    call :fatal "app.py is missing."
    exit /b 1
)
if not exist "%PROJECT_DIR%RUN.vbs" (
    call :fatal "RUN.vbs is missing."
    exit /b 1
)
if not exist "%PROJECT_DIR%maintenance.py" (
    call :fatal "maintenance.py is missing. Update all project files."
    exit /b 1
)
if not exist "%PROJECT_DIR%network.py" (
    call :fatal "network.py is missing. Update all project files."
    exit /b 1
)
if not exist "%PROJECT_DIR%app_update.py" (
    call :fatal "app_update.py is missing. Update all project files."
    exit /b 1
)
if not exist "%PROJECT_DIR%assets\gallery-dl-logo.png" (
    call :fatal "The application logo is missing."
    exit /b 1
)
if not exist "%PROJECT_DIR%assets\gallery-dl-icon.png" (
    call :fatal "The application PNG icon is missing."
    exit /b 1
)
if not exist "%PROJECT_DIR%assets\gallery-dl-icon.ico" (
    call :fatal "The application Windows icon is missing."
    exit /b 1
)

call :find_python
call :find_ffmpeg

if "%CHECK_ONLY%"=="1" (
    echo [CHECK] Python: !PYTHON_STATUS!
    set "EXTRA_OK=0"
    set "BROWSER_OK=0"
    set "GDL_OK=0"
    if exist "%VENV_GDL%" (
        for /f "delims=" %%V in ('"%VENV_GDL%" --version 2^>nul') do set "GDL_VERSION=%%V"
        "%VENV_PY%" -c "import sys; sys.path.insert(0, sys.argv[1]); import maintenance; raise SystemExit(0 if maintenance.engine_ready() else 1)" "%PROJECT_DIR%." >nul 2>&1 && set "GDL_OK=1"
        if "!GDL_OK!"=="1" (echo [OK] gallery-dl !GDL_VERSION! with current Instagram support) else (echo [OUTDATED] gallery-dl !GDL_VERSION!; run INSTALL.bat to update Instagram support)
        "%VENV_PY%" -c "import bs4, PIL, playwright, requests" >nul 2>&1 && set "EXTRA_OK=1"
    ) else (
        echo [MISSING] Local gallery-dl environment
    )
    if "!EXTRA_OK!"=="1" (echo [OK] Web page components) else (echo [MISSING] Web page components)
    if "!EXTRA_OK!"=="1" (
        "%VENV_PY%" -c "import engine; raise SystemExit(0 if engine.installed_browser()[0] else 1)" >nul 2>&1
        if not errorlevel 1 set "BROWSER_OK=1"
    )
    if "!BROWSER_OK!"=="1" (echo [OK] Chromium-based browser found on the system) else (echo [MISSING] Google Chrome, Microsoft Edge o Brave)
    if "!FFMPEG_OK!"=="1" (echo [OK] FFmpeg) else (echo [MISSING] FFmpeg)
    if defined PYTHON_LAUNCHER if "!GDL_OK!"=="1" if "!EXTRA_OK!"=="1" if "!BROWSER_OK!"=="1" if "!FFMPEG_OK!"=="1" exit /b 0
    exit /b 2
)

where winget.exe >nul 2>&1
if errorlevel 1 (
    call :fatal "WinGet is not available. Install App Installer from the Microsoft Store and try again."
    exit /b 1
)

echo [1/6] Checking Python...
if not defined PYTHON_LAUNCHER (
    echo [INSTALL] Python 3.12
    winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        call :fatal "Python installation failed."
        exit /b 1
    )
    set "PYTHON_LAUNCHER=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if not exist "!PYTHON_LAUNCHER!" call :find_python
)
if not defined PYTHON_LAUNCHER (
    call :fatal "Python was not found after installation."
    exit /b 1
)
echo [OK] !PYTHON_STATUS!

echo.
echo [2/6] Preparing the isolated environment...
if not exist "%VENV_PY%" (
    "!PYTHON_LAUNCHER!" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        call :fatal "Could not create the virtual environment."
        exit /b 1
    )
) else (
    echo [OK] The virtual environment already exists.
)
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel requests truststore
if errorlevel 1 (
    call :fatal "Could not update the Python packaging tools."
    exit /b 1
)

echo.
echo [3/6] Installing or updating gallery-dl and integrations...
set "GDL_BEFORE=not installed"
set "YTDLP_BEFORE=not installed"
if exist "%VENV_GDL%" for /f "delims=" %%V in ('"%VENV_GDL%" --version 2^>nul') do set "GDL_BEFORE=%%V"
if exist "%VENV_YTDLP%" for /f "delims=" %%V in ('"%VENV_YTDLP%" --version 2^>nul') do set "YTDLP_BEFORE=%%V"
echo Installed gallery-dl version: !GDL_BEFORE!
echo Checking current official releases and verifying the installed engines...
"%VENV_PY%" -u "%PROJECT_DIR%maintenance.py" --dependencies-only
if errorlevel 1 (
    call :fatal "Python package installation failed."
    exit /b 1
)
set "GDL_AFTER=not available"
set "YTDLP_AFTER=not available"
for /f "delims=" %%V in ('"%VENV_GDL%" --version 2^>nul') do set "GDL_AFTER=%%V"
for /f "delims=" %%V in ('"%VENV_YTDLP%" --version 2^>nul') do set "YTDLP_AFTER=%%V"
if "!GDL_BEFORE!"=="!GDL_AFTER!" (echo [OK] gallery-dl !GDL_AFTER! is already up to date.) else (echo [UPDATED] gallery-dl !GDL_BEFORE! --^> !GDL_AFTER!)
if "!YTDLP_BEFORE!"=="!YTDLP_AFTER!" (echo [OK] yt-dlp !YTDLP_AFTER! is already up to date.) else (echo [UPDATED] yt-dlp !YTDLP_BEFORE! --^> !YTDLP_AFTER!)

echo.
echo Checking the installed browser...
"%VENV_PY%" -c "import engine; path,name,_=engine.installed_browser(); print('[OK] '+name if path else '[MISSING] Google Chrome, Microsoft Edge o Brave'); raise SystemExit(0 if path else 1)"
if errorlevel 1 (
    call :fatal "Install Google Chrome, Microsoft Edge, or Brave and try again."
    exit /b 1
)
if exist "%PROJECT_DIR%.browser-binaries" (
    echo [CLEANUP] Removing the old bundled Chromium browser...
    rmdir /s /q "%PROJECT_DIR%.browser-binaries"
)
echo [4/6] Checking FFmpeg for HLS/DASH videos and Pixiv Ugoira...
call :find_ffmpeg
if "!FFMPEG_OK!"=="0" (
    winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [INFO] The main package is unavailable. Trying the yt-dlp FFmpeg package...
        winget install --id yt-dlp.FFmpeg --exact --accept-package-agreements --accept-source-agreements
    )
    call :find_ffmpeg
    if "!FFMPEG_OK!"=="0" echo [WARNING] FFmpeg is not on the current PATH. Restart Windows if necessary.
) else (
    echo [OK] FFmpeg is already available.
    winget upgrade --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements >nul 2>&1
    winget upgrade --id yt-dlp.FFmpeg --exact --accept-package-agreements --accept-source-agreements >nul 2>&1
)

echo.
echo [5/6] Final verification...
if not exist "%VENV_GDL%" (
    call :fatal "gallery-dl.exe was not created."
    exit /b 1
)
if not exist "%VENV_YTDLP%" (
    call :fatal "yt-dlp.exe was not created."
    exit /b 1
)
"%VENV_GDL%" --version
if errorlevel 1 (
    call :fatal "gallery-dl verification failed."
    exit /b 1
)
"%VENV_YTDLP%" --version
if errorlevel 1 (
    call :fatal "yt-dlp verification failed."
    exit /b 1
)
"%VENV_PY%" -m py_compile "%PROJECT_DIR%app.py" "%PROJECT_DIR%engine.py" "%PROJECT_DIR%gallery_worker.py" "%PROJECT_DIR%maintenance.py" "%PROJECT_DIR%network.py" "%PROJECT_DIR%app_update.py"
if errorlevel 1 (
    call :fatal "app.py contains a syntax error."
    exit /b 1
)

echo.
echo [6/6] Creating the desktop shortcut...
set "GDL_PROJECT=%PROJECT_DIR%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$project=$env:GDL_PROJECT.TrimEnd('\'); $desktop=[Environment]::GetFolderPath('Desktop'); $shell=New-Object -ComObject WScript.Shell; $link=Join-Path $desktop 'gallery-dl Desktop.lnk'; $old=Join-Path $desktop 'Gallery-DL.lnk'; if((Test-Path -LiteralPath $old) -and -not (Test-Path -LiteralPath $link)){ $previous=$shell.CreateShortcut($old); if($previous.WorkingDirectory.TrimEnd('\') -ieq $project.TrimEnd('\')){Move-Item -LiteralPath $old -Destination $link} }; $shortcut=$shell.CreateShortcut($link); $shortcut.TargetPath=(Join-Path $env:SystemRoot 'System32\wscript.exe'); $shortcut.Arguments=([char]34)+(Join-Path $project 'RUN.vbs')+([char]34); $shortcut.WorkingDirectory=$project; $shortcut.Description='Launch gallery-dl Desktop'; $shortcut.IconLocation=(Join-Path $project 'assets\gallery-dl-icon.ico')+',0'; $shortcut.Save()"
if errorlevel 1 (
    echo [WARNING] Could not create the shortcut. RUN.vbs is still available.
) else (
    echo [OK] gallery-dl Desktop shortcut created on the desktop.
)

echo.
echo ================================================================
echo Installation and updates completed.
echo Launch the app using RUN.vbs or the gallery-dl Desktop shortcut.
echo ================================================================
pause
exit /b 0

:find_python
set "PYTHON_LAUNCHER="
set "PYTHON_STATUS=not available"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_LAUNCHER=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else (
    for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHON_LAUNCHER set "PYTHON_LAUNCHER=%%P"
)
if defined PYTHON_LAUNCHER for /f "delims=" %%V in ('"!PYTHON_LAUNCHER!" --version 2^>^&1') do set "PYTHON_STATUS=%%V"
exit /b 0

:find_ffmpeg
set "FFMPEG_OK=0"
where ffmpeg.exe >nul 2>&1 && set "FFMPEG_OK=1"
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe" set "FFMPEG_OK=1"
exit /b 0

:fatal
echo.
echo ================================================================
echo [ERROR] %~1
echo ================================================================
if "%CHECK_ONLY%"=="0" pause
exit /b 1
