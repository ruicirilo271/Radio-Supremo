# Rádio Supremo 24/7 — Super Deus Supremo

App Flask preparada para Vercel que toca rádios portuguesas 24/7 e muda automaticamente conforme uma grelha curada de música, notícias, entrevistas e humor.

## Correção desta versão

Esta versão corrige o botão **Ativar rádio 24/7**.

O problema estava na lógica antiga: ao carregar no botão, a app chamava `/api/stream` e o servidor tentava validar streams antes de devolver resposta. Em Vercel isso podia demorar demasiado, falhar por timeout, ou fazer o browser perder a ativação do clique necessária para `audio.play()`.

Agora:

- `/api/config` envia logo os streams para o frontend.
- O botão **Ativar rádio 24/7** tenta tocar imediatamente no browser.
- `/api/stream/<radio>` já não valida por defeito; devolve candidatos rápido.
- Para validar manualmente, usa `/api/stream/<radio>?validate=1`.
- O player tenta vários candidatos por estação.
- O spectrum visual não usa Web Audio API, para não silenciar streams externos sem CORS.

## Estações incluídas

- Rádio Comercial
- RFM
- Rádio Renascença
- M80 Rádio
- Cidade FM
- Mega Hits
- Antena 1
- Antena 3
- TSF Rádio Notícias

## Rotas úteis

- `/` — app principal
- `/api/health` — estado da app
- `/api/config` — grelha + estações + streams
- `/api/now` — programa recomendado neste momento
- `/api/stream/m80` — candidatos rápidos da M80
- `/api/stream/m80?validate=1` — diagnóstico validado da M80
- `/api/test-streams` — diagnóstico geral dos streams

## Correr no PC

```bash
pip install -r requirements.txt
python api/index.py
```

Depois abre:

```txt
http://127.0.0.1:5000
```

## Publicar no Vercel

1. Envia os ficheiros para um repositório GitHub.
2. Importa no Vercel.
3. Framework: Other.
4. Deploy.

Não são necessárias API keys.

## Nota legal

A app não grava, não redistribui e não faz proxy permanente de áudio. Apenas muda o endereço do player HTML5 para streams públicos/diretos das rádios.


## Shazam em escada progressiva

Nesta versão a identificação já não fica presa numa única amostra de 18 segundos.

No botão manual, a app tenta automaticamente:

```txt
12s → 18s → 25s → 35s → 50s
```

Assim que o Shazam reconhecer a música, a app para a sequência e mostra título, artista, capa e link do Shazam quando disponível.

No modo automático, para não rebentar timeouts no Vercel, a app usa uma escada mais leve:

```txt
12s → 18s → 25s
```

Se o automático não identificar, carrega em **Forçar nova identificação** para tentar a escada completa até 50 segundos.

Rotas úteis:

```txt
/api/identify/m80?seconds=12&force=1
/api/identify/m80?seconds=25&force=1
/api/identify/m80?seconds=50&force=1
```
