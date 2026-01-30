from playwright.sync_api import sync_playwright

SHEETS_URL = "https://docs.google.com/spreadsheets/d/1Z_2mW4sQj6WtkqPgLMdcKa3pma1gAOchWk7Df79pXKs/edit?gid=966315382#gid=966315382"
OUT_STATE = "google_state.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        page = context.new_page()
        page.goto(SHEETS_URL, wait_until="domcontentloaded")

        print("\n✅ Faça login no Google normalmente nessa janela.")
        print("✅ Quando a planilha abrir completamente, volte aqui e aperte ENTER no terminal...\n")
        input()

        context.storage_state(path=OUT_STATE)
        print(f"✅ Sessão salva em: {OUT_STATE}")

        context.close()
        browser.close()

if __name__ == "__main__":
    main()
