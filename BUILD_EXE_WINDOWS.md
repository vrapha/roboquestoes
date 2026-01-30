# Gerar o executável (Windows)

Este projeto foi adaptado para virar um **executável com tela** (usuário leigo):

1) Seleciona o PDF
2) Clica em **Iniciar (Extrair + Buscar)**
3) Vê os códigos na tela
4) Clica em **Enviar para planilha**

---

## 1) Preparar ambiente

Abra o **CMD** ou **PowerShell** na pasta do projeto e rode:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> Se der erro no `fitz`/PyMuPDF, confirme que você está com a `.venv` ativa.

---

## 2) Instalar o navegador do Playwright dentro da pasta do projeto

Isso é importante para o executável funcionar em outras máquinas:

```bat
set PLAYWRIGHT_BROWSERS_PATH=ms-playwright
python -m playwright install chromium
```

Vai aparecer uma pasta `ms-playwright/`.

---

## 3) Gerar executável (recomendado: onedir)

```bat
set PLAYWRIGHT_BROWSERS_PATH=ms-playwright
pyinstaller --noconfirm --clean --onedir --name RoboQuestoes \
  --add-data "scripts;scripts" \
  --add-data "debug;debug" \
  --add-data "inputs;inputs" \
  --add-data "outputs;outputs" \
  --add-data "ms-playwright;ms-playwright" \
  gui_app.py
```

O executável fica em:

`dist\RoboQuestoes\RoboQuestoes.exe`

---

## 4) Entregar para usuários

Envie a pasta inteira:

`dist\RoboQuestoes\`

O usuário só precisa:
1) extrair o zip
2) dar duplo clique no `RoboQuestoes.exe`

---

## 5) Se pedir login

Na tela do app, use:
- **Fazer login no site…** (salva `debug/storage_state.json`)
- **Fazer login no Google…** (salva `debug/google_storage_state.json`)

Depois disso, o uso normal é só selecionar PDF -> iniciar -> enviar.
