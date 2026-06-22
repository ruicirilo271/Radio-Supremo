# -*- coding: utf-8 -*-
"""
Rádio Supremo 24/7 — Flask + Vercel
Toca streams oficiais/diretos no browser e muda automaticamente conforme a grelha.
Não grava, não retransmite e não faz proxy permanente de áudio.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

import asyncio
import json
import os
import re
import tempfile
import time
import requests
from flask import Flask, jsonify, render_template, request, send_from_directory, make_response

API_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(API_DIR)
BASE_DIR = ROOT_DIR

# No Vercel, os ficheiros dentro de /api entram sempre no bundle da função.
# Por isso usamos /api/templates e /api/static como fonte principal.
app = Flask(
    __name__,
    template_folder=os.path.join(API_DIR, "templates"),
    static_folder=None,
)

TZ = ZoneInfo("Europe/Lisbon")
USER_AGENT = "Mozilla/5.0 RadioSupremo24-7/2.0 (+https://vercel.app)"


def _static_dir() -> str:
    primary = os.path.join(API_DIR, "static")
    fallback = os.path.join(ROOT_DIR, "static")
    return primary if os.path.isdir(primary) else fallback


@app.get("/static/<path:filename>", endpoint="static")
def static_files(filename: str):
    # Servir CSS/JS pela própria app evita que o Vercel ignore a pasta /static.
    resp = make_response(send_from_directory(_static_dir(), filename))
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp


@app.get("/api/static-check")
def static_check():
    static_dir = _static_dir()
    files = sorted(os.listdir(static_dir)) if os.path.isdir(static_dir) else []
    return jsonify({
        "ok": True,
        "static_dir": static_dir,
        "files": files,
        "style_exists": os.path.exists(os.path.join(static_dir, "style.css")),
        "script_exists": os.path.exists(os.path.join(static_dir, "script.js")),
    })

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
            "https://stream-icy.bauermedia.pt/comercial.mp3",
            "https://stream-icy.bauermedia.pt/comercial.aac",
            "https://stream-hls.bauermedia.pt/comercial.aac/playlist.m3u8",
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
            "https://stream-icy.bauermedia.pt/m80.mp3",
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
            "https://stream-icy.bauermedia.pt/cidade.mp3",
            "https://stream-icy.bauermedia.pt/cidade.aac",
            "https://stream-hls.bauermedia.pt/cidade.aac/playlist.m3u8",
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


def load_programacao_file() -> None:
    """Carrega a grelha editável a partir de api/programacao.json, se existir.

    Isto permite editar a programação no GitHub/Vercel sem mexer no código Python.
    No browser também há import/export por ficheiro JSON, guardado em localStorage.
    """
    global PROGRAMS, DEFAULT_FAVORITES
    path = os.path.join(API_DIR, "programacao.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        programs = data.get("programs")
        favorites = data.get("default_favorites")
        if isinstance(programs, list) and programs:
            PROGRAMS = programs
        if isinstance(favorites, list):
            DEFAULT_FAVORITES = favorites
    except Exception as exc:
        print(f"[programacao.json] Não foi possível carregar: {exc}")


load_programacao_file()


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


# Cache simples em memória para não chamar o Shazam vezes a mais quando o utilizador
# carrega várias vezes seguidas no botão. Em Vercel isto pode desaparecer entre invocações.
IDENTIFY_CACHE: Dict[str, Dict[str, Any]] = {}


def _safe_seconds(value: Any, default: int = 18) -> int:
    try:
        n = int(value)
    except Exception:
        n = default
    return max(8, min(n, 60))


def _guess_audio_ext(url: str, content_type: str = "") -> str:
    lower = (url or "").lower().split("?")[0]
    ctype = (content_type or "").lower()
    if ".mp3" in lower or "mpeg" in ctype or "mp3" in ctype:
        return ".mp3"
    if ".m4a" in lower or "mp4" in ctype:
        return ".m4a"
    if ".aac" in lower or "aac" in ctype:
        return ".aac"
    if ".ts" in lower or "video/mp2t" in ctype:
        return ".ts"
    return ".aac"


def _tmp_audio_file(ext: str) -> str:
    fd, path = tempfile.mkstemp(prefix="radio_supremo_shazam_", suffix=ext, dir="/tmp")
    os.close(fd)
    return path


def _is_hls_url(url: str) -> bool:
    return ".m3u8" in (url or "").lower() or "mpegurl" in (url or "").lower()


def _read_hls_playlist(url: str) -> Tuple[str, str]:
    res = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.apple.mpegurl,*/*"},
        timeout=(5, 9),
        allow_redirects=True,
    )
    res.raise_for_status()
    return res.text, res.url


def _hls_media_playlist(url: str, depth: int = 0) -> Tuple[str, str]:
    text, final_url = _read_hls_playlist(url)
    if depth > 3:
        return text, final_url

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            for nxt in lines[i + 1:]:
                if nxt and not nxt.startswith("#"):
                    return _hls_media_playlist(urljoin(final_url, nxt), depth + 1)
    return text, final_url


def _record_hls_sample(url: str, seconds: int, max_bytes: int = 4_800_000) -> Tuple[str, int, str]:
    text, base_url = _hls_media_playlist(url)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    segments: List[Tuple[str, float]] = []
    last_duration = 4.0

    for line in lines:
        if line.startswith("#EXTINF"):
            m = re.search(r"#EXTINF:([0-9.]+)", line)
            if m:
                try:
                    last_duration = float(m.group(1))
                except Exception:
                    last_duration = 4.0
            continue
        if line.startswith("#"):
            continue
        segments.append((urljoin(base_url, line), last_duration))

    if not segments:
        raise RuntimeError("playlist HLS sem segmentos de áudio")

    # Em live HLS os últimos segmentos são normalmente os mais recentes.
    selected_count = max(8, min(len(segments), int(seconds / max(last_duration, 1.0)) + 4))
    selected = segments[-selected_count:]
    path = _tmp_audio_file(_guess_audio_ext(selected[-1][0], "video/mp2t"))
    total = 0
    total_duration = 0.0

    with open(path, "wb") as out:
        for seg_url, duration in selected:
            res = requests.get(
                seg_url,
                headers={"User-Agent": USER_AGENT, "Accept": "audio/*,video/*,*/*"},
                timeout=(5, 12),
                stream=True,
                allow_redirects=True,
            )
            try:
                if res.status_code >= 400:
                    continue
                for chunk in res.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    out.write(chunk)
                    total += len(chunk)
                    if total >= max_bytes:
                        break
                total_duration += duration
            finally:
                res.close()
            if total >= max_bytes or total_duration >= seconds:
                break

    if total < 35_000:
        raise RuntimeError(f"amostra HLS demasiado pequena: {total} bytes")
    return path, total, "hls"


def _record_direct_sample(url: str, seconds: int, max_bytes: int = 4_800_000) -> Tuple[str, int, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "audio/aac,audio/mpeg,audio/*,*/*",
        "Icy-MetaData": "0",
        "Connection": "close",
    }
    res = requests.get(url, headers=headers, timeout=(5, min(seconds + 12, 58)), stream=True, allow_redirects=True)
    try:
        if res.status_code >= 400:
            raise RuntimeError(f"HTTP {res.status_code}")
        content_type = res.headers.get("Content-Type", "")
        if "text/html" in content_type.lower():
            raise RuntimeError("o stream devolveu HTML em vez de áudio")

        path = _tmp_audio_file(_guess_audio_ext(res.url or url, content_type))
        total = 0
        start = time.monotonic()
        with open(path, "wb") as out:
            for chunk in res.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                out.write(chunk)
                total += len(chunk)
                if total >= max_bytes or (time.monotonic() - start) >= seconds:
                    break
    finally:
        res.close()

    if total < 35_000:
        raise RuntimeError(f"amostra direta demasiado pequena: {total} bytes")
    return path, total, "direct"


def _station_identification_candidates(station: Dict[str, Any]) -> List[str]:
    # Primeiro os diretos configurados. Depois tentamos resolver via Radio Browser.
    candidates = unique_urls(station.get("streams", []))
    for term in station.get("search_terms", [])[:2]:
        try:
            candidates.extend(radio_browser_search(term)[:4])
        except Exception:
            pass
    return unique_urls(candidates)


def record_station_sample(station: Dict[str, Any], seconds: int = 18) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    candidates = _station_identification_candidates(station)
    if not candidates:
        raise RuntimeError("esta estação não tem streams configurados")

    # Para identificar, preferimos MP3 direto, depois AAC direto. HLS fica como recurso final.
    def _candidate_score(u: str) -> int:
        lu = u.lower()
        if _is_hls_url(u):
            return 50
        if ".mp3" in lu or "_sc" in lu:
            return 0
        if ".aac" in lu:
            return 10
        return 20

    ordered = sorted(candidates, key=_candidate_score)

    for url in ordered:
        try:
            if _is_hls_url(url):
                path, size, mode = _record_hls_sample(url, seconds)
            else:
                path, size, mode = _record_direct_sample(url, seconds)
            return {"ok": True, "path": path, "bytes": size, "source_url": url, "mode": mode}
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)[:180]})
            continue

    raise RuntimeError("não consegui gravar amostra de nenhum stream", errors)


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


def _extract_shazam_track(out: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    track = (out or {}).get("track") or {}
    if not track:
        return None

    images = track.get("images") or {}
    sections = track.get("sections") or []
    album = None
    label = None
    released = None
    genres: List[str] = []

    for section in sections:
        for meta in section.get("metadata", []) or []:
            title = str(meta.get("title", "")).strip().lower()
            text = meta.get("text")
            if title == "album" and text:
                album = text
            elif title in {"label", "gravadora"} and text:
                label = text
            elif title in {"released", "lançamento", "release date"} and text:
                released = text
        if section.get("type") == "SONG" and section.get("tabname"):
            pass

    for genre in track.get("genres", {}).values() if isinstance(track.get("genres"), dict) else []:
        if genre and genre not in genres:
            genres.append(genre)

    return {
        "title": track.get("title"),
        "artist": track.get("subtitle"),
        "album": album,
        "label": label,
        "released": released,
        "genres": genres,
        "shazam_key": track.get("key"),
        "shazam_url": track.get("url"),
        "cover": images.get("coverarthq") or images.get("coverart") or images.get("background"),
        "raw_subject": track.get("share", {}).get("subject") if isinstance(track.get("share"), dict) else None,
    }


def identify_with_shazam(sample_path: str) -> Dict[str, Any]:
    try:
        from shazamio import Shazam
    except Exception as exc:
        return {
            "ok": False,
            "error": "ShazamIO não está instalado. Confirma se o requirements.txt foi publicado no Vercel.",
            "technical": str(exc),
        }

    async def _recognize():
        shazam = Shazam()
        return await shazam.recognize(sample_path)

    try:
        out = _run_async(_recognize())
    except Exception as exc:
        return {"ok": False, "error": "O Shazam não conseguiu analisar a amostra.", "technical": str(exc)}

    track = _extract_shazam_track(out)
    if not track or not track.get("title"):
        return {"ok": False, "error": "O Shazam não reconheceu música nesta amostra.", "raw_keys": list((out or {}).keys())}

    return {"ok": True, "track": track}


def _cache_key(station_id: str, seconds: int) -> str:
    bucket = int(time.time() // 75)
    return f"{station_id}:{seconds}:{bucket}"


def identify_station(station_id: str, seconds: int = 18, force: bool = False) -> Dict[str, Any]:
    station = STATIONS.get(station_id)
    if not station:
        return {"ok": False, "error": "Estação desconhecida."}

    key = _cache_key(station_id, seconds)
    if not force and key in IDENTIFY_CACHE:
        cached = dict(IDENTIFY_CACHE[key])
        cached["cached"] = True
        return cached

    sample_path = None
    try:
        sample = record_station_sample(station, seconds=seconds)
        sample_path = sample.get("path")
        result = identify_with_shazam(sample_path)
        payload = {
            "ok": bool(result.get("ok")),
            "station_id": station_id,
            "station": public_station(station),
            "recorded_bytes": sample.get("bytes"),
            "sample_mode": sample.get("mode"),
            "source_url": sample.get("source_url"),
            "seconds": seconds,
            "time_lisbon": now_lisbon().isoformat(),
        }
        if result.get("ok"):
            payload["track"] = result.get("track")
        else:
            payload["error"] = result.get("error")
            payload["technical"] = result.get("technical")
            payload["raw_keys"] = result.get("raw_keys")
        IDENTIFY_CACHE[key] = payload
        return payload
    except Exception as exc:
        details = None
        if len(getattr(exc, "args", [])) > 1:
            details = exc.args[1]
        return {
            "ok": False,
            "station_id": station_id,
            "station": public_station(station),
            "error": str(exc.args[0] if getattr(exc, "args", None) else exc),
            "details": details,
            "seconds": seconds,
            "time_lisbon": now_lisbon().isoformat(),
        }
    finally:
        if sample_path:
            try:
                os.remove(sample_path)
            except Exception:
                pass


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




@app.get("/api/programacao")
def programacao_json():
    return jsonify({
        "ok": True,
        "schema": "radio_supremo_programacao_v1",
        "name": "Rádio Supremo 24/7 — Programação",
        "timezone": "Europe/Lisbon",
        "days_reference": "0=segunda, 1=terça, 2=quarta, 3=quinta, 4=sexta, 5=sábado, 6=domingo",
        "default_favorites": DEFAULT_FAVORITES,
        "programs": [enrich_program(p) for p in sorted(PROGRAMS, key=program_sort_key)],
    })

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


@app.get("/api/identify/<station_id>")
def api_identify_station(station_id: str):
    """Grava uma pequena amostra do stream e envia para reconhecimento ShazamIO."""
    seconds = _safe_seconds(request.args.get("seconds"), 18)
    force = request.args.get("force") == "1"
    data = identify_station(station_id, seconds=seconds, force=force)
    status = 200 if data.get("ok") else 200
    return jsonify(data), status


@app.get("/api/identify")
def api_identify_current():
    station_id = request.args.get("station_id", "").strip()
    if not station_id:
        active = get_active_programs(now_lisbon())
        station_id = active[0]["station_id"] if active else "rfm"
    seconds = _safe_seconds(request.args.get("seconds"), 18)
    force = request.args.get("force") == "1"
    data = identify_station(station_id, seconds=seconds, force=force)
    status = 200 if data.get("ok") else 200
    return jsonify(data), status


@app.get("/api/test-shazam")
def test_shazam():
    try:
        import shazamio  # type: ignore
        version = getattr(shazamio, "__version__", "instalado")
        return jsonify({"ok": True, "shazamio": version})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "hint": "Confirma shazamio==0.8.1 no requirements.txt"})


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
