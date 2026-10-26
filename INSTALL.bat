@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Gallery-DL - Installazione e aggiornamento
color 0F

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_GDL=%VENV_DIR%\Scripts\gallery-dl.exe"
set "VENV_YTDLP=%VENV_DIR%\Scripts\yt-dlp.exe"
set "CHECK_ONLY=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo ================================================================
echo                    GALLERY-DL INSTALLER
echo ================================================================
echo Cartella progetto: %PROJECT_DIR%
echo.

if not exist "%PROJECT_DIR%app.py" (
    call :fatal "Manca app.py."
    exit /b 1
)
if not exist "%PROJECT_DIR%RUN.vbs" (
    call :fatal "Manca RUN.vbs."
    exit /b 1
)
if not exist "%PROJECT_DIR%maintenance.py" (
    call :fatal "Manca maintenance.py. Aggiorna tutti i file del progetto."
    exit /b 1
)
if not exist "%PROJECT_DIR%network.py" (
    call :fatal "Manca network.py. Aggiorna tutti i file del progetto."
    exit /b 1
)
if not exist "%PROJECT_DIR%app_update.py" (
    call :fatal "Manca app_update.py. Aggiorna tutti i file del progetto."
    exit /b 1
)
if not exist "%PROJECT_DIR%assets\gallery-dl-logo.png" (
    call :fatal "Manca il logo dell'applicazione."
    exit /b 1
)
if not exist "%PROJECT_DIR%assets\gallery-dl-icon.png" (
    call :fatal "Manca l'icona PNG dell'applicazione."
    exit /b 1
)
if not exist "%PROJECT_DIR%assets\gallery-dl-icon.ico" (
    call :fatal "Manca l'icona Windows dell'applicazione."
    exit /b 1
)

call :find_python
call :find_ffmpeg

if "%CHECK_ONLY%"=="1" (
    echo [CONTROLLO] Python: !PYTHON_STATUS!
    set "EXTRA_OK=0"
    set "BROWSER_OK=0"
    set "GDL_OK=0"
    if exist "%VENV_GDL%" (
        for /f "delims=" %%V in ('"%VENV_GDL%" --version 2^>nul') do set "GDL_VERSION=%%V"
        "%VENV_PY%" -c "import sys; sys.path.insert(0, sys.argv[1]); import maintenance; raise SystemExit(0 if maintenance.engine_ready() else 1)" "%PROJECT_DIR%." >nul 2>&1 && set "GDL_OK=1"
        if "!GDL_OK!"=="1" (echo [OK] gallery-dl !GDL_VERSION! con correzione Instagram) else (echo [OBSOLETO] gallery-dl !GDL_VERSION!; esegui INSTALL.bat per la correzione Instagram)
        "%VENV_PY%" -c "import bs4, PIL, playwright, requests" >nul 2>&1 && set "EXTRA_OK=1"
    ) else (
        echo [MANCANTE] Ambiente locale gallery-dl
    )
    if "!EXTRA_OK!"=="1" (echo [OK] Componenti per pagine web) else (echo [MANCANTE] Componenti per pagine web)
    if "!EXTRA_OK!"=="1" (
        "%VENV_PY%" -c "import engine; raise SystemExit(0 if engine.installed_browser()[0] else 1)" >nul 2>&1
        if not errorlevel 1 set "BROWSER_OK=1"
    )
    if "!BROWSER_OK!"=="1" (echo [OK] Browser Chromium già installato nel sistema) else (echo [MANCANTE] Google Chrome, Microsoft Edge o Brave)
    if "!FFMPEG_OK!"=="1" (echo [OK] FFmpeg) else (echo [MANCANTE] FFmpeg)
    if defined PYTHON_LAUNCHER if "!GDL_OK!"=="1" if "!EXTRA_OK!"=="1" if "!BROWSER_OK!"=="1" if "!FFMPEG_OK!"=="1" exit /b 0
    exit /b 2
)

where winget.exe >nul 2>&1
if errorlevel 1 (
    call :fatal "WinGet non è disponibile. Installa 'App Installer' dal Microsoft Store e riprova."
    exit /b 1
)

echo [1/6] Controllo di Python...
if not defined PYTHON_LAUNCHER (
    echo [INSTALLA] Python 3.12
    winget install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        call :fatal "Installazione di Python non riuscita."
        exit /b 1
    )
    set "PYTHON_LAUNCHER=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if not exist "!PYTHON_LAUNCHER!" call :find_python
)
if not defined PYTHON_LAUNCHER (
    call :fatal "Python non è stato trovato dopo l'installazione."
    exit /b 1
)
echo [OK] !PYTHON_STATUS!

echo.
echo [2/6] Preparazione dell'ambiente isolato...
if not exist "%VENV_PY%" (
    "!PYTHON_LAUNCHER!" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        call :fatal "Creazione dell'ambiente virtuale non riuscita."
        exit /b 1
    )
) else (
    echo [OK] Ambiente virtuale già presente.
)
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel requests truststore
if errorlevel 1 (
    call :fatal "Aggiornamento degli strumenti Python non riuscito."
    exit /b 1
)

echo.
echo [3/6] Installazione o aggiornamento di gallery-dl e integrazioni...
set "GDL_BEFORE=non installato"
set "YTDLP_BEFORE=non installato"
if exist "%VENV_GDL%" for /f "delims=" %%V in ('"%VENV_GDL%" --version 2^>nul') do set "GDL_BEFORE=%%V"
if exist "%VENV_YTDLP%" for /f "delims=" %%V in ('"%VENV_YTDLP%" --version 2^>nul') do set "YTDLP_BEFORE=%%V"
echo Versione gallery-dl presente: !GDL_BEFORE!
echo Controllo le release ufficiali attuali e verifico i motori installati...
"%VENV_PY%" -u "%PROJECT_DIR%maintenance.py" --dependencies-only
if errorlevel 1 (
    call :fatal "Installazione dei pacchetti Python non riuscita."
    exit /b 1
)
set "GDL_AFTER=non disponibile"
set "YTDLP_AFTER=non disponibile"
for /f "delims=" %%V in ('"%VENV_GDL%" --version 2^>nul') do set "GDL_AFTER=%%V"
for /f "delims=" %%V in ('"%VENV_YTDLP%" --version 2^>nul') do set "YTDLP_AFTER=%%V"
if "!GDL_BEFORE!"=="!GDL_AFTER!" (echo [OK] gallery-dl !GDL_AFTER! è già aggiornato.) else (echo [AGGIORNATO] gallery-dl !GDL_BEFORE! --^> !GDL_AFTER!)
if "!YTDLP_BEFORE!"=="!YTDLP_AFTER!" (echo [OK] yt-dlp !YTDLP_AFTER! è già aggiornato.) else (echo [AGGIORNATO] yt-dlp !YTDLP_BEFORE! --^> !YTDLP_AFTER!)

echo.
echo Controllo del browser già installato...
"%VENV_PY%" -c "import engine; path,name,_=engine.installed_browser(); print('[OK] '+name if path else '[MANCANTE] Google Chrome, Microsoft Edge o Brave'); raise SystemExit(0 if path else 1)"
if errorlevel 1 (
    call :fatal "Installa Google Chrome, Microsoft Edge o Brave e riprova."
    exit /b 1
)
if exist "%PROJECT_DIR%.browser-binaries" (
    echo [PULIZIA] Rimuovo il vecchio Chromium incluso, non più necessario...
    rmdir /s /q "%PROJECT_DIR%.browser-binaries"
)
echo [4/6] Controllo di FFmpeg per video HLS/DASH e Pixiv Ugoira...
call :find_ffmpeg
if "!FFMPEG_OK!"=="0" (
    winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [INFO] Pacchetto principale non disponibile, provo il pacchetto FFmpeg per yt-dlp...
        winget install --id yt-dlp.FFmpeg --exact --accept-package-agreements --accept-source-agreements
    )
    call :find_ffmpeg
    if "!FFMPEG_OK!"=="0" echo [AVVISO] FFmpeg non è visibile nel PATH corrente. Potrebbe diventarlo dopo il riavvio.
) else (
    echo [OK] FFmpeg già disponibile.
    winget upgrade --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements >nul 2>&1
    winget upgrade --id yt-dlp.FFmpeg --exact --accept-package-agreements --accept-source-agreements >nul 2>&1
)

echo.
echo [5/6] Verifica finale...
if not exist "%VENV_GDL%" (
    call :fatal "gallery-dl.exe non è stato creato."
    exit /b 1
)
if not exist "%VENV_YTDLP%" (
    call :fatal "yt-dlp.exe non è stato creato."
    exit /b 1
)
"%VENV_GDL%" --version
if errorlevel 1 (
    call :fatal "gallery-dl non supera la verifica."
    exit /b 1
)
"%VENV_YTDLP%" --version
if errorlevel 1 (
    call :fatal "yt-dlp non supera la verifica."
    exit /b 1
)
"%VENV_PY%" -m py_compile "%PROJECT_DIR%app.py" "%PROJECT_DIR%engine.py" "%PROJECT_DIR%gallery_worker.py" "%PROJECT_DIR%maintenance.py" "%PROJECT_DIR%network.py" "%PROJECT_DIR%app_update.py"
if errorlevel 1 (
    call :fatal "app.py contiene un errore di sintassi."
    exit /b 1
)

echo.
echo [6/6] Creazione del collegamento sul Desktop...
set "GDL_PROJECT=%PROJECT_DIR%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$project=$env:GDL_PROJECT.TrimEnd('\'); $desktop=[Environment]::GetFolderPath('Desktop'); $shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Gallery-DL.lnk')); $shortcut.TargetPath=(Join-Path $env:SystemRoot 'System32\wscript.exe'); $shortcut.Arguments='""'+(Join-Path $project 'RUN.vbs')+'""'; $shortcut.WorkingDirectory=$project; $shortcut.Description='Gallery-DL - Image and gallery downloader'; $shortcut.IconLocation=(Join-Path $project 'assets\gallery-dl-icon.ico')+',0'; $shortcut.Save()"
if errorlevel 1 (
    echo [AVVISO] Non è stato possibile creare il collegamento. RUN.vbs rimane utilizzabile.
) else (
    echo [OK] Collegamento Gallery-DL creato sul Desktop.
)

echo.
echo ================================================================
echo Installazione e aggiornamento completati.
echo Avvia l'app con RUN.vbs o con il collegamento Gallery-DL.
echo ================================================================
pause
exit /b 0

:find_python
set "PYTHON_LAUNCHER="
set "PYTHON_STATUS=non disponibile"
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
echo [ERRORE] %~1
echo ================================================================
if "%CHECK_ONLY%"=="0" pause
exit /b 1
