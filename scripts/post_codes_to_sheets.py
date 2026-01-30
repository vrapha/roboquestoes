import csv
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Carrega segredos (Sheet ID) de arquivo local para não subir no GitHub
def load_secrets():
    candidates = ["secrets.json", "debug/secrets.json", "../secrets.json"]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "r") as f:
                    return json.load(f)
            except:
                pass
    return {}

_secrets = load_secrets()
SHEET_ID = _secrets.get("sheet_id") or os.environ.get("SHEET_ID")
GID = _secrets.get("gid") or os.environ.get("GID")
TARGET_CELL = "E75"

if not SHEET_ID:
    print("⚠️ AVISO: SHEET_ID não encontrado em secrets.json. O envio pode falhar.")

# URL com navegação direta para a célula usando range parameter
def build_sheets_url(target_cell: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={GID}#gid={GID}&range={target_cell}"

HEADLESS = False

STORAGE_STATE = "debug/google_storage_state.json"
CSV_CODES_PATH = "outputs/codigos.csv"


def read_codes(csv_path: str) -> list[str]:
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Não achei o arquivo {csv_path} no seu projeto.")
    codes = []
    with p.open("r", encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            code = row[0].strip()
            # Se tiver cabeçalho "codigo", ignora
            if code.lower() == "codigo":
                continue
            if code:
                codes.append(code)
    if not codes:
        raise ValueError("Seu codigos.csv está vazio.")
    return codes


def focus_grid(page):
    """
    Sheets usa canvas + overlays. Em alguns layouts, o clique no canvas é interceptado
    pelo div .grid4-inner-container. Então a gente clica direto nele (ou força).
    """
    page.wait_for_timeout(2000)

    # 1) Tentativa: clicar no div que costuma interceptar mesmo
    intercept = page.locator(".grid4-inner-container").first
    try:
        intercept.wait_for(state="visible", timeout=30000)
        intercept.click(timeout=8000)
        page.wait_for_timeout(300)
        return
    except PlaywrightTimeoutError:
        pass

    # 2) Tentativa: clicar na tabela/grid do Sheets
    grid_table = page.locator(".grid-table-container").first
    try:
        grid_table.wait_for(state="visible", timeout=15000)
        grid_table.click(timeout=8000)
        page.wait_for_timeout(300)
        return
    except PlaywrightTimeoutError:
        pass

    # 3) Tentativa: clicar no canvas FORÇANDO (force=True)
    canvas = page.locator("canvas").first
    canvas.wait_for(state="visible", timeout=30000)
    canvas.click(position={"x": 200, "y": 200}, force=True, timeout=8000)
    page.wait_for_timeout(300)


def goto_cell(page, cell: str):
    """
    Força o Google Sheets a selecionar a célula correta usando a Caixa de Nome.
    Suporta Inglês ('Name Box') e Português ('Caixa de nome').
    """
    # Lista de possíveis seletores para a Caixa de Nome
    selectors = [
        "[aria-label='Caixa de nome']", # PT-BR
        "[aria-label='Name Box']",      # EN
        "#t-name-box",                  # ID (HTML interno, pode mudar, mas é tentativa)
        "input.ax-name-box-input"       # Classe interna (pode mudar)
    ]

    focus_success = False
    for sel in selectors:
        try:
            # Tenta achar e clicar
            loc = page.locator(sel).first
            if loc.is_visible():
                loc.click(timeout=1000)
                focus_success = True
                print(f"DEBUG: Focou na Caixa de Nome usando '{sel}'")
                break
        except Exception:
            continue

    if not focus_success:
        print("⚠️ AVISO: Não encontrei a 'Caixa de nome'. Tentando atalho F5 (Go To Range)...")
        page.keyboard.press("F5") # F5 no Sheets as vezes abre "Ir para" se não der refresh
        page.wait_for_timeout(500)

    # De qualquer forma, tenta digitar e dar Enter
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A") # Seleciona tudo na caixa de nome
    page.wait_for_timeout(100)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(100)
    
    page.keyboard.type(cell, delay=50) # Digita devagar
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    
    # Espera a navegação acontecer
    page.wait_for_timeout(1500)


def open_note(page):
    """Abre a nota da célula usando Shift+F2"""
    page.keyboard.press("Shift+F2")
    page.wait_for_timeout(800)


def fill_note(page, text: str):
    """Preenche o conteúdo da nota"""
    # Nota aparece em textarea
    tb = page.locator("textarea:visible").first
    tb.wait_for(timeout=10000)
    tb.click()
    page.wait_for_timeout(200)
    
    # Limpa conteúdo anterior
    page.keyboard.press("Control+A")
    page.wait_for_timeout(100)
    
    # Digita o novo conteúdo
    page.keyboard.type(text)
    page.wait_for_timeout(300)


def close_note(page):
    """Fecha e salva a nota"""
    page.keyboard.press("Escape")
    page.wait_for_timeout(1000)


def main(target_cell: str | None = None, *, headless: bool | None = None, csv_path: str | None = None, storage_state_path: str | None = None):
    global TARGET_CELL, HEADLESS, CSV_CODES_PATH, STORAGE_STATE
    if target_cell:
        TARGET_CELL = target_cell
    if headless is not None:
        HEADLESS = bool(headless)
    if csv_path:
        CSV_CODES_PATH = csv_path
    if storage_state_path:
        STORAGE_STATE = storage_state_path

    codes = read_codes(CSV_CODES_PATH)
    note_text = "\n".join(codes)

    with sync_playwright() as p:
        # Use Firefox to match login session and bypass detection
        browser = p.firefox.launch(headless=HEADLESS)
        # Ensure path is absolute or exists
        if not Path(STORAGE_STATE).exists():
             print(f"❌ ERRO: Arquivo de sessão não encontrado: {STORAGE_STATE}")
             raise FileNotFoundError(f"Arquivo de sessão não encontrado: {STORAGE_STATE}")
             
        context = browser.new_context(storage_state=STORAGE_STATE)
        page = context.new_page()
        
        # FIX: Inject stealth script to bypass Sheets detection
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"🌍 Navegando para a Planilha (Tabela: {SHEET_ID} | Célula: {TARGET_CELL})...")
        # Navega para a URL com range parameter - isso já seleciona a célula
        try:
            page.goto(build_sheets_url(TARGET_CELL), wait_until="domcontentloaded", timeout=60000)
            print("✅ Página carregada! (DOM Content Loaded)")
        except Exception as e:
            print(f"⚠️ Aviso: Timeout ou erro ao carregar página: {e}")
        
        print("⏳ Aguardando renderização inicial...")
        page.wait_for_timeout(6000)

        if "accounts.google.com" in page.url:
            print("❌ Caiu no login do Google. Refaz o save da sessão (google_storage_state.json).")
            browser.close()
            return

        # 1) Foca o grid
        focus_grid(page)
        page.wait_for_timeout(500)

        # 2) VAI PRA CÉLULA CERTA (ESSENCIAL)
        # A URL já deveria ter selecionado, mas reforçamos com goto_cell
        goto_cell(page, TARGET_CELL)
        page.wait_for_timeout(500)

        # 3) Abre nota e cola
        open_note(page)
        page.wait_for_timeout(500)
        
        fill_note(page, note_text)
        page.wait_for_timeout(500)
        
        close_note(page)
        page.wait_for_timeout(1000)

        print(f"✅ Nota criada/atualizada em {TARGET_CELL} com {len(codes)} códigos.")
        print("👉 Passe o mouse no triângulo da célula (canto) para ver a nota.")

        browser.close()


if __name__ == "__main__":
    main()