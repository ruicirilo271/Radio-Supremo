# Rádio Supremo 24/7 — CSS Corrigido para Vercel

Esta versão corrige o problema em que o Vercel carregava a página mas não lia o CSS/JS.

## Correção aplicada

- `static` e `templates` foram também colocados dentro de `/api`, para entrarem no bundle da função Python do Vercel.
- O Flask serve `/static/style.css` e `/static/script.js` diretamente com `send_from_directory`.
- O `vercel.json` já não tenta servir `/static` por uma rota separada.
- Cache atualizado para `?v=6`.

## Testes depois do deploy

Abre estes links:

```txt
https://TEU-SITE.vercel.app/api/health
https://TEU-SITE.vercel.app/api/static-check
https://TEU-SITE.vercel.app/static/style.css?v=6
https://TEU-SITE.vercel.app/static/script.js?v=6
```

Se `/static/style.css?v=6` abrir texto CSS, o estilo está a ser servido.

## Correr no PC

```bash
pip install -r requirements.txt
python api/index.py
```

Depois abre:

```txt
http://127.0.0.1:5000
```
