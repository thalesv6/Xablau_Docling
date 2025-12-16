# Pipeline offline PDF → (empresa, funcionario)

Pipeline em **Python 3.11** totalmente **offline** para extrair **empresa** e **funcionário** de PDFs usando:

- Docling (PDF → JSON/estrutura)
- spaCy (NER + heurísticas)
- llama.cpp via `llama-cpp-python` (decisão final restrita a candidatos)

## Requisitos

- Windows 10/11
- Python 3.11.x (recomendado)
- Execução local (processamento do PDF ocorre na sua máquina)
- Modelo GGUF local em `models/`
- Modelo spaCy `pt_core_news_lg` já disponível **offline** (não baixar em runtime)

## Instalação (offline)

1. Crie um venv:

```bash
py -3.11 -m venv .venv
.\.venv\Scripts\activate
```

2. Instale dependências a partir de wheels/artefatos locais.

Este projeto **não faz download automático**. Você deve ter um diretório local com wheels, por exemplo `wheels/`.

```bash
pip install --no-index --find-links wheels -r requirements.txt
```

3. Instale o modelo spaCy **offline** (sem downloads em runtime).

Se você tem o pacote do modelo (ex.: `pt_core_news_lg-*.whl`) em `wheels/`, use:

```bash
pip install --no-index --find-links wheels pt_core_news_lg
```

4. Coloque seu modelo GGUF em `models/` (ex.: `models/model.gguf`).

## Uso

```bash
python main.py --pdf examples\sample.pdf --out output\result.json --model models\model.gguf
```

### Privacidade e rede

- **O pipeline não “sobe” seu PDF nem o resultado.** O processamento acontece localmente.
- Algumas bibliotecas (ex.: Docling) podem **baixar modelos** na primeira execução. Isso é **download de artefatos**, não upload do seu documento.
- Se você quiser bloquear qualquer acesso à rede (e aceitar `INDEFINIDO` quando faltar modelo), use:

```bash
python main.py --pdf funcionario.pdf --out output\result.json --offline
```

Para evitar subir arquivos no Git, este projeto ignora por padrão `*.pdf`, `output/` e `models/` via `.gitignore`.

Saída:

```json
{
  "funcionario": "INDEFINIDO",
  "empresa": "INDEFINIDO",
  "confidence": { "funcionario": 0.0, "empresa": 0.0 },
  "debug": { "extraction_quality": "weak" }
}
```

## Notas de determinismo

- LLM roda com `temperature=0` e `seed` fixo.
- Ranking e desempates são estáveis (ordem de aparição como fallback).
- Em caso de extração ruim / erro de modelo / erro de validação JSON: retorna `INDEFINIDO`.
