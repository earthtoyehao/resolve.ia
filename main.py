import os
import asyncio
import threading
import time
import subprocess
import speech_recognition as sr
import tempfile
from datetime import datetime
from gtts import gTTS
from dotenv import load_dotenv

# --- FLASK PARA O DEPLOY (RENDER) ---
from flask import Flask

# Telegram
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Importação da sua IA (Mantendo como você enviou: from bot import ...)
from bot import ResolveIaBlindado 

# --- CARREGA VARIÁVEIS ---
load_dotenv() 
TOKEN = os.getenv("TELEGRAM_TOKEN")

# --- CONFIGURAÇÃO DO SERVIDOR WEB (FAKE) ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Resolve.ia Backend está Online e Operante!"

def run_web_server():
    port = int(os.environ.get("PORT", 8585))
    app_flask.run(host='0.0.0.0', port=port, use_reloader=False)

# --- GERENCIADOR DE ESTADO GLOBAL ---
class BotState:
    def __init__(self):
        self.fase_atual = '1'
        
        # AQUI VOCÊ DEFINE A PRIORIDADE DIRETO NO CÓDIGO
        # Opções: 'groq' ou 'gemini'
        self.modelo_prioridade = 'groq' 
        
        self.logs = []
        print(f"🚀 Inicializando Sistema Resolve.ia (Prioridade: {self.modelo_prioridade.upper()})...")
        self.ai_system = ResolveIaBlindado()

    def add_log(self, tipo, msg, status="Info"):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"time": ts, "type": tipo, "msg": msg, "status": status}
        self.logs.insert(0, entry)
        print(f"[{ts}] {tipo} - {msg}")
        if len(self.logs) > 30:
            self.logs.pop()

state = BotState()

# --- UTILITÁRIOS ---
def converter_audio_nativo(input_path):
    output_path = input_path.replace(".ogg", ".wav")
    ffmpeg_cmd = "ffmpeg"
    possible_paths = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
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

# --- COMANDOS DO TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🟢 **Resolve.ia Online!**\n\n"
        "Comandos de Configuração:\n"
        "`/fase1` - Modo Julgamento (Certo/Errado)\n"
        "`/fase2` - Modo Discursivo (Explicações)\n"
        "`/status` - Ver configurações\n\n"
        "Mande um áudio para começarmos."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_fase1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.fase_atual = '1'
    state.add_log("Config", "Fase alterada para 1")
    await update.message.reply_text("✅ **Fase 1 (Julgamento Rápido) ativada.**", parse_mode=ParseMode.MARKDOWN)

async def cmd_fase2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.fase_atual = '2'
    state.add_log("Config", "Fase alterada para 2")
    await update.message.reply_text("✅ **Fase 2 (Modo Discursivo) ativada.**", parse_mode=ParseMode.MARKDOWN)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ícones para visualização
    motor = "Desconhecido"
    if state.ai_system.gemini_ok: motor = "Gemini"
    if state.ai_system.groq_ok: motor += " + Groq"

    relatorio = (
        f"📊 **Métricas Resolve.ia**\n"
        f"---------------------------\n"
        f"⚙️ Fase Atual: {state.fase_atual}\n"
        f"🏆 Prioridade: {state.modelo_prioridade.upper()} ⚡\n"
        f"🧠 Motores: {motor}\n"
        f"📜 Último evento: {state.logs[0]['msg'] if state.logs else 'Nenhum'}"
    )
    await update.message.reply_text(relatorio, parse_mode=ParseMode.MARKDOWN)

# --- PROCESSAMENTO DE ÁUDIO ---
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    state.add_log("Telegram", f"Áudio de {user}", "Recebido")
    
    temp_dir = tempfile.gettempdir()
    ogg_file = os.path.join(temp_dir, f"voice_{int(time.time())}.ogg")
    
    try:
        msg_wait = await update.message.reply_text("⬇️ Baixando...")
        f = await context.bot.get_file(update.message.voice.file_id)
        await f.download_to_drive(ogg_file)
        
        wav = converter_audio_nativo(ogg_file)
        if not wav: raise Exception("Falha Conversão")

        # STT
        r = sr.Recognizer()
        with sr.AudioFile(wav) as source:
            texto = r.recognize_google(r.record(source), language="pt-BR")
        
        state.add_log("Transcrição", texto, "Sucesso")
        
        # Edita a mensagem de espera com o texto transcrito
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg_wait.message_id, text=f"📝 {texto}")
        
        # Envia feedback de processamento
        processing_msg = await update.message.reply_text(f"🧠 Processando via {state.modelo_prioridade.upper()}...") 

        # --- AQUI É A CONEXÃO COM A CLASSE BLINDADA ---
        inputs = {
            'user_input': texto,
            'fase': state.fase_atual,
            'prioridade': state.modelo_prioridade # Passa a config do init
        }
        
        # Executa a IA
        resposta_final, modelo_utilizado = state.ai_system.processar(inputs)
        
        # Apaga msg de "Processando..." e manda a resposta
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
        await update.message.reply_text(f"{resposta_final}")

        # TTS (Áudio Resposta)
        tts = gTTS(text=resposta_final, lang='pt', slow=False) 
        mp3 = wav.replace(".wav", ".mp3")
        tts.save(mp3)
        await update.message.reply_voice(voice=open(mp3, 'rb'))
        
        state.add_log("Ciclo", f"Resp. via {modelo_utilizado}", "Finalizado")

    except Exception as e:
        error_msg = str(e)
        state.add_log("Erro", error_msg, "Erro")
        await update.message.reply_text(f"⚠️ Erro interno: {error_msg}")

# --- EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERRO: TOKEN não encontrado no .env")
        exit()

    # 1. Inicia o servidor Flask
    print("🌐 Iniciando servidor Web...")
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

    # 2. Inicia o Bot do Telegram
    print("🤖 Iniciando Polling do Telegram...")
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fase1", cmd_fase1))
    app.add_handler(CommandHandler("fase2", cmd_fase2))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.VOICE, handle_audio))
    
    app.run_polling(stop_signals=None)