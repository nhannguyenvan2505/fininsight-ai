@echo off
cd /d "%~dp0"
call .venv\Scripts\streamlit.exe run ui/app.py
