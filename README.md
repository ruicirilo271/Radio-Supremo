# Rádio Supremo 24/7 — Shazam Escada Progressiva — Vercel Fix

Esta versão corrige o erro das funções no Vercel.

## Estrutura correta

No GitHub/Vercel, estes ficheiros têm de estar na raiz do projeto:

```txt
api/index.py
api/templates/index.html
api/static/style.css
api/static/script.js
requirements.txt
vercel.json
```

Não coloques estes ficheiros dentro de uma pasta extra tipo `radio_supremo_24_7_shazam/`, senão o Vercel deixa de encontrar `api/index.py`.

## vercel.json corrigido

```json
{
  "version": 2,
  "functions": {
    "api/index.py": {
      "maxDuration": 60
    }
  },
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/api/index.py"
    }
  ]
}
```

Nesta versão removi `builds` e `routes`, porque podem provocar conflitos no Vercel moderno. O Vercel deteta o runtime Python automaticamente quando existe uma app Flask exposta como `app` dentro de `api/index.py`.

## Como testar depois do deploy

Abre estas rotas:

```txt
/api/health
/api/static-check
/static/style.css?v=8-ladder
/static/script.js?v=8-ladder
/api/test-shazam
/api/identify/m80?seconds=18&force=1
```

## Shazam em escada

O botão manual tenta:

```txt
12s → 18s → 25s → 35s → 50s
```

O modo automático tenta apenas:

```txt
12s → 18s → 25s
```

Isto evita timeouts constantes no Vercel.

## Correr localmente

```bash
pip install -r requirements.txt
python api/index.py
```

Depois abre:

```txt
http://127.0.0.1:5000
```
