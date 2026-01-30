import csv
from pathlib import Path
from playwright.sync_api import sync_playwright

SHEET_ID = "1Z_2mW4sQj6WtkqPgLMdcKa3pma1gAOchWk7Df79pXKs"
GID = "966315382"
TARGET_CELL = "E92"

# URL com range parameter - leva direto para E75
SHEETS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={GID}#gid={GID}&range={TARGET_CELL}"

STORAGE_STATE = "debug/google_storage_state.json"
CSV_CODES_PATH = "outputs/codigos.csv"


def read_codes(csv_path: str ) -> list[str]:
    """Lê os códigos do CSV"""
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Não achei o arquivo {csv_path}")
    
    codes = []
    with p.open("r", encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            code = row[0].strip()
            if code.lower() == "codigo":
                continue
            if code:
                codes.append(code)
    
    if not codes:
        raise ValueError("Seu codigos.csv está vazio")
    
    return codes


def main():
    codes = read_codes(CSV_CODES_PATH)
    note_text = "\n".join(codes)

    print("=" * 70)
    print("🚀 SCRIPT FINAL - ADICIONA NOTA NA CÉLULA E75")
    print("=" * 70)
    print(f"📊 Total de códigos: {len(codes)}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=STORAGE_STATE)
        page = context.new_page()

        print("1️⃣  Abrindo planilha e navegando para E75...")
        # A URL já tem &range=E75, então vai direto para lá
        page.goto(SHEETS_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)

        if "accounts.google.com" in page.url:
            print("❌ Erro: Caiu no login do Google")
            browser.close()
            return

        print("✅ Planilha aberta e em E75")
        print()

        # Aguarda um pouco para a página carregar completamente
        page.wait_for_timeout(2000)

        # Abre a nota com Shift+F2
        print("2️⃣  Abrindo nota (comentário)...")
        page.keyboard.press("Shift+F2")
        page.wait_for_timeout(2500)
        print("✅ Nota aberta")
        print()

        # Aguarda a textarea aparecer
        print("3️⃣  Aguardando campo de texto...")
        try:
            tb = page.locator("textarea:visible").first
            tb.wait_for(timeout=10000)
            page.wait_for_timeout(1000)
            print("✅ Campo de texto encontrado")
        except Exception as e:
            print(f"❌ Erro ao encontrar campo de texto: {e}")
            print("   Tentando clicar na textarea...")
            try:
                # Tenta encontrar a textarea de outra forma
                tb = page.locator("textarea").first
                tb.wait_for(timeout=5000)
                tb.click()
                page.wait_for_timeout(1000)
                print("✅ Campo encontrado e clicado")
            except:
                print("❌ Não conseguiu encontrar o campo de texto")
                browser.close()
                return
        print()

        # Clica na textarea
        print("4️⃣  Clicando no campo de texto...")
        tb.click()
        page.wait_for_timeout(500)
        print("✅ Campo focado")
        print()

        # Limpa conteúdo anterior (se houver)
        print("5️⃣  Limpando conteúdo anterior...")
        page.keyboard.press("Control+A")
        page.wait_for_timeout(200)
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        print("✅ Limpado")
        print()

        # Digita os códigos
        print(f"6️⃣  Adicionando {len(codes)} códigos na nota...")
        page.keyboard.type(note_text)
        page.wait_for_timeout(1500)
        print("✅ Códigos adicionados")
        print()

        # Fecha a nota
        print("7️⃣  Fechando e salvando nota...")
        page.keyboard.press("Escape")
        page.wait_for_timeout(2500)
        print("✅ Nota salva")
        print()

        print("=" * 70)
        print("✅ SUCESSO!")
        print("=" * 70)
        print(f"✓ Nota criada em {TARGET_CELL}")
        print(f"✓ {len(codes)} códigos adicionados")
        print("✓ Passe o mouse no triângulo vermelho da célula para ver a nota")
        print()
        print("A planilha vai fechar em 5 segundos...")
        print()

        page.wait_for_timeout(5000)
        browser.close()

        print("✅ Tudo pronto!")


if __name__ == "__main__":
    main()
