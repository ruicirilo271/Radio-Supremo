# -*- coding: utf-8 -*-
"""
Rádio Supremo 24/7 — Flask + Vercel
Toca streams oficiais/diretos no browser e muda automaticamente conforme a grelha.
Não grava, não retransmite e não faz proxy permanente de áudio.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import os
import time
import requests
from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

TZ = ZoneInfo("Europe/Lisbon")
USER_AGENT = "Mozilla/5.0 RadioSupremo24-7/2.0 (+https://vercel.app)"

# Streams diretos conhecidos + fallback dinâmico via Radio Browser.
# Alguns URLs podem mudar com o tempo; por isso há vários candidatos e /api/stream tenta resolver.
STATIONS: Dict[str, Dict[str, Any]] = {
    "comercial": {
        "id": "comercial",
        "name": "Rádio Comercial",
        "brand": "Comercial",
        "kind": "Música + humor + entretenimento",
        "color": "#ff5630",
        "site": "https://radiocomercial.pt/",
        "search_terms": ["Radio Comercial Portugal", "Rádio Comercial Lisboa", "Comercial Portugal"],
        "streams": [
            "https://stream-icy.bauermedia.pt/comercial.aac",
            "https://stream-hls.bauermedia.pt/comercial.aac/playlist.m3u8",
            "https://stream-icy.bauermedia.pt/comercial.mp3",
            "https://mcrscast.mcr.iol.pt/comercial.mp3",
            "http://mcrscast.mcr.iol.pt/comercial.mp3",
        ],
    },
    "rfm": {
        "id": "rfm",
        "name": "RFM",
        "brand": "RFM",
        "kind": "Música pop + humor + magazine",
        "color": "#1dd1a1",
        "site": "https://rfm.pt/",
        "search_terms": ["RFM Portugal", "RFM Lisboa", "RFM só grandes músicas"],
        "streams": [
            "https://22353.live.streamtheworld.com/RFMAAC.aac",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/RFMAAC.aac",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/RFM_SC",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/RFM_SC.mp3",
        ],
    },
    "renascenca": {
        "id": "renascenca",
        "name": "Rádio Renascença",
        "brand": "Renascença",
        "kind": "Notícias + humor + entrevistas + música",
        "color": "#1f7aff",
        "site": "https://rr.pt/",
        "search_terms": ["Radio Renascenca Portugal", "Rádio Renascença Lisboa", "RR Portugal"],
        "streams": [
            "https://28933.live.streamtheworld.com/RADIO_RENASCENCAAAC.aac",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/RADIO_RENASCENCAAAC.aac",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/RADIO_RENASCENCA_SC",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/RADIO_RENASCENCA_SC.mp3",
        ],
    },
    "m80": {
        "id": "m80",
        "name": "M80 Rádio",
        "brand": "M80",
        "kind": "Clássicos 70/80/90/2000 + humor",
        "color": "#ffb703",
        "site": "https://m80.pt/",
        "search_terms": ["M80 Radio Portugal", "M80 Rádio Lisboa", "M80 Portugal"],
        "streams": [
            "https://stream-icy.bauermedia.pt/m80.aac",
            "https://stream-hls.bauermedia.pt/m80.aac/playlist.m3u8",
            "https://stream-icy.bauermedia.pt/m8080.aac",
            "https://stream-icy.bauermedia.pt/m8090.aac",
            "https://stream-icy.bauermedia.pt/m80rock.aac",
            "https://mcrscast.mcr.iol.pt/m80.mp3",
            "http://mcrscast.mcr.iol.pt/m80.mp3",
        ],
    },
    "cidade": {
        "id": "cidade",
        "name": "Cidade FM",
        "brand": "Cidade FM",
        "kind": "Hits jovem + humor + jogos",
        "color": "#00d4ff",
        "site": "https://cidade.fm/",
        "search_terms": ["Cidade FM Portugal", "Radio Cidade FM Portugal", "Cidade FM Lisboa"],
        "streams": [
            "https://stream-icy.bauermedia.pt/cidade.aac",
            "https://stream-hls.bauermedia.pt/cidade.aac/playlist.m3u8",
            "https://stream-icy.bauermedia.pt/cidade.mp3",
            "https://mcrscast.mcr.iol.pt/cidadefm.mp3",
            "http://mcrscast.mcr.iol.pt/cidadefm.mp3",
        ],
    },
    "mega": {
        "id": "mega",
        "name": "Mega Hits",
        "brand": "Mega Hits",
        "kind": "Hits jovem + cultura pop",
        "color": "#e84393",
        "site": "https://megahits.fm/",
        "search_terms": ["Mega Hits Portugal", "Mega Hits Lisboa", "MegaHits Portugal"],
        "streams": [
            "https://28553.live.streamtheworld.com/MEGA_HITSAAC.aac",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/MEGA_HITSAAC.aac",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/MEGA_HITS_SC",
            "https://playerservices.streamtheworld.com/api/livestream-redirect/MEGA_HITS_SC.mp3",
        ],
    },
    "antena1": {
        "id": "antena1",
        "name": "Antena 1",
        "brand": "Antena 1",
        "kind": "Serviço público + notícias + entrevistas",
        "color": "#d63031",
        "site": "https://www.rtp.pt/antena1/",
        "search_terms": ["Antena 1 Portugal", "RTP Antena 1"],
        "streams": [
            "https://streaming-live.rtp.pt/liveradio/antena180a/playlist.m3u8",
        ],
    },
    "antena3": {
        "id": "antena3",
        "name": "Antena 3",
        "brand": "Antena 3",
        "kind": "Alternativa pop + nova música + cultura",
        "color": "#6c5ce7",
        "site": "https://antena3.rtp.pt/",
        "search_terms": ["Antena 3 Portugal", "RTP Antena 3"],
        "streams": [
            "https://streaming-live.rtp.pt/liveradio/antena380a/playlist.m3u8",
        ],
    },
    "tsf": {
        "id": "tsf",
        "name": "TSF Rádio Notícias",
        "brand": "TSF",
        "kind": "Notícias + debate + entrevistas",
        "color": "#0984e3",
        "site": "https://www.tsf.pt/",
        "search_terms": ["TSF Radio Noticias Portugal", "TSF Lisboa", "TSF Rádio Notícias"],
        "streams": [
            "http://tsfdirecto.tsf.pt/tsfdirecto.aac",
            "https://tsfdirecto.tsf.pt/tsfdirecto.mp3",
            "http://tsfdirecto.tsf.pt/tsfdirecto.mp3",
        ],
    },
}

# Grelha curada. Dias: 0 segunda ... 6 domingo.
# "official": programa conhecido da estação; "curated": bloco criado pela app para preencher 24/7.
PROGRAMS: List[Dict[str, Any]] = [
    {
        "id": "mega_snooze",
        "name": "Snooze",
        "station_id": "mega",
        "days": [0, 1, 2, 3, 4],
        "start": "06:00",
        "end": "07:00",
        "presenters": "Pilar Lourenço, Joana Sequeira e Mateus Lourenço",
        "category": "jovem/humor",
        "official": True,
        "priority": 70,
        "description": "Arranque jovem, hits, boa disposição e cultura pop.",
    },
    {
        "id": "comercial_manhas",
        "name": "Manhãs da Comercial",
        "station_id": "comercial",
        "days": [0, 1, 2, 3, 4],
        "start": "07:00",
        "end": "07:45",
        "presenters": "Pedro Ribeiro, Vera Fernandes, Vasco Palmeirim, Nuno Markl e equipa",
        "category": "humor/música",
        "official": True,
        "priority": 100,
        "description": "O primeiro bloco da manhã vai para a rádio líder: humor, música e ritmo.",
    },
    {
        "id": "tsf_manha_jornal",
        "name": "Manhã TSF / Jornal da manhã",
        "station_id": "tsf",
        "days": [0, 1, 2, 3, 4],
        "start": "07:45",
        "end": "08:15",
        "presenters": "Redação TSF",
        "category": "notícias",
        "official": True,
        "priority": 92,
        "description": "Bloco forte de informação, manchetes, trânsito, atualidade e contexto.",
    },
    {
        "id": "rfm_cafe",
        "name": "Café da Manhã",
        "station_id": "rfm",
        "days": [0, 1, 2, 3, 4],
        "start": "08:15",
        "end": "09:00",
        "presenters": "Pedro Fernandes, Mariana Alvim, Luís Pinheiro e Ana Garcia Martins",
        "category": "humor/música",
        "official": True,
        "priority": 97,
        "description": "Humor, música, atualidade leve e grande audiência.",
    },
    {
        "id": "rr_tres_manha",
        "name": "As Três da Manhã",
        "station_id": "renascenca",
        "days": [0, 1, 2, 3, 4],
        "start": "09:00",
        "end": "09:30",
        "presenters": "Ana Galvão, Inês Lopes Gonçalves e Joana Marques",
        "category": "humor/notícias",
        "official": True,
        "priority": 98,
        "description": "Humor, comentário, atualidade e o estilo Joana Marques.",
    },
    {
        "id": "antena3_manhas",
        "name": "Manhãs da 3",
        "station_id": "antena3",
        "days": [0, 1, 2, 3, 4],
        "start": "09:30",
        "end": "10:00",
        "presenters": "Alexandre Guimarães e Andreia Pinto",
        "category": "cultura/música nova",
        "official": True,
        "priority": 75,
        "description": "Nova música portuguesa, cultura pop e alternativa.",
    },
    {
        "id": "m80_manhas",
        "name": "Manhãs da M80",
        "station_id": "m80",
        "days": [0, 1, 2, 3, 4],
        "start": "10:00",
        "end": "11:00",
        "presenters": "Ana Moreira, Paulo Fernandes e Susana Romana",
        "category": "clássicos/humor",
        "official": True,
        "priority": 82,
        "description": "Clássicos, boa disposição e transição para a manhã adulta.",
    },
    {
        "id": "tsf_forum",
        "name": "Fórum TSF",
        "station_id": "tsf",
        "days": [0, 1, 2, 3, 4],
        "start": "11:00",
        "end": "12:00",
        "presenters": "TSF + ouvintes",
        "category": "debate/notícias",
        "official": True,
        "priority": 86,
        "description": "Debate livre sobre a notícia do dia, com participação dos ouvintes.",
    },
    {
        "id": "antena1_servico_publico",
        "name": "Antena 1 — Atualidade e entrevistas",
        "station_id": "antena1",
        "days": [0, 1, 2, 3, 4],
        "start": "12:00",
        "end": "13:00",
        "presenters": "RTP / Antena 1",
        "category": "notícias/entrevistas",
        "official": False,
        "priority": 80,
        "description": "Bloco de serviço público para equilibrar a rádio com informação séria.",
    },
    {
        "id": "comercial_lunch",
        "name": "Comercial — almoço com hits",
        "station_id": "comercial",
        "days": [0, 1, 2, 3, 4],
        "start": "13:00",
        "end": "16:00",
        "presenters": "Rádio Comercial",
        "category": "música/entretenimento",
        "official": False,
        "priority": 76,
        "description": "Música comercial para manter a emissão viva durante a tarde.",
    },
    {
        "id": "tsf_tarde_news",
        "name": "TSF — atualização da tarde",
        "station_id": "tsf",
        "days": [0, 1, 2, 3, 4],
        "start": "16:00",
        "end": "16:30",
        "presenters": "Redação TSF",
        "category": "notícias",
        "official": False,
        "priority": 78,
        "description": "Meia hora para atualizar notícias antes do regresso a casa.",
    },
    {
        "id": "mega_drive",
        "name": "Drive In / Regresso jovem",
        "station_id": "mega",
        "days": [0, 1, 2, 3, 4],
        "start": "16:30",
        "end": "18:00",
        "presenters": "Mega Hits",
        "category": "jovem/música",
        "official": True,
        "priority": 74,
        "description": "Hits e energia para o regresso a casa.",
    },
    {
        "id": "rfm_drive",
        "name": "RFM — grandes músicas ao fim da tarde",
        "station_id": "rfm",
        "days": [0, 1, 2, 3, 4],
        "start": "18:00",
        "end": "19:00",
        "presenters": "RFM",
        "category": "música",
        "official": False,
        "priority": 73,
        "description": "Bloco musical forte para final do dia.",
    },
    {
        "id": "antena1_jornal_noite",
        "name": "Antena 1 — jornal e atualidade",
        "station_id": "antena1",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "19:00",
        "end": "20:00",
        "presenters": "RTP / Antena 1",
        "category": "notícias",
        "official": False,
        "priority": 82,
        "description": "Resumo sério do dia antes da noite musical.",
    },
    {
        "id": "m80_prime",
        "name": "M80 — clássicos da noite",
        "station_id": "m80",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "20:00",
        "end": "23:00",
        "presenters": "M80 Rádio",
        "category": "clássicos/música",
        "official": False,
        "priority": 71,
        "description": "Noite segura, adulta e musical com clássicos conhecidos.",
    },
    {
        "id": "rfm_noite",
        "name": "RFM — noite musical",
        "station_id": "rfm",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "23:00",
        "end": "00:00",
        "presenters": "RFM",
        "category": "música/noite",
        "official": False,
        "priority": 68,
        "description": "Fecho do dia com música mais leve.",
    },
    {
        "id": "madrugada_rfm",
        "name": "Madrugada 24/7 — RFM",
        "station_id": "rfm",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "00:00",
        "end": "06:00",
        "presenters": "RFM",
        "category": "música/madrugada",
        "official": False,
        "priority": 60,
        "description": "Música contínua para manter a emissão sempre ligada.",
    },
    {
        "id": "weekend_morning_m80",
        "name": "Fim de semana — M80 manhã",
        "station_id": "m80",
        "days": [5, 6],
        "start": "06:00",
        "end": "10:00",
        "presenters": "M80 Rádio",
        "category": "música/clássicos",
        "official": False,
        "priority": 70,
        "description": "Fim de semana com clássicos e ritmo leve.",
    },
    {
        "id": "weekend_comercial",
        "name": "Fim de semana — Comercial hits",
        "station_id": "comercial",
        "days": [5, 6],
        "start": "10:00",
        "end": "13:00",
        "presenters": "Rádio Comercial",
        "category": "música/entretenimento",
        "official": False,
        "priority": 72,
        "description": "Hits e entretenimento para meio do dia.",
    },
    {
        "id": "weekend_rfm",
        "name": "Fim de semana — RFM grandes músicas",
        "station_id": "rfm",
        "days": [5, 6],
        "start": "13:00",
        "end": "18:00",
        "presenters": "RFM",
        "category": "música",
        "official": False,
        "priority": 70,
        "description": "Tarde de fim de semana com música popular.",
    },
    {
        "id": "comercial_tnt",
        "name": "TNT — Todos no Top",
        "station_id": "comercial",
        "days": [6],
        "start": "18:00",
        "end": "20:00",
        "presenters": "Mariana Pinto e André Penim",
        "category": "top/música",
        "official": True,
        "priority": 85,
        "description": "Top semanal da Comercial ao domingo.",
    },
]

# Programas favoritos por defeito. O utilizador pode mudar no browser.
DEFAULT_FAVORITES = [
    "comercial_manhas",
    "rfm_cafe",
    "rr_tres_manha",
    "tsf_manha_jornal",
    "m80_manhas",
    "tsf_forum",
    "comercial_tnt",
]


def now_lisbon() -> datetime:
    return datetime.now(TZ)


def parse_minutes(value: str) -> int:
    hh, mm = value.split(":")
    return int(hh) * 60 + int(mm)


def is_program_active(program: Dict[str, Any], dt: datetime) -> bool:
    day = dt.weekday()
    if day not in program.get("days", []):
        return False

    now_min = dt.hour * 60 + dt.minute
    start = parse_minutes(program["start"])
    end = parse_minutes(program["end"])

    # Blocos que atravessam meia-noite, se algum for criado no futuro.
    if end == 0:
        end = 24 * 60
    if start < end:
        return start <= now_min < end
    return now_min >= start or now_min < end


def get_active_programs(dt: Optional[datetime] = None) -> List[Dict[str, Any]]:
    dt = dt or now_lisbon()
    active = [p for p in PROGRAMS if is_program_active(p, dt)]
    active.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return [enrich_program(p) for p in active]


def enrich_program(program: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(program)
    st = STATIONS.get(p["station_id"], {})
    p["station"] = {
        "id": st.get("id"),
        "name": st.get("name"),
        "brand": st.get("brand"),
        "kind": st.get("kind"),
        "color": st.get("color"),
        "site": st.get("site"),
    }
    return p


def program_sort_key(program: Dict[str, Any]) -> tuple:
    return (program.get("days", [0])[0], parse_minutes(program["start"]), program.get("priority", 0))


def test_stream_url(url: str) -> bool:
    try:
        headers = {"User-Agent": USER_AGENT, "Range": "bytes=0-2048"}
        r = requests.get(url, headers=headers, timeout=(3, 6), stream=True, allow_redirects=True)
        try:
            # 2xx/3xx: OK. 4xx não deve ser aceite, senão o browser tenta tocar uma página de erro.
            status_ok = 200 <= r.status_code < 400
            ctype = (r.headers.get("Content-Type") or "").lower()
            # Muitos streams têm content-type errado, por isso aceitamos status OK + extensão conhecida.
            audioish = any(
                part in ctype
                for part in [
                    "audio",
                    "mpegurl",
                    "mpeg",
                    "aac",
                    "mp3",
                    "octet-stream",
                    "application/vnd.apple.mpegurl",
                ]
            )
            return bool(status_ok and (audioish or url.lower().endswith((".mp3", ".m3u8", ".aac"))))
        finally:
            r.close()
    except Exception:
        return False


@lru_cache(maxsize=128)
def radio_browser_search(term: str) -> List[str]:
    urls: List[str] = []
    hosts = [
        "https://de1.api.radio-browser.info",
        "https://nl1.api.radio-browser.info",
        "https://at1.api.radio-browser.info",
    ]
    params = {
        "name": term,
        "countrycode": "PT",
        "hidebroken": "true",
        "limit": 8,
        "order": "votes",
        "reverse": "true",
    }
    for host in hosts:
        try:
            res = requests.get(
                f"{host}/json/stations/search",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=(4, 8),
            )
            if not res.ok:
                continue
            data = res.json()
            for item in data:
                url = item.get("url_resolved") or item.get("url")
                if url and url not in urls:
                    urls.append(url)
            if urls:
                break
        except Exception:
            continue
    return urls


@lru_cache(maxsize=64)
def resolve_stream_cached(station_id: str, cache_bucket: int) -> Dict[str, Any]:
    station = STATIONS.get(station_id)
    if not station:
        return {"ok": False, "error": "Estação desconhecida."}

    checked: List[str] = []
    for url in station.get("streams", []):
        checked.append(url)
        if test_stream_url(url):
            return {
                "ok": True,
                "station_id": station_id,
                "station": public_station(station),
                "url": url,
                "source": "candidate",
                "candidates": unique_urls([url] + station.get("streams", [])),
                "checked": checked,
            }

    for term in station.get("search_terms", []):
        for url in radio_browser_search(term):
            if url in checked:
                continue
            checked.append(url)
            if test_stream_url(url):
                return {
                    "ok": True,
                    "station_id": station_id,
                    "station": public_station(station),
                    "url": url,
                    "source": f"radio-browser: {term}",
                    "candidates": unique_urls([url] + station.get("streams", []) + checked[-10:]),
                    "checked": checked[-10:],
                }

    # Último recurso: devolver o primeiro candidato mesmo sem conseguir validar.
    fallback = station.get("streams", [None])[0]
    return {
        "ok": bool(fallback),
        "station_id": station_id,
        "station": public_station(station),
        "url": fallback,
        "source": "fallback-unverified",
        "candidates": unique_urls(station.get("streams", []) + checked[-10:]),
        "warning": "Não consegui validar o stream agora; devolvi o primeiro candidato.",
        "checked": checked[-10:],
    }


def public_station(station: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": station["id"],
        "name": station["name"],
        "brand": station["brand"],
        "kind": station["kind"],
        "color": station["color"],
        "site": station["site"],
        # Exposto ao frontend de propósito: assim o botão Ativar toca imediatamente
        # sem esperar validações lentas do servidor/Vercel.
        "streams": unique_urls(station.get("streams", [])),
    }


def unique_urls(urls: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    n = now_lisbon()
    return jsonify(
        {
            "ok": True,
            "app": "Rádio Supremo 24/7",
            "time_lisbon": n.isoformat(),
            "stations": len(STATIONS),
            "programs": len(PROGRAMS),
        }
    )


@app.get("/api/config")
def config():
    n = now_lisbon()
    return jsonify(
        {
            "ok": True,
            "timezone": "Europe/Lisbon",
            "server_time": n.isoformat(),
            "stations": [public_station(s) for s in STATIONS.values()],
            "programs": [enrich_program(p) for p in sorted(PROGRAMS, key=program_sort_key)],
            "default_favorites": DEFAULT_FAVORITES,
            "legal_note": "A app toca streams oficiais/diretos no browser. Não grava, não retransmite e não redistribui áudio.",
        }
    )


@app.get("/api/now")
def api_now():
    n = now_lisbon()
    active = get_active_programs(n)
    return jsonify(
        {
            "ok": True,
            "time_lisbon": n.isoformat(),
            "weekday": n.weekday(),
            "active": active,
            "recommended": active[0] if active else None,
        }
    )


@app.get("/api/stream/<station_id>")
def stream(station_id: str):
    station = STATIONS.get(station_id)
    if not station:
        return jsonify({"ok": False, "error": "Estação desconhecida."}), 404

    # O botão Ativar não pode ficar preso a validar streams no servidor.
    # Por defeito devolvemos logo os candidatos e o browser tenta tocar.
    # Para diagnóstico manual, usar /api/stream/<id>?validate=1.
    if request.args.get("validate") == "1":
        cache_bucket = int(time.time() // 600)
        return jsonify(resolve_stream_cached(station_id, cache_bucket))

    candidates = unique_urls(station.get("streams", []))
    return jsonify({
        "ok": bool(candidates),
        "station_id": station_id,
        "station": public_station(station),
        "url": candidates[0] if candidates else None,
        "candidates": candidates,
        "source": "direct-candidates-no-server-validation",
        "note": "O frontend tenta os candidatos diretamente para evitar timeouts no Vercel.",
    })


@app.get("/api/station/<station_id>")
def station(station_id: str):
    st = STATIONS.get(station_id)
    if not st:
        return jsonify({"ok": False, "error": "Estação desconhecida."}), 404
    return jsonify({"ok": True, "station": public_station(st)})


@app.get("/api/test-streams")
def test_streams():
    """Diagnóstico rápido: devolve o primeiro candidato validado para cada estação."""
    cache_bucket = int(time.time() // 60)
    results = []
    for station_id in STATIONS:
        data = resolve_stream_cached(station_id, cache_bucket)
        results.append({
            "station_id": station_id,
            "station": STATIONS[station_id]["name"],
            "ok": bool(data.get("ok")),
            "source": data.get("source"),
            "url": data.get("url"),
            "warning": data.get("warning"),
            "checked": data.get("checked", []),
        })
    return jsonify({"ok": True, "results": results})


@app.errorhandler(404)
def not_found(_):
    # Permite refresh em rotas futuras de SPA.
    return render_template("index.html"), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
