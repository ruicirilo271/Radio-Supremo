# Rádio Supremo 24/7 — Shazam Supremo

Versão preparada para Vercel com:

- Rádio 24/7 automática.
- Troca automática de stream conforme a grelha.
- Player fixo no rodapé.
- CSS servido pelo Flask para evitar problemas no Vercel.
- Identificação de músicas com ShazamIO.
- Botão manual **Identificar**.
- Botão **Forçar nova identificação**.
- Identificação automática a cada 2 minutos quando a rádio está a tocar.

## Ficheiros

```txt
api/index.py
api/templates/index.html
api/static/style.css
api/static/script.js
templates/index.html
static/style.css
static/script.js
requirements.txt
vercel.json
```

## Como correr no PC

```bash
pip install -r requirements.txt
python api/index.py
```

Abre:

```txt
http://127.0.0.1:5000
```

## Como publicar no Vercel

1. Envia os ficheiros para o GitHub.
2. Importa o repositório no Vercel.
3. Framework: Other.
4. Deploy.

## Testes úteis depois de publicar

```txt
/api/health
/api/static-check
/static/style.css?v=7-shazam
/static/script.js?v=7-shazam
/api/test-shazam
/api/identify/m80?seconds=18&force=1
/api/identify/rfm?seconds=18&force=1
/api/test-streams
```

## Notas importantes

A identificação não retransmite rádio. A app grava uma pequena amostra temporária do stream em `/tmp`, envia para reconhecimento pelo ShazamIO e apaga a amostra no fim.

Em algumas rádios, se estiver a dar conversa, publicidade, notícias ou uma intro sem música, o Shazam pode não reconhecer. Nesses casos, tenta novamente quando a música estiver no refrão.
