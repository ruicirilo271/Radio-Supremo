# Rádio Supremo 24/7 — Shazam + Programação JSON

Versão preparada para Vercel, sem bloco `functions` no `vercel.json`, com:

- rádio 24/7 automática;
- streams por estação;
- Shazam em escada progressiva;
- ficheiro `api/programacao.json` com a grelha da rádio;
- exportação de JSON no frontend;
- importação de JSON no frontend;
- reposição da grelha padrão.

## Estrutura obrigatória na raiz do repositório

```txt
api/index.py
api/programacao.json
api/templates/index.html
api/static/style.css
api/static/script.js
requirements.txt
vercel.json
README.md
```

Não coloques estes ficheiros dentro de uma subpasta no GitHub.

## Programação JSON

A grelha padrão está em:

```txt
api/programacao.json
```

Formato principal:

```json
{
  "schema": "radio_supremo_programacao_v1",
  "name": "Rádio Supremo 24/7 — Programação",
  "timezone": "Europe/Lisbon",
  "default_favorites": ["comercial_manhas", "rfm_cafe"],
  "programs": [
    {
      "id": "comercial_manhas",
      "name": "Manhãs da Comercial",
      "station_id": "comercial",
      "days": [0, 1, 2, 3, 4],
      "start": "07:00",
      "end": "07:45",
      "presenters": "Pedro Ribeiro, Vera Fernandes, Vasco Palmeirim, Nuno Markl e equipa",
      "category": "humor/música",
      "official": true,
      "priority": 100,
      "description": "Humor, música e ritmo."
    }
  ]
}
```

Dias:

```txt
0 = segunda
1 = terça
2 = quarta
3 = quinta
4 = sexta
5 = sábado
6 = domingo
```

## Importar/exportar JSON no site

Na página tens agora:

- **Exportar JSON**: baixa a grelha atual para o computador.
- **Importar JSON**: escolhes um ficheiro `.json` e a app passa a usar essa grelha.
- **Repor grelha padrão**: remove o JSON importado e volta ao `api/programacao.json`.

A importação no browser fica guardada em `localStorage`, por isso continua depois de recarregares a página.

## Como publicar no Vercel

1. Apaga os ficheiros antigos do repositório.
2. Envia estes ficheiros para a raiz do repositório.
3. Confirma que no GitHub aparece `api/index.py` logo na raiz.
4. Faz redeploy no Vercel.

## Testes depois do deploy

```txt
/api/health
/api/static-check
/api/config
/api/programacao
/api/test-shazam
/api/identify/m80?seconds=18&force=1
```
