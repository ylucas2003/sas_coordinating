# banco-questoes — o material bruto do banco ITA · IME

Pipeline que transforma PDF de prova em questão classificada por tópico do
edital, e as três taxonomias dos editais.

⚠️ **As 934 questões não moram aqui.** Elas estão no Postgres, que é a fonte da
verdade desde 22/08/2026 ([docs/22 §13](../docs/22-plano-banco-questoes.md)).
O diretório `questoes_json/` existe em disco e **não é versionado**: é onde o
pipeline escreve e de onde o importador lê. Para tê-lo de volta a partir do
banco:

```sh
cd ../api && ./.venv/bin/python -m scripts.exportar_banco_questoes
```

Veio do projeto `ita-por-assunto`, que era um site estático próprio. O plano da
migração — o que entrou, o que ficou de fora e por quê — está em
[docs/22-plano-banco-questoes.md](../docs/22-plano-banco-questoes.md).

## Por que isto não mora em `api/`

O pipeline não roda em requisição nenhuma. Ele lê PDF, chama OCR e fala com o
S3 — `pymupdf`, `pytesseract`, `boto3`. Dentro de `api/app/` obrigaria o
container da API a carregar tudo isso para nunca usar.

O que roda em produção é só o **importador**, que vive em
[api/app/banco/importador.py](../api/app/banco/importador.py) e lê os JSONs
daqui.

## O que tem aqui

```
banco-questoes/
├── config/
│   ├── schema-questao.json        formato canônico de uma questão
│   ├── taxonomia-fisica.json      taxonomia do edital, por matéria
│   ├── taxonomia-matematica.json
│   └── taxonomia-quimica.json
├── questoes_json/                 934 JSONs — uma pasta por prova
│   └── ita_2019_fase1/q01.json
└── pipeline/                      scripts Python de processamento
```

Os arquivos de taxonomia foram renomeados na importação: o original chamava a de
Física de `taxonomia.json`, sem sufixo, só por ter sido a primeira das três. Era
acidente histórico virando armadilha.

## Filosofia

1. **Uma questão por arquivo, enquanto está sendo processada.** O JSON é o
   formato de trabalho do pipeline; quem guarda o acervo é o Postgres. O
   caminho é de mão dupla: `importar_banco_questoes.py` entra,
   `exportar_banco_questoes.py` sai, e o `--conferir` prova que nada se perde.
2. **Imagem em vez de extração de texto.** Cada questão é recortada como PNG.
   Evita quebrar fórmula e preserva o visual da prova.
3. **Texto como metadado.** Extraído para permitir busca e classificação — não
   para exibir. Ele tem sujeira de OCR, e é esperado.
4. **Etapas independentes.** Dá para rerodar qualquer uma sem refazer as outras.

## Processar uma prova nova

```sh
# 1. PDFs em pdfs_originais/ita_fase1/  (não versionado)

# 2. extração + recorte + gabarito
python pipeline/pipeline_completo.py pdfs_originais/ita_fase1/2026_fase1.pdf \
    --ano 2026 --fase 1 --materia Física \
    --gabarito pdfs_originais/ita_fase1/gabarito_2026.pdf

# 3. classificação (exige raciocínio — é feita com o Claude)
python pipeline/classificar.py listar ita_2026_fase1 > pendentes.txt
#    peça a classificação segundo a taxonomia de config/, e aplique:
python pipeline/classificar.py aplicar ita_2026_fase1 _classificacao_patch.json

# 4. subir as imagens novas
python pipeline/upload_s3.py ita_2026_fase1

# 5. importar para o SAS (a partir de api/)
cd ../api && ./.venv/bin/python -m scripts.importar_banco_questoes
```

O importador é **idempotente**: rodar de novo não duplica. Corrigir um JSON e
reimportar é o ciclo normal de trabalho, não operação especial.

## Corrigir uma questão

Quando alguém disser "o enunciado da 23 do IME 2018 está picotado":

```sql
select arquivo_origem, imagem_url from questao_vestibular
where id = 'ime_2018_fase1_q23';
-- banco-questoes/questoes_json/ime_2018_fase1/q23.json
```

Exporta (`exportar_banco_questoes.py`), abre o arquivo, corrige, reimporta. Com
o JSON fora do git, quem responde "de onde veio isto" são as colunas
`fonte_pdf` e `fonte_pagina` — `arquivo_origem` virou pista de reprocessamento,
não endereço garantido.

## O que saiu na migração

- **`gerar_banco_unificado.py` e `renderizar_html.py`** — geravam o HTML
  estático de 2,2 MB com todos os dados inline. Quem serve o banco agora é a
  API; quem monta lista filtrada é a tela `/banco/lista`.
- **`site/`** — a interface estática inteira, incluindo um login cosmético que
  baixava 817 matrículas de aluno para o browser validar em JavaScript.

## Limitações conhecidas

- Prova 100% escaneada com qualidade ruim pode falhar o OCR ao localizar
  "Questão N". O script avisa; registrar coordenada à mão não está implementado.
- A última questão de cada matéria às vezes traz o número da página no recorte.
- **A classificação precisa de revisão humana.** `revisado` é `false` nas 934;
  40 estão sem classificação nenhuma. Questão mista tem ambiguidade legítima.
- **As imagens só existem no S3.** `imagens/` é gerado e não versionado, e não
  há cópia local — dívida consciente registrada em
  [docs/22 §0.2](../docs/22-plano-banco-questoes.md).
- **O acervo tem uma cópia só.** Com os JSONs fora do git, as questões existem
  no Postgres e mais nada; as imagens, no S3 e mais nada. O Canvas não restaura
  nenhum dos dois. Rodar o exportador de vez em quando é o remendo até haver
  backup do banco ([docs/22 §13](../docs/22-plano-banco-questoes.md)).
