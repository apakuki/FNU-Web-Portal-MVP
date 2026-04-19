@echo off
setlocal

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker Desktop first.
    exit /b 1
)

echo Starting FNU Web Portal...
docker compose -f "%~dp0..\docker\docker-compose.yml" --project-directory "%~dp0.." up --build -d

echo.
echo FNU Web Portal is starting up.
echo   Portal:  http://localhost
echo   API:     http://localhost/api/health
echo   API docs: http://localhost:8000/api/docs
echo.
echo Run scripts\stop.bat to stop all services.
