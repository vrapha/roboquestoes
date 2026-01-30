@echo off
setlocal

REM Build do executável com tela (usuário leigo)

REM 1) Garanta que o Playwright use a pasta local do projeto
set PLAYWRIGHT_BROWSERS_PATH=ms-playwright

REM 2) Gera executável em modo onedir (mais estável)
REM 2) Gera executável usando o arquivo de especificação (RoboQuestoes.spec)
pyinstaller --noconfirm --clean RoboQuestoes.spec

echo.
echo Pronto! Veja: dist\RoboQuestoes\RoboQuestoes.exe
pause

endlocal