# Pipeline Offline PDF → (empresa, funcionário)

Pipeline em **Python 3.11** para extrair informações de **empresa** e **funcionário** de documentos PDF usando processamento local e modelos de linguagem.

## 📋 Visão Geral

Este projeto implementa um pipeline de extração de informações estruturadas a partir de PDFs, combinando:

- **Docling**: Conversão de PDF para estrutura JSON
- **spaCy**: Reconhecimento de entidades nomeadas (NER) e heurísticas
- **llama.cpp**: Decisão final usando modelos de linguagem locais (GGUF)

O pipeline processa documentos **localmente** (sem enviar dados para servidores externos) e faz **downloads automáticos** de modelos e dependências quando necessário.

## 🏗️ Arquitetura

O pipeline segue uma arquitetura modular em etapas:

1. **Extração (extract_json)**: Converte PDF para JSON estruturado usando Docling
2. **Blocos (blocks)**: Processa e normaliza os blocos de texto extraídos
3. **Candidatos (candidates)**: Gera candidatos para empresa e funcionário usando spaCy NER
4. **Pontuação (scoring)**: Classifica e ranqueia os candidatos com base em heurísticas
5. **Decisão LLM (decision_llm)**: Usa modelo de linguagem local para decisão final
6. **Confiança (confidence)**: Calcula métricas de confiança para os resultados

## 🚀 Requisitos

- **Sistema Operacional**: Windows 10/11
- **Python**: 3.11.x (recomendado)
- **Conexão com internet**: Necessária para downloads automáticos de dependências e modelos
- **Modelo GGUF**: Modelo de linguagem local em formato GGUF (ex.: `models/model.gguf`) - opcional

## 📦 Instalação

### 1. Criar ambiente virtual

```bash
py -3.11 -m venv .venv
.\.venv\Scripts\activate
```

### 2. Instalar dependências

O projeto faz **downloads automáticos** de todas as dependências necessárias:

```bash
pip install -r requirements.txt
```

### 3. Instalar modelo spaCy

O modelo spaCy `pt_core_news_lg` será baixado automaticamente na primeira execução. Para instalar manualmente:

```bash
python -m spacy download pt_core_news_lg
```

### 4. Configurar modelo GGUF (opcional)

Coloque seu modelo GGUF em `models/` (ex.: `models/model.gguf`).

**Modelo recomendado: Qwen**

Para usar o modelo Qwen, baixe uma versão GGUF do repositório oficial:

- [Qwen2.5 GGUF Models](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF)
  Para testes iniciais, usamos o modelo Qween 2.5 7b q4 k_m
  https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/blob/main/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
  https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/blob/main/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf

Após o download, coloque o arquivo `.gguf` na pasta `models/` e use com a flag `--chat-format qwen`:

```bash
python main.py --pdf documento.pdf --out output\result.json --model models\qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguff --chat-format qwen
```

## 💻 Uso

### Uso básico

```bash
python main.py --pdf examples\sample.pdf --out output\result.json --model models\model.gguf
```

### Opções disponíveis

- `--pdf`: Caminho para o PDF de entrada (obrigatório)
- `--out`: Caminho para o arquivo JSON de saída (obrigatório)
- `--model`: Caminho para o modelo GGUF (opcional)
- `--chat-format`: Formato de chat do llama.cpp (ex.: `qwen`) - útil quando o modelo precisa de um template explícito
- `--offline`: Desabilita acesso à rede (sem downloads de modelos). Se os modelos necessários estiverem faltando, a saída será `INDEFINIDO`
- `--debug`: Inclui detalhes de debug no JSON de saída

### Exemplo com modo offline

```bash
python main.py --pdf funcionario.pdf --out output\result.json --offline
```

## 📤 Formato de Saída

O pipeline gera um arquivo JSON com a seguinte estrutura:

```json
{
  "funcionario": "João Silva",
  "empresa": "Empresa XYZ Ltda",
  "confidence": {
    "funcionario": 0.85,
    "empresa": 0.92
  },
  "debug": {
    "extraction_quality": "ok",
    "blocks_count": 45,
    "candidates_count": {
      "funcionarios": 12,
      "empresas": 8
    },
    "top_ranked": {
      "funcionario": [
        { "text": "João Silva", "score": 0.95 },
        { "text": "J. Silva", "score": 0.7 }
      ],
      "empresa": [{ "text": "Empresa XYZ Ltda", "score": 0.98 }]
    },
    "llm_used": true
  }
}
```

### Casos de erro

Em caso de falha na extração ou erro de processamento, a saída será:

```json
{
  "funcionario": "INDEFINIDO",
  "empresa": "INDEFINIDO",
  "confidence": {
    "funcionario": 0.0,
    "empresa": 0.0
  },
  "debug": {
    "extraction_quality": "weak",
    "error": "extract_failed:ExceptionName"
  }
}
```

## 🔒 Privacidade e Segurança

- **Processamento local**: O pipeline não envia seu PDF nem resultados para nenhum servidor. Todo o processamento acontece na sua máquina
- **Downloads automáticos**: Por padrão, o projeto faz downloads automáticos de modelos e dependências quando necessário (Docling, spaCy, etc.)
- **Modo offline**: Use a flag `--offline` para desabilitar downloads durante a execução (requer que todos os modelos já estejam instalados)
- **Arquivos ignorados**: Por padrão, o `.gitignore` exclui `*.pdf`, `output/`, `result/`, `.history/` e `models/`

## ⚙️ Configuração

As configurações do pipeline podem ser ajustadas em `config.py` através da classe `PipelineConfig`:

- **Extração**: Qualidade mínima de extração, número mínimo de caracteres úteis
- **Candidatos**: Modelo spaCy, número máximo de candidatos por tipo
- **Pontuação**: Pesos para diferentes heurísticas (palavras-chave, frequência, posição, formato)
- **LLM**: Parâmetros do modelo (contexto, temperatura, tokens máximos)
- **Confiança**: Limite mínimo de confiança

## 🧪 Testes

O projeto inclui testes para garantir qualidade e determinismo:

```bash
pytest tests/
```

### Testes disponíveis

- `test_determinism.py`: Verifica que os resultados são determinísticos
- `test_extract_quality.py`: Valida a qualidade da extração

## 📝 Notas sobre Determinismo

- O LLM roda com `temperature=0` e `seed` fixo para garantir resultados reproduzíveis
- Ranking e desempates são estáveis (ordem de aparição como fallback)
- Em caso de extração ruim, erro de modelo ou erro de validação JSON: retorna `INDEFINIDO`

## 📁 Estrutura do Projeto

```
docling_project/
├── main.py                 # Ponto de entrada principal
├── config.py              # Configurações do pipeline
├── requirements.txt       # Dependências do projeto
├── pipeline/              # Módulos do pipeline
│   ├── __init__.py
│   ├── blocks.py          # Processamento de blocos de texto
│   ├── candidates.py      # Geração de candidatos (NER)
│   ├── confidence.py      # Cálculo de confiança
│   ├── decision_llm.py    # Decisão final com LLM
│   ├── extract_json.py    # Extração Docling
│   ├── scoring.py         # Pontuação e ranking
│   └── utils.py           # Utilitários
└── tests/                 # Testes automatizados
    ├── test_determinism.py
    └── test_extract_quality.py
```

## 🤝 Contribuindo

Este é um projeto privado. Para contribuições, entre em contato com o mantenedor.


## 🔗 Referências

- [Docling](https://github.com/DS4SD/docling)
- [spaCy](https://spacy.io/)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
