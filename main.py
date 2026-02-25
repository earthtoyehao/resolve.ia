import os
import streamlit as st
import threading
import asyncio
import time
import subprocess
import speech_recognition as sr
import tempfile
from datetime import datetime
from gtts import gTTS
from dotenv import load_dotenv

# Telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Importação da sua IA
from bot import ResolveIaBlindado 

# --- CARREGA VARIÁVEIS ---
load_dotenv() 
TOKEN = os.getenv("TELEGRAM_TOKEN")

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="Resolve.ia Admin", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- GERENCIADOR DE ESTADO (DADOS LEVES) ---
class ServerState:
    def __init__(self):
        self.logs = []
        self.fase_atual = '1'
        self.modelo_prioridade = 'groq' 
        self.texto_apoio_atual = None   
    
    def add_log(self, tipo, msg, status="Info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.insert(0, {"time": ts, "type": tipo, "msg": msg, "status": status})
        if len(self.logs) > 50: self.logs.pop()
        
    def set_fase(self, nova_fase):
        self.fase_atual = nova_fase
        self.add_log("Config", f"Fase alterada para {nova_fase}", "⚙️")

    def set_prioridade(self, nova_prioridade):
        self.modelo_prioridade = nova_prioridade.lower()
        self.add_log("Config", f"Prioridade alterada para {nova_prioridade}", "⚙️")

    def set_texto_apoio(self, texto):
        self.texto_apoio_atual = texto
        self.add_log("Memória", "Novo Texto de Apoio Memorizado", "💾")

    def get_texto_apoio(self):
        return self.texto_apoio_atual

@st.cache_resource
def get_state(): return ServerState()
state = get_state()

# --- INICIALIZAÇÃO DA IA (PESADA) ---
@st.cache_resource
def get_ai_system():
    print("🚀 Inicializando Cérebro Resolve.ia...")
    return ResolveIaBlindado()

# Variável Global da IA
ai_system = get_ai_system()

# --- UTILITÁRIOS DE ÁUDIO ---
def converter_audio_nativo(input_path):
    output_path = input_path.replace(".ogg", ".wav")
    ffmpeg_cmd = "ffmpeg"
    possible_paths = ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]
    for path in possible_paths:
        if os.path.exists(path):
            ffmpeg_cmd = path
            break     
    cmd = [ffmpeg_cmd, "-i", input_path, "-ac", "1", "-ar", "16000", output_path, "-y"]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        return output_path
    except Exception as e:
        print(f"Erro ffmpeg: {e}")
        return None

# --- LÓGICA DO BOT TELEGRAM ---
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    state.add_log("Telegram", f"Áudio de {user}", "Recebido")
    
    temp_dir = tempfile.gettempdir()
    ogg_file = os.path.join(temp_dir, f"voice_{int(time.time())}.ogg")
    
    try:
        msg_wait = await update.message.reply_text("⬇️ Ouvindo...")
        f = await context.bot.get_file(update.message.voice.file_id)
        await f.download_to_drive(ogg_file)
        
        wav = converter_audio_nativo(ogg_file)
        if not wav: raise Exception("Falha Conversão")

        # 1. Transcrição (Google)
        r = sr.Recognizer()
        with sr.AudioFile(wav) as source:
            texto_bruto = r.recognize_google(r.record(source), language="pt-BR")
        
        # 2. Agente Faxineiro
        # CORREÇÃO CRUCIAL: Usamos 'ai_system' direto (Global), SEM 'state.'
        texto_limpo = ai_system._corrigir_transcricao(texto_bruto)
        state.add_log("Correção", f"'{texto_bruto}' -> '{texto_limpo}'", "✨")
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=msg_wait.message_id, 
            text=f"📝 {texto_limpo}"
        )
        
        # 3. Contexto
        inicio_frase = texto_limpo.lower()[:40]
        gatilhos_texto = ["texto de apoio", "texto base", "novo texto", "leia o texto"]
        gatilhos_item = ["item", "questão", "julgue", "número"]

        eh_comando_texto = any(g in inicio_frase for g in gatilhos_texto)
        tem_item_junto = any(g in texto_limpo.lower() for g in gatilhos_item)

        prompt_final = ""

        if eh_comando_texto:
            state.set_texto_apoio(texto_limpo)
            if not tem_item_junto:
                await update.message.reply_text("🧠 **Texto Base Memorizado!** Pode mandar os itens.")
                return 
            prompt_final = texto_limpo
            aviso = "🧠 Texto salvo e processando item..."
        else:
            memoria = state.get_texto_apoio()
            if memoria:
                aviso = "💡 Usando Texto Base da memória..."
                prompt_final = f"TEXTO BASE (MEMÓRIA):\n{memoria}\n\nITEM ATUAL:\n{texto_limpo}"
            else:
                aviso = "⚠️ Processando item isolado..."
                prompt_final = texto_limpo

        await update.message.reply_text(aviso)

        # 4. Executa a IA
        inputs = {
            'user_input': prompt_final,
            'fase': state.fase_atual,
            'prioridade': state.modelo_prioridade
        }
        
        # CORREÇÃO CRUCIAL: Usamos 'ai_system' direto (Global), SEM 'state.'
        resposta_final, modelo_utilizado = ai_system.processar(inputs)
        
        await update.message.reply_text(resposta_final)

        # 5. TTS
        tts = gTTS(text=resposta_final, lang='pt', slow=False) 
        mp3 = wav.replace(".wav", ".mp3")
        tts.save(mp3)
        await update.message.reply_voice(voice=open(mp3, 'rb'))
        
        state.add_log("Ciclo", f"Resp. via {modelo_utilizado}", "Finalizado")

    except Exception as e:
        error_msg = str(e)
        state.add_log("Erro", error_msg, "Erro")
        await update.message.reply_text(f"⚠️ Erro interno: {error_msg}")

async def start(u, c): await u.message.reply_text("🤖 Resolve.ia Online!")

# --- THREAD DO TELEGRAM ---
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if not TOKEN: return
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_audio))
    app.run_polling(stop_signals=[], close_loop=False)

@st.cache_resource
def start_bg_bot():
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    return t

start_bg_bot()

# ==========================================
#      INTERFACE VISUAL (STREAMLIT)
# ==========================================

# Layout Topo
col_icon, col_title, col_vazia, col_fase, col_ai = st.columns([0.6, 2.5, 0.5, 1.2, 1.2])

with col_icon:
    if os.path.exists("assets/icon.png"):
        st.image("assets/icon.png", width=70)
    else:
        st.write("🤖")

with col_title:
    st.markdown("""<h1 style='margin-top: -5px; padding-top: 0; font-size: 2.5rem;'>Resolve.ia</h1>""", unsafe_allow_html=True)
    st.caption("Central de Comando")

with col_fase:
    modo_fase2 = st.toggle("Fase 2 (Discursiva)", value=(state.fase_atual == '2'))
    nova_fase = '2' if modo_fase2 else '1'
    if nova_fase != state.fase_atual:
        state.set_fase(nova_fase)
        st.rerun()

with col_ai:
    prioridade_sel = st.radio("Prioridade IA", ["Groq", "Gemini"], index=0 if state.modelo_prioridade == 'groq' else 1, horizontal=True, label_visibility="collapsed")
    if prioridade_sel.lower() != state.modelo_prioridade:
        state.set_prioridade(prioridade_sel)
        st.rerun()

st.markdown("---")

# Métricas
m1, m2, m3 = st.columns(3)
m1.metric("Status", "Online 🟢" if TOKEN else "Erro Token")
memoria_status = "Ativa 💾" if state.texto_apoio_atual else "Vazia ⚪"
m2.metric("Memória Contexto", memoria_status)

with m3:
    if state.texto_apoio_atual:
        if st.button("Limpar Memória", type="primary"):
            state.set_texto_apoio(None)
            st.rerun()
    else:
        st.metric("Logs", len(state.logs))

# Logs
st.markdown("### 📜 Logs")
if state.logs:
    with st.container(height=300):
        for log in state.logs:
            icon = "ℹ️"
            if log["status"] == "Erro": icon = "🔴"
            elif log["status"] == "Finalizado": icon = "✅"
            elif log["status"] == "✨": icon = "✨" 
            elif log["status"] == "💾": icon = "💾"
            st.text(f"{log['time']} {icon} [{log['type']}] {log['msg']}")
else:
    st.info("Aguardando conexões...")

time.sleep(2)
st.rerun()