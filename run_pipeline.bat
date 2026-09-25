@echo off
REM Wrapper para correr pipeline.py desde el Programador de tareas de Windows.
REM Ajusta la primera línea si tu carpeta del proyecto no es esta.

cd /d C:\Escuela\CV\AutoScramping

if not exist logs mkdir logs

echo. >> logs\pipeline_log.txt
echo ==== %DATE% %TIME% ==== >> logs\pipeline_log.txt
python pipeline.py >> logs\pipeline_log.txt 2>&1
