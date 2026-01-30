import os

try:
    os.remove(r"\\?\c:\Users\Rafael\Downloads\robo-questoes-gui-ready\robo-questoes\nul")
    print("Deleted nul")
except Exception as e:
    print(f"Failed: {e}")
