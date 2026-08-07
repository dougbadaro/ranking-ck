import time
import logging
import pandas as pd
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─── CONFIGURAÇÕES GERAIS ─────────────────────────────────────────────────────
EMAIL             = "marcos.barnabe2014@gmail.com"
SENHA             = "Barnabe3"
INTERVALO_SLIDE   = 10000   # ms entre slides no HTML
TEMPO_ATUALIZACAO = 300     # segundos entre coletas
# ──────────────────────────────────────────────────────────────────────────────

# Configuração profissional de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def criar_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--log-level=3") # Suprime logs desnecessários do Chrome
    
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def esperar(driver, by, selector, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, selector))
    )


def padronizar_nome(nome):
    partes = nome.split()
    if len(partes) > 4:
        partes = partes[:4] + [partes[4][0] + "."]
    return " ".join(partes)


def coletar_dados():
    driver = criar_driver()
    try:
        driver.get("https://global.gamefik.com/login")

        # 1. Tela de E-mail
        email_input = esperar(driver, By.CSS_SELECTOR, 'input[type="email"], input[type="text"]')
        email_input.send_keys(EMAIL)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

        # 2. Tela de Opções -> Selecionar "Entrar com senha"
        btn_senha = esperar(driver, By.XPATH, "//*[contains(text(), 'Entrar com senha')]")
        btn_senha.click()

        # 3. Tela de Senha
        senha_input = esperar(driver, By.CSS_SELECTOR, 'input[type="password"]')
        senha_input.send_keys(SENHA)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

        # Validação de saída da tela de login
        try:
            WebDriverWait(driver, 20).until(lambda d: "/login" not in d.current_url)
        except Exception:
            logging.error(f"Falha no login. URL atual: {driver.current_url}")
            return []

        # Extração
        driver.get("https://global.gamefik.com/players")
        
        WebDriverWait(driver, 30).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "img[alt='Coins']")) > 0
        )
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.find_all(
            "div",
            class_=lambda c: c and "group" in c and "relative" in c and "cursor-pointer" in c
        )

        jogadores = []
        for card in cards:
            try:
                info_div = card.find("div", class_=lambda c: c and "flex-1" in c and "min-w-0" in c)
                if not info_div:
                    continue

                first_text = ""
                for child in info_div.children:
                    if hasattr(child, "get_text"):
                        t = child.get_text(strip=True)
                        if t:
                            first_text = t
                            break

                m = re.search(r"(CK \d{4} - (?:Kids|Teens))(.*?)(\d{2}/\d{2}/\d{4})", first_text)
                if not m:
                    continue

                nome = padronizar_nome(first_text[:m.start()].strip())
                turma = m.group(2).strip()

                coin_img = card.find("img", alt="Coins")
                coin_str = str(coin_img.next_sibling) if coin_img else "0"
                coin_val = int(coin_str.replace(".", "").replace(",", ""))

                if nome and turma:
                    jogadores.append({"Nome": nome, "Turma": turma, "Coin": coin_val})

            except Exception as e:
                logging.warning(f"Card ignorado devido a erro de parsing: {e}")
                continue

        logging.info(f"Extração concluída: {len(jogadores)} jogadores encontrados.")
        return jogadores

    finally:
        driver.quit()


def gerar_html(df):
    dados_json = json.dumps(df.to_dict(orient="records"), ensure_ascii=False)

    html_template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@700;800;900&display=swap" rel="stylesheet">
<style>
:root {
  --yellow:   #F2CD37;
  --yellow2:  #FFE066;
  --purple:   #4B3786;
  --purple2:  #6B52B8;
  --purple3:  #2A1F55;
  --dark:     #0E0A1F;
  --darker:   #07050F;
  --green:    #55FCB9;
  --red:      #FF5757;
  --white:    #FFFFFF;
  --card-bg:  rgba(75, 55, 134, 0.25);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
  font-family: 'Nunito', sans-serif;
  background: var(--darker);
  color: var(--white);
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
#particles {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}
.star {
  position: absolute;
  border-radius: 50%;
  opacity: 0;
  animation: fall linear infinite;
}
@keyframes fall {
  0%   { opacity: 0; transform: translateY(-20px) scale(0); }
  10%  { opacity: 1; }
  90%  { opacity: 0.6; }
  100% { opacity: 0; transform: translateY(105vh) scale(1.5); }
}
.bg-glow {
  position: fixed;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(75,55,134,0.7) 0%, transparent 70%),
    radial-gradient(ellipse 60% 40% at 80% 110%, rgba(242,205,55,0.12) 0%, transparent 60%),
    linear-gradient(180deg, #0E0A1F 0%, #07050F 100%);
}
.wrapper {
  position: relative;
  z-index: 1;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.header {
  flex: 0 0 auto;
  height: 10vh;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3vw;
  padding: 0 4vw;
}
.logo-img {
  height: 7vh;
  filter: drop-shadow(0 0 12px rgba(242,205,55,0.5));
}
.title-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5vh;
}
.title-main {
  font-family: 'Fredoka One', cursive;
  font-size: clamp(20px, 4.5vw, 38px);
  color: var(--yellow);
  letter-spacing: 2px;
  line-height: 1;
}
.title-sub {
  font-size: clamp(10px, 2vw, 14px);
  font-weight: 800;
  color: var(--green);
  letter-spacing: 3px;
  text-transform: uppercase;
}
.carousel {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.carousel-item {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.7s ease;
  display: flex;
  flex-direction: column;
  padding: 0 4vw 10vh 4vw;
  pointer-events: none;
}
.carousel-item.active {
  opacity: 1;
  pointer-events: auto;
}
.turma-title {
  flex: 0 0 auto;
  margin-bottom: 2vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.turma-title-text {
  font-family: 'Fredoka One', cursive;
  font-size: clamp(20px, 4vw, 36px);
  color: var(--white);
  text-transform: uppercase;
  text-align: center;
  line-height: 1.2;
}
.turma-title-text span {
  color: var(--yellow);
}
.podium-section {
  flex: 0 0 auto;
  margin-bottom: 2vh;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 3vw;
}
.podium-place {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1vh;
  opacity: 0;
  transform: translateY(20px);
}
.carousel-item.active .podium-place {
  animation: popIn 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards;
}
.carousel-item.active .podium-place:nth-child(1) { animation-delay: 0.1s; }
.carousel-item.active .podium-place:nth-child(2) { animation-delay: 0.0s; }
.carousel-item.active .podium-place:nth-child(3) { animation-delay: 0.2s; }
@keyframes popIn {
  to { opacity: 1; transform: translateY(0); }
}
.podium-avatar {
  width: clamp(50px, 14vw, 100px);
  height: clamp(50px, 14vw, 100px);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(20px, 5vw, 40px);
  border: 4px solid;
  position: relative;
}
.podium-avatar.gold   { background: linear-gradient(135deg,#FFE066,#F2A500); border-color: #F2CD37; box-shadow: 0 0 20px rgba(242,205,55,0.6); }
.podium-avatar.silver { background: linear-gradient(135deg,#E8F0FE,#9AA8BD); border-color: #C8D6E5; box-shadow: 0 0 12px rgba(200,214,229,0.4); }
.podium-avatar.bronze { background: linear-gradient(135deg,#FFD4A8,#C8622A); border-color: #E8915A; box-shadow: 0 0 12px rgba(232,145,90,0.4); }
.medal-crown {
  position: absolute;
  top: -15px;
  font-size: clamp(16px, 3.5vw, 26px);
}
.podium-name {
  font-family: 'Fredoka One', cursive;
  font-size: clamp(12px, 2.5vw, 20px);
  text-align: center;
  max-width: 26vw;
  line-height: 1.1;
}
.podium-score {
  font-size: clamp(11px, 2vw, 16px);
  font-weight: 900;
  display: flex;
  align-items: center;
  gap: 5px;
}
.podium-score.gold   { color: var(--yellow); }
.podium-score.silver { color: #C8D6E5; }
.podium-score.bronze { color: #E8915A; }
.podium-block {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px 12px 4px 4px;
  width: clamp(70px, 22vw, 140px);
  font-family: 'Fredoka One', cursive;
  font-size: clamp(24px, 5vw, 42px);
  color: rgba(255,255,255,0.9);
  text-shadow: 0 3px 0 rgba(0,0,0,0.3);
  box-shadow: 0 6px 20px rgba(0,0,0,0.5);
  position: relative;
  overflow: hidden;
}
.podium-block::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 30%;
  background: rgba(255,255,255,0.15);
  border-radius: 12px 12px 0 0;
}
.podium-block.gold   { background: linear-gradient(180deg,#F2CD37,#C98A00); height: 11vh; }
.podium-block.silver { background: linear-gradient(180deg,#9AA8BD,#5A6A80); height: 8.5vh; }
.podium-block.bronze { background: linear-gradient(180deg,#E8915A,#954020); height: 6.5vh; }
.rank-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  padding: 0 2vw;
}
@keyframes slideIn {
  0%   { opacity: 0; transform: translateX(-40px); }
  100% { opacity: 1; transform: translateX(0); }
}
.player-card {
  display: flex;
  align-items: center;
  gap: 3vw;
  background: var(--card-bg);
  border: 1px solid rgba(107,82,184,0.3);
  border-left: 6px solid;
  border-radius: 12px;
  padding: 0 4vw;
  height: clamp(40px, 5vh, 70px);
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  opacity: 0;
  position: relative;
}
.player-card.rank-4  { border-left-color: #7B68EE; }
.player-card.rank-5  { border-left-color: #6A5ACD; }
.player-card.rank-6  { border-left-color: #5A4BBD; }
.player-card.rank-7  { border-left-color: #4B3CAE; }
.player-card.rank-8  { border-left-color: #3D2E9F; }
.player-card.rank-9  { border-left-color: #302290; }
.player-card.rank-10 { border-left-color: #241882; }
.carousel-item.active .player-card {
  animation: slideIn 0.4s cubic-bezier(0.22,1,0.36,1) forwards;
}
.carousel-item.active .player-card:nth-child(1) { animation-delay: 0.05s; }
.carousel-item.active .player-card:nth-child(2) { animation-delay: 0.10s; }
.carousel-item.active .player-card:nth-child(3) { animation-delay: 0.15s; }
.carousel-item.active .player-card:nth-child(4) { animation-delay: 0.20s; }
.carousel-item.active .player-card:nth-child(5) { animation-delay: 0.25s; }
.carousel-item.active .player-card:nth-child(6) { animation-delay: 0.30s; }
.carousel-item.active .player-card:nth-child(7) { animation-delay: 0.35s; }
.rank-num {
  font-family: 'Fredoka One', cursive;
  font-size: clamp(16px, 3.5vw, 28px);
  width: 10vw;
  text-align: center;
  color: rgba(255,255,255,0.5);
  flex-shrink: 0;
}
.rank-num strong { color: var(--yellow); }
.player-name {
  flex: 1;
  font-size: clamp(14px, 3vw, 24px);
  font-weight: 800;
  color: var(--white);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.player-coin {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Fredoka One', cursive;
  font-size: clamp(14px, 3vw, 24px);
  color: var(--yellow);
  flex-shrink: 0;
}
.slide-dots {
  position: absolute;
  bottom: 4vh;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 12px;
  z-index: 10;
}
.slide-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  transition: all 0.3s;
}
.slide-dot.active {
  background: var(--yellow);
  width: 25px;
  border-radius: 5px;
}
.clock-container {
  position: absolute;
  bottom: 3vh;
  right: 5vw;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  z-index: 20;
  line-height: 1;
}
.clock-time {
  font-family: 'Fredoka One', cursive;
  font-size: clamp(28px, 6vw, 56px);
  color: var(--yellow);
  letter-spacing: 2px;
}
.clock-date {
  font-size: clamp(10px, 2vw, 18px);
  font-weight: 800;
  color: rgba(255,255,255,0.6);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-right: 4px;
  margin-top: 5px;
}
</style>
</head>
<body>
<div class="bg-glow"></div>
<div id="particles"></div>
<div class="wrapper">
  <div class="header">
    <img src="logo.png" class="logo-img" alt="Código Kid">
    <div class="title-badge">
      <div class="title-main">🏆 RANKING</div>
      <div class="title-sub">Classificação de alunos</div>
    </div>
  </div>
  <div class="carousel" id="carousel"></div>
  <div class="clock-container">
    <div id="clock-time" class="clock-time">--:--</div>
    <div id="clock-date" class="clock-date">--/--/----</div>
  </div>
</div>
<script>
const RANKING_DATA = __RANKING_DATA__;
const INTERVALO_SLIDE = __INTERVALO_SLIDE__;

const pContainer = document.getElementById('particles');
const COLORS = ['#F2CD37','#55FCB9','#7B68EE','#FF5757','#FFE066'];
for (let i = 0; i < 40; i++) {
  const s = document.createElement('div');
  s.className = 'star';
  const size = Math.random() * 6 + 4;
  s.style.cssText = `
    left: ${Math.random()*100}%;
    width: ${size}px; height: ${size}px;
    background: ${COLORS[Math.floor(Math.random()*COLORS.length)]};
    animation-duration: ${4 + Math.random()*7}s;
    animation-delay: ${Math.random()*8}s;
  `;
  pContainer.appendChild(s);
}
function coinSVG(size = "4vw") {
  return `<svg width="${size}" height="${size}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" style="max-width:30px; max-height:30px; filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5))">
    <circle cx="50" cy="50" r="45" fill="#F2CD37" stroke="#C9A31A" stroke-width="5"/>
    <circle cx="50" cy="50" r="33" fill="#FFDF4D" stroke="#D4AF37" stroke-width="2"/>
    <path d="M50 24 L57 41 L76 41 L61 52 L68 70 L50 57 L32 70 L39 52 L24 41 L43 41 Z" fill="rgba(255,255,255,0.85)"/>
  </svg>`;
}
const carousel = document.getElementById('carousel');
const turmas = [...new Set(RANKING_DATA.map(p => p.Turma))];

turmas.forEach((turma, tIdx) => {
  const players = RANKING_DATA
    .filter(p => p.Turma === turma)
    .sort((a, b) => b.Coin - a.Coin)
    .slice(0, 10);
  const item = document.createElement('div');
  item.className = 'carousel-item' + (tIdx === 0 ? ' active' : '');
  const turmaName = turma.replace('Clube do Código ', '');
  item.innerHTML += `
    <div class="turma-title">
      <div class="turma-title-text">Clube do Código <br><span>${turmaName}</span></div>
    </div>
  `;
  if (players.length >= 1) {
    const podiumOrder = [players[1] || null, players[0], players[2] || null];
    const ranks  = [2, 1, 3];
    const types  = ['silver', 'gold', 'bronze'];
    const crowns = ['🥈', '👑', '🥉'];
    const emojis = ['🤖', '⭐', '🎮']; 

    let podiumHTML = '<div class="podium-section">';
    podiumOrder.forEach((p, i) => {
      if (!p) { podiumHTML += '<div></div>'; return; }
      const type = types[i];
      const r    = ranks[i];
      const nameShort = p.Nome.split(' ').slice(0,2).join(' ');
      podiumHTML += `
        <div class="podium-place">
          <div class="podium-avatar ${type}">
            <span class="medal-crown">${crowns[i]}</span>
            ${emojis[i]} 
          </div>
          <div class="podium-name">${nameShort}</div>
          <div class="podium-score ${type}">${coinSVG("2.5vw")} ${p.Coin.toLocaleString('pt-BR')}</div>
          <div class="podium-block ${type}">${r}</div>
        </div>
      `;
    });
    podiumHTML += '</div>';
    item.innerHTML += podiumHTML;
  }
  const rest = players.slice(3);
  if (rest.length > 0) {
    let listHTML = '<div class="rank-list">';
    rest.forEach((p, i) => {
      const rankNum = i + 4;
      listHTML += `
        <div class="player-card rank-${rankNum}">
          <div class="rank-num"><strong>${rankNum}º</strong></div>
          <div class="player-name">${p.Nome}</div>
          <div class="player-coin">${p.Coin.toLocaleString('pt-BR')} ${coinSVG("3.5vw")}</div>
        </div>
      `;
    });
    listHTML += '</div>';
    item.innerHTML += listHTML;
  }
  carousel.appendChild(item);
});
const dotsContainer = document.createElement('div');
dotsContainer.className = 'slide-dots';
turmas.forEach((_, i) => {
  const d = document.createElement('div');
  d.className = 'slide-dot' + (i === 0 ? ' active' : '');
  dotsContainer.appendChild(d);
});
document.querySelector('.wrapper').appendChild(dotsContainer);
const slides = document.querySelectorAll('.carousel-item');
const dots   = document.querySelectorAll('.slide-dot');
let current  = 0;
function goTo(n) {
  slides[current].classList.remove('active');
  dots[current].classList.remove('active');
  current = (n + slides.length) % slides.length;
  slides[current].classList.add('active');
  dots[current].classList.add('active');
}
if (slides.length > 1) {
  setInterval(() => goTo(current + 1), INTERVALO_SLIDE);
}
function updateTime() {
  const now = new Date();
  document.getElementById('clock-time').textContent = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  document.getElementById('clock-date').textContent = now.toLocaleDateString('pt-BR');
}
updateTime();
setInterval(updateTime, 1000);
setInterval(() => location.reload(), 60000);
</script>
</body>
</html>"""

    html_final = html_template.replace("__RANKING_DATA__", dados_json)
    html_final = html_final.replace("__INTERVALO_SLIDE__", str(INTERVALO_SLIDE))

    with open("ranking.html", "w", encoding="utf-8") as f:
        f.write(html_final)


def loop_atualizacao():
    ChromeDriverManager().install()
    logging.info("Iniciando serviço de coleta Gamefik...")

    while True:
        try:
            logging.info("Iniciando ciclo de coleta de dados.")
            dados = coletar_dados()
            df = pd.DataFrame(dados)

            if df.empty:
                logging.warning("Nenhum jogador retornado ou falha no login.")
            else:
                df = df[~df["Turma"].isin(["Tour Gameficado", "Colaboradores"])]
                gerar_html(df)
                logging.info("Arquivo HTML gerado com sucesso.")

        except Exception as e:
            logging.error(f"Erro inesperado no loop principal: {e}", exc_info=True)
        
        logging.info(f"Aguardando {TEMPO_ATUALIZACAO} segundos para a próxima execução.")
        time.sleep(TEMPO_ATUALIZACAO)


if __name__ == "__main__":
    try:
        loop_atualizacao()
    except KeyboardInterrupt:
        logging.info("Execução encerrada pelo usuário (Ctrl+C).")