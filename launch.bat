@echo off
title Instagram Follower Tracker
cls
echo ===================================================
echo     Demarrage du Tracker Instagram...
echo ===================================================
echo.
python run.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Une erreur est survenue lors du lancement.
    pause
)
