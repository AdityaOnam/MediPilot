@echo off
echo [MediPilot] Compiling white paper...
pdflatex -synctex=1 -interaction=nonstopmode main.tex
pdflatex -synctex=1 -interaction=nonstopmode main.tex
echo.
echo Done! Open main.pdf to view the white paper.
pause
