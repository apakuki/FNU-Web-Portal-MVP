@echo off
setlocal

echo Stopping FNU Web Portal...
docker compose -f "%~dp0..\docker\docker-compose.yml" --project-directory "%~dp0.." down

echo All services stopped.
