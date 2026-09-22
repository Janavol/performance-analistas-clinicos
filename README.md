# Performance Analistas Clínicos

Painel automático de performance dos analistas: calcula notificação de resultados
críticos, cumprimento de TAT por protocolo (PA, UI, UTI, Sepse, Dor Torácica, AVE) e o
score final ponderado de cada analista a partir de uma planilha de pedidos — com
exportação em **Excel** e **PDF**.

Reimplementação em Python/Streamlit do artifact original, para que qualquer pessoa
que abra o link do app consiga baixar os relatórios (o download por link de artifact
do Claude só funciona para quem tem acesso de edição na mesma organização).

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura

- `app.py` — interface Streamlit (layout, upload, configuração, filtro de analistas, downloads).
- `engine.py` — motor de cálculo (réplica da lógica da planilha de referência: TAT, notificação, scores por bloco, score final ponderado, classificação).
- `insights.py` — geração de insight automático por analista, comparado à equipe.
- `charts.py` — gráficos (barras e radar) em matplotlib, usados na tela e no PDF.
- `excel_export.py` — geração do `.xlsx` de resultado e do modelo de planilha para preenchimento.
- `pdf_report.py` — geração do relatório em PDF (reportlab), com uma página por analista.

## Formato da planilha de entrada

Colunas esperadas (nomes flexíveis, detectados por palavra-chave):

| Coluna | Descrição |
|---|---|
| Analista | nome do analista responsável |
| Categoria | `CRITICOAMB`, `CRITICOHOSP`, `PA`, `UI`, `UTI`, `SEPSE`, `DOR_TORACICA`, `AVE` |
| Hora início | data/hora de início do atendimento |
| Hora Liberação Clínica | data/hora da liberação |
| Hora Notificação | só para `CRITICOAMB`/`CRITICOHOSP` |

Baixe o modelo pronto direto no app (seção "Enviar planilha", no fim da página).

## Deploy no Streamlit Community Cloud

1. Suba este repositório no GitHub (já feito, se você está lendo isso a partir de lá).
2. Em [share.streamlit.io](https://share.streamlit.io), clique em **New app**.
3. Selecione este repositório, branch `main` e o arquivo principal `app.py`.
4. Deploy. O app fica disponível em uma URL pública `https://<algo>.streamlit.app`,
   e qualquer pessoa com o link consegue usar os botões de download.
