/* Rádio Supremo 24/7 — versão botão/som corrigidos */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  config: null,
  stations: [],
  programs: [],
  favorites: new Set(),
  currentProgram: null,
  currentStationId: null,
  desiredStationId: null,
  userStarted: false,
  hls: null,
  lastSwitchKey: "",
  switching: false,
  lastAudioErrorRetryAt: 0,
};

const els = {
  audio: $("#audio"),
  clock: $("#clock"),
  startAuto: $("#startAuto"),
  stopBtn: $("#stopBtn"),
  nextBest: $("#nextBest"),
  dockPlay: $("#dockPlay"),
  dockAuto: $("#dockAuto"),
  autoSwitch: $("#autoSwitch"),
  favoritesOnly: $("#favoritesOnly"),
  newsBoost: $("#newsBoost"),
  volume: $("#volume"),
  nowProgram: $("#nowProgram"),
  nowStation: $("#nowStation"),
  currentTitle: $("#currentTitle"),
  currentDesc: $("#currentDesc"),
  currentStation: $("#currentStation"),
  currentTime: $("#currentTime"),
  currentHosts: $("#currentHosts"),
  currentCategory: $("#currentCategory"),
  dockTitle: $("#dockTitle"),
  dockSub: $("#dockSub"),
  coverOrb: $("#coverOrb"),
  stations: $("#stations"),
  schedule: $("#schedule"),
  upNext: $("#upNext"),
  favCurrent: $("#favCurrent"),
  toast: $("#toast"),
  meters: $("#meters"),
  dockSpectrum: $("#dockSpectrum"),
};

function pad(n) { return String(n).padStart(2, "0"); }
function nowLisbon() {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Lisbon" }));
}
function minutes(t) {
  const [h, m] = String(t || "00:00").split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}
function dayName(i) { return ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][i] || "Dia"; }
function timeRange(p) { return `${p.start}–${p.end}`; }
function stationById(id) { return state.stations.find(s => s.id === id); }
function unique(arr) { return Array.from(new Set((arr || []).filter(Boolean))); }

function toast(msg, type = "") {
  if (!els.toast) return;
  els.toast.textContent = msg;
  els.toast.className = `toast show ${type}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { els.toast.className = "toast"; }, 3600);
}

function storageGet(key, fallback = null) {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch {}
}

function saveSettings() {
  storageSet("radioSupremo.favorites", JSON.stringify([...state.favorites]));
  storageSet("radioSupremo.autoSwitch", els.autoSwitch.checked ? "1" : "0");
  storageSet("radioSupremo.favoritesOnly", els.favoritesOnly.checked ? "1" : "0");
  storageSet("radioSupremo.newsBoost", els.newsBoost.checked ? "1" : "0");
  storageSet("radioSupremo.volume", String(els.volume.value));
}

function loadSettings() {
  const favRaw = storageGet("radioSupremo.favorites");
  if (favRaw) {
    try { state.favorites = new Set(JSON.parse(favRaw)); } catch { state.favorites = new Set(); }
  } else {
    state.favorites = new Set(state.config.default_favorites || []);
  }
  els.autoSwitch.checked = storageGet("radioSupremo.autoSwitch", "1") !== "0";
  els.favoritesOnly.checked = storageGet("radioSupremo.favoritesOnly", "0") === "1";
  els.newsBoost.checked = storageGet("radioSupremo.newsBoost", "1") !== "0";
  els.volume.value = storageGet("radioSupremo.volume", "0.82");
  els.audio.volume = Number(els.volume.value);
  els.dockAuto.classList.toggle("active", els.autoSwitch.checked);
}

function isActive(program, dt = nowLisbon()) {
  const day = (dt.getDay() + 6) % 7;
  if (!program.days.includes(day)) return false;
  const nowM = dt.getHours() * 60 + dt.getMinutes();
  const start = minutes(program.start);
  let end = minutes(program.end);
  if (end === 0) end = 24 * 60;
  return start <= nowM && nowM < end;
}

function scoreProgram(program) {
  let score = program.priority || 0;
  if (state.favorites.has(program.id)) score += 60;
  if (els.newsBoost.checked && ["notícias", "debate/notícias", "notícias/entrevistas", "humor/notícias"].includes(program.category)) score += 18;
  if (els.favoritesOnly.checked && !state.favorites.has(program.id)) score -= 25;
  return score;
}

function getActivePrograms(dt = nowLisbon()) {
  return state.programs.filter(p => isActive(p, dt)).sort((a, b) => scoreProgram(b) - scoreProgram(a));
}

function getRecommendedProgram() {
  const active = getActivePrograms();
  if (!active.length) return null;
  if (els.favoritesOnly.checked) {
    const fav = active.find(p => state.favorites.has(p.id));
    if (fav) return fav;
  }
  return active[0];
}

function getNextPrograms(limit = 6) {
  const now = nowLisbon();
  const currentDay = (now.getDay() + 6) % 7;
  const nowM = now.getHours() * 60 + now.getMinutes();
  const items = [];

  for (let offset = 0; offset < 8; offset++) {
    const day = (currentDay + offset) % 7;
    for (const p of state.programs) {
      if (!p.days.includes(day)) continue;
      const startM = minutes(p.start);
      if (offset === 0 && startM <= nowM) continue;
      items.push({ ...p, day, offset, sort: offset * 1440 + startM });
    }
  }
  return items.sort((a, b) => a.sort - b.sort).slice(0, limit);
}

function setStationTheme(station) {
  if (!station) return;
  document.documentElement.style.setProperty("--station", station.color || "#ffcc66");
  if (els.coverOrb) els.coverOrb.style.boxShadow = `0 0 35px ${station.color || "#ffcc66"}`;
}

function updateClock() {
  const dt = nowLisbon();
  els.clock.textContent = `${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
}

function renderStations() {
  els.stations.innerHTML = state.stations.map(s => `
    <button class="stationBtn" data-station="${s.id}" style="--s:${s.color}">
      <span class="stationLogo">${s.brand.split(" ").map(x => x[0]).join("").slice(0, 3)}</span>
      <strong>${s.name}</strong>
      <small>${s.kind}</small>
    </button>
  `).join("");

  $$(".stationBtn").forEach(btn => {
    btn.addEventListener("click", async () => {
      state.userStarted = true;
      await switchToStation(btn.dataset.station, "Escolha manual");
    });
  });
}

function renderSchedule() {
  const grouped = new Map();
  for (const p of state.programs) {
    const days = p.days.join(",");
    const key = days === "0,1,2,3,4" ? "Seg–Sex" :
                days === "5,6" ? "Fim de semana" :
                days === "0,1,2,3,4,5,6" ? "Todos os dias" :
                p.days.map(dayName).join(", ");
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(p);
  }

  els.schedule.innerHTML = [...grouped.entries()].map(([group, programs]) => `
    <div class="dayBlock">
      <h3>${group}</h3>
      ${programs.map(p => {
        const st = stationById(p.station_id) || p.station || {};
        const fav = state.favorites.has(p.id);
        return `
          <div class="programRow ${isActive(p) ? "active" : ""}" style="--s:${st.color || "#ffcc66"}">
            <button class="favBtn ${fav ? "on" : ""}" data-program="${p.id}" title="Favorito">${fav ? "★" : "☆"}</button>
            <div class="programTime">${timeRange(p)}</div>
            <div class="programMain">
              <strong>${p.name}</strong>
              <span>${st.name || ""} · ${p.category} · ${p.presenters || "—"}</span>
            </div>
            <em>${p.official ? "programa" : "curadoria"}</em>
          </div>
        `;
      }).join("")}
    </div>
  `).join("");

  $$(".favBtn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.program;
      if (state.favorites.has(id)) state.favorites.delete(id);
      else state.favorites.add(id);
      saveSettings();
      renderSchedule();
      updateNowUI();
    });
  });
}

function renderUpNext() {
  const next = getNextPrograms(6);
  els.upNext.innerHTML = next.map(p => {
    const st = stationById(p.station_id) || p.station || {};
    return `
      <div class="nextItem" style="--s:${st.color || "#ffcc66"}">
        <b>${p.offset === 0 ? "Hoje" : dayName(p.day)} · ${p.start}</b>
        <strong>${p.name}</strong>
        <span>${st.name || ""}</span>
      </div>
    `;
  }).join("");
}

function updateNowUI() {
  const program = getRecommendedProgram();
  const active = getActivePrograms();
  state.currentProgram = program;

  if (!program) {
    els.nowProgram.textContent = "Sem bloco ativo";
    els.nowStation.textContent = "A grelha está vazia neste momento";
    return;
  }

  const st = stationById(program.station_id) || program.station || {};
  setStationTheme(st);

  els.nowProgram.textContent = program.name;
  els.nowStation.textContent = `${st.name || ""} · ${program.category}`;
  els.currentTitle.textContent = program.name;
  els.currentDesc.textContent = program.description || "—";
  els.currentStation.textContent = st.name || "—";
  els.currentTime.textContent = `${timeRange(program)} · ${program.days.map(dayName).join(", ")}`;
  els.currentHosts.textContent = program.presenters || "—";
  els.currentCategory.textContent = program.category || "—";
  els.dockTitle.textContent = st.name || "Rádio Supremo";
  els.dockSub.textContent = `${program.name} · ${timeRange(program)}`;
  els.coverOrb.textContent = (st.brand || "RS").slice(0, 3).toUpperCase();
  els.favCurrent.textContent = state.favorites.has(program.id) ? "★ favorito" : "☆ favorito";

  renderUpNext();
  if (active.length > 1) {
    els.nowStation.title = "Outros ativos: " + active.slice(1).map(p => p.name).join(", ");
  }
}

function getStationCandidates(station) {
  // Usa primeiro os streams já vindos de /api/config para tocar dentro do clique do utilizador.
  // Isto evita que o browser bloqueie play() por a ativação do clique expirar durante um fetch lento.
  return unique(station.streams || []);
}

async function fetchServerCandidates(stationId) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch(`/api/stream/${encodeURIComponent(stationId)}?t=${Date.now()}`, { signal: controller.signal });
    const data = await res.json();
    if (!data.ok) return [];
    return unique([data.url, ...(data.candidates || [])]);
  } catch (err) {
    console.warn("Não consegui obter candidatos do servidor", err);
    return [];
  } finally {
    clearTimeout(timer);
  }
}

async function switchToStation(stationId, reason = "Auto") {
  const station = stationById(stationId);
  if (!station || state.switching) return;

  state.switching = true;
  state.desiredStationId = stationId;
  setStationTheme(station);
  setBusy(true, `A ligar ${station.name}...`);
  toast(`A ligar ${station.name}...`);

  try {
    let candidates = getStationCandidates(station);
    const serverCandidatesPromise = fetchServerCandidates(stationId);

    if (!candidates.length) {
      candidates = await serverCandidatesPromise;
    } else {
      // Junta candidatos extra sem bloquear o primeiro play.
      serverCandidatesPromise.then(extra => { station.streams = unique([...station.streams, ...extra]); });
    }

    if (!candidates.length) throw new Error("Sem streams configurados para esta estação");

    let lastError = null;
    for (const candidate of candidates) {
      try {
        await loadAudioUrl(candidate);
        state.currentStationId = stationId;
        els.dockTitle.textContent = station.name;
        els.dockSub.textContent = `${reason} · ${candidate.includes("m3u8") ? "HLS" : "stream direto"}`;
        els.dockPlay.textContent = "⏸";
        toast(`Agora a tocar: ${station.name}`, "ok");
        return;
      } catch (playErr) {
        console.warn("Falhou stream candidato", candidate, playErr);
        lastError = playErr;
      }
    }

    // Segunda tentativa com candidatos do servidor, caso sejam diferentes.
    const extraCandidates = unique([...(await serverCandidatesPromise), ...getStationCandidates(station)]);
    for (const candidate of extraCandidates) {
      if (candidates.includes(candidate)) continue;
      try {
        await loadAudioUrl(candidate);
        state.currentStationId = stationId;
        els.dockTitle.textContent = station.name;
        els.dockSub.textContent = `${reason} · stream alternativo`;
        els.dockPlay.textContent = "⏸";
        toast(`Agora a tocar: ${station.name}`, "ok");
        return;
      } catch (playErr) {
        console.warn("Falhou stream alternativo", candidate, playErr);
        lastError = playErr;
      }
    }

    throw lastError || new Error("Nenhum stream tocou no browser");
  } catch (err) {
    console.error(err);
    els.dockPlay.textContent = "▶";
    toast(`Não consegui tocar ${station.name}. Experimenta outro botão/estação.`, "bad");
  } finally {
    setBusy(false);
    state.switching = false;
  }
}

function setBusy(isBusy, text = "") {
  [els.startAuto, els.nextBest].forEach(btn => {
    if (!btn) return;
    btn.disabled = isBusy;
    btn.classList.toggle("busy", isBusy);
  });
  if (isBusy && text) els.dockSub.textContent = text;
}

function waitForMediaEvent(audio, okEvents = ["playing", "canplay", "loadeddata"], timeoutMs = 5500) {
  return new Promise((resolve, reject) => {
    let done = false;
    const clean = () => {
      okEvents.forEach(ev => audio.removeEventListener(ev, onOk));
      audio.removeEventListener("error", onErr);
      clearTimeout(timer);
    };
    const finish = (fn, value) => {
      if (done) return;
      done = true;
      clean();
      fn(value);
    };
    const onOk = () => finish(resolve, true);
    const onErr = () => finish(reject, new Error("Erro do elemento áudio"));
    const timer = setTimeout(() => finish(resolve, true), timeoutMs); // live streams às vezes não disparam eventos, mas estão a tocar
    okEvents.forEach(ev => audio.addEventListener(ev, onOk, { once: true }));
    audio.addEventListener("error", onErr, { once: true });
  });
}

function canPlayDirect(url) {
  const lower = url.toLowerCase();
  if (lower.includes(".m3u8")) {
    return els.audio.canPlayType("application/vnd.apple.mpegurl") || els.audio.canPlayType("application/x-mpegURL");
  }
  return true;
}

function waitForHlsReady(hls, timeoutMs = 7000) {
  return new Promise((resolve, reject) => {
    let done = false;
    const timer = setTimeout(() => finish(reject, new Error("Timeout HLS")), timeoutMs);
    const finish = (fn, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      hls.off(Hls.Events.MANIFEST_PARSED, onManifest);
      hls.off(Hls.Events.ERROR, onError);
      fn(value);
    };
    const onManifest = () => finish(resolve, true);
    const onError = (_event, data) => {
      if (data && data.fatal) finish(reject, new Error(data.details || "Erro fatal HLS"));
    };
    hls.on(Hls.Events.MANIFEST_PARSED, onManifest);
    hls.on(Hls.Events.ERROR, onError);
  });
}

async function loadAudioUrl(url) {
  const lower = url.toLowerCase();
  const isHls = lower.includes(".m3u8") || lower.includes("mpegurl");

  if (state.hls) {
    state.hls.destroy();
    state.hls = null;
  }

  els.audio.pause();
  els.audio.removeAttribute("src");
  els.audio.load();
  els.audio.muted = false;
  els.audio.volume = Number(els.volume.value || 0.82);

  if (isHls && window.Hls && Hls.isSupported()) {
    state.hls = new Hls({
      lowLatencyMode: true,
      liveDurationInfinity: true,
      enableWorker: true,
      maxBufferLength: 20,
    });
    state.hls.attachMedia(els.audio);
    state.hls.loadSource(url);
    await waitForHlsReady(state.hls, 7000);
  } else if (isHls && !canPlayDirect(url)) {
    throw new Error("Este browser precisa do Hls.js para este stream HLS");
  } else {
    els.audio.src = url;
    els.audio.load();
  }

  const playPromise = els.audio.play();
  if (playPromise) await playPromise;
  await waitForMediaEvent(els.audio, ["playing", "canplay", "loadeddata"], 5500);

  // Importante: não usar createMediaElementSource aqui.
  // Web Audio API + streams externos sem CORS pode silenciar o áudio.
}

async function playRecommended(force = false) {
  updateNowUI();
  let rec = state.currentProgram || getRecommendedProgram();
  if (!rec) {
    rec = { station_id: state.stations[0]?.id || "rfm", name: "Emissão contínua" };
  }
  const switchKey = `${rec.id || rec.station_id}-${rec.station_id}-${rec.start || ""}-${rec.end || ""}`;
  state.lastSwitchKey = switchKey;
  await switchToStation(rec.station_id, force ? `Auto · ${rec.name}` : `Recomendado · ${rec.name}`);
}

function schedulerTick(force = false) {
  updateClock();
  updateNowUI();

  const rec = state.currentProgram;
  if (!rec) return;
  const switchKey = `${rec.id}-${rec.station_id}-${rec.start}-${rec.end}`;

  if (els.autoSwitch.checked && state.userStarted) {
    const shouldSwitch = force || state.currentStationId !== rec.station_id || state.lastSwitchKey !== switchKey;
    if (shouldSwitch && !state.switching) {
      state.lastSwitchKey = switchKey;
      switchToStation(rec.station_id, `Auto · ${rec.name}`);
    }
  }
}

function initBars() {
  const bars = Array.from({ length: 42 }, (_, i) => `<i style="--i:${i}"></i>`).join("");
  els.meters.innerHTML = bars;
  els.dockSpectrum.innerHTML = bars;
}

function animateSpectrum() {
  const bars = [...els.meters.querySelectorAll("i"), ...els.dockSpectrum.querySelectorAll("i")];
  const playing = !els.audio.paused && state.userStarted;
  bars.forEach((bar, idx) => {
    const t = Date.now() / 240;
    const v = playing ? 18 + Math.abs(Math.sin(t + idx * 0.42)) * (22 + (idx % 7) * 3) : 10 + (idx % 4) * 3;
    bar.style.height = `${v}px`;
    bar.style.opacity = playing ? ".95" : ".35";
  });
  requestAnimationFrame(animateSpectrum);
}

async function startAuto() {
  state.userStarted = true;
  await playRecommended(true);
}

function bindEvents() {
  els.startAuto.addEventListener("click", startAuto);
  els.nextBest.addEventListener("click", async () => {
    state.userStarted = true;
    await playRecommended(false);
  });
  els.stopBtn.addEventListener("click", () => {
    els.audio.pause();
    els.dockPlay.textContent = "▶";
    toast("Rádio pausada");
  });
  els.dockPlay.addEventListener("click", async () => {
    state.userStarted = true;
    if (!els.audio.src && !state.hls) return startAuto();
    if (els.audio.paused) {
      try {
        await els.audio.play();
        els.dockPlay.textContent = "⏸";
      } catch (err) {
        console.warn(err);
        await startAuto();
      }
    } else {
      els.audio.pause();
      els.dockPlay.textContent = "▶";
    }
  });
  els.dockAuto.addEventListener("click", () => {
    els.autoSwitch.checked = !els.autoSwitch.checked;
    els.dockAuto.classList.toggle("active", els.autoSwitch.checked);
    saveSettings();
    toast(els.autoSwitch.checked ? "Auto-switch ligado" : "Auto-switch desligado");
  });
  els.favCurrent.addEventListener("click", () => {
    const p = state.currentProgram;
    if (!p) return;
    if (state.favorites.has(p.id)) state.favorites.delete(p.id);
    else state.favorites.add(p.id);
    saveSettings();
    renderSchedule();
    updateNowUI();
  });
  [els.autoSwitch, els.favoritesOnly, els.newsBoost].forEach(el => {
    el.addEventListener("change", () => {
      els.dockAuto.classList.toggle("active", els.autoSwitch.checked);
      saveSettings();
      schedulerTick(false);
    });
  });
  els.volume.addEventListener("input", () => {
    els.audio.volume = Number(els.volume.value);
    saveSettings();
  });
  els.audio.addEventListener("playing", () => { els.dockPlay.textContent = "⏸"; });
  els.audio.addEventListener("pause", () => { els.dockPlay.textContent = "▶"; });
  els.audio.addEventListener("error", () => {
    if (!state.userStarted || !state.desiredStationId || state.switching) return;
    toast("Erro no stream. Vou tentar recuperar.", "bad");
    const now = Date.now();
    if (!state.lastAudioErrorRetryAt || now - state.lastAudioErrorRetryAt > 10000) {
      state.lastAudioErrorRetryAt = now;
      setTimeout(() => switchToStation(state.desiredStationId, "Recuperação automática"), 1200);
    }
  });
}

async function boot() {
  initBars();
  bindEvents();
  animateSpectrum();
  updateClock();

  try {
    const res = await fetch(`/api/config?t=${Date.now()}`);
    const config = await res.json();
    if (!config.ok) throw new Error("Configuração inválida");
    state.config = config;
    state.stations = config.stations || [];
    state.programs = config.programs || [];
    loadSettings();
    renderStations();
    renderSchedule();
    renderUpNext();
    schedulerTick(false);
    setInterval(() => schedulerTick(false), 15000);
    setInterval(updateClock, 1000);
    toast("Rádio pronta. Carrega em Ativar rádio 24/7.", "ok");
  } catch (err) {
    console.error(err);
    toast("Erro ao carregar a configuração da rádio.", "bad");
  }
}

boot();
