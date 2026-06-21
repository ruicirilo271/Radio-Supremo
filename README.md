# Rádio Supremo 24/7 — Shazam Escada — Vercel sem erro de functions

Esta versão removeu o bloco `functions` do `vercel.json` para evitar o erro:

`The pattern "api/index.py" defined in functions doesn't match any Serverless Functions inside the api directory`

## Estrutura obrigatória na raiz do repositório

```
api/index.py
api/templates/index.html
api/static/style.css
api/static/script.js
requirements.txt
vercel.json
README.md
```

Não coloques estes ficheiros dentro de uma subpasta no GitHub.

## Como publicar no Vercel

1. Apaga os ficheiros antigos do repositório.
2. Envia estes ficheiros para a raiz do repositório.
3. Confirma que no GitHub aparece `api/index.py` logo na raiz.
4. Faz redeploy no Vercel.

## Testes depois do deploy

```
/api/health
/api/static-check
/api/test-shazam
/api/identify/m80?seconds=18&force=1
```
