# Robo Questões

Automação para extração de questões de PDFs e envio para Google Sheets.

## Estrutura do Projeto

- `gui_app.py`: Interface gráfica principal.
- `scripts/`: Scripts de extração (PDF) e envio (Sheets).
- `inputs/`: Coloque os PDFs aqui.
- `outputs/`: Resultados CSV.
- `debug/`: Logs e sessões de navegador (não comitar!).

## Configuração (Segurança)

Este projeto utiliza um arquivo `secrets.json` para armazenar o ID da planilha, evitando exposição no código. Crie um arquivo `secrets.json` na raiz do projeto com o seguinte conteúdo:

```json
{
    "sheet_id": "SEU_ID_DA_PLANILHA",
    "gid": "SEU_GID"
}
```

## Como Gerar o Executável

Para criar o arquivo `.exe` (Windows), execute o script:

```bat
build_exe_windows.bat
```

O executável será gerado na pasta `dist/`.

> **Nota:** A pasta `debug/` não é copiada para o executável por segurança. Ao rodar o EXE pela primeira vez, será necessário fazer login novamente.
