from playwright.sync_api import sync_playwright
import traceback

BASE_URL = "https://manager.eumedicoresidente.com.br"
START_URL = BASE_URL + "/admin/resources/Question"

def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=50)
            context = browser.new_context()
            page = context.new_page()

            print("Abrindo:", START_URL)
            page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)

            print("\n✅ Navegador aberto.")
            print("👉 Faça login se aparecer.")
            print("👉 Quando estiver logado na tela de Questões, aperte ENTER aqui.\n")
            input()

            context.storage_state(path="debug/storage_state.json")
            print("✅ Sessão salva em storage_state.json")

            browser.close()

    except Exception:
        print("\n❌ Deu erro. Aqui está o erro completo:\n")
        traceback.print_exc()
        print("\n(aperte ENTER para sair)")
        input()

if __name__ == "__main__":
    main()
