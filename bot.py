import os
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class ResolveIaBlindado:
    def __init__(self):
        # --- CONFIGURAÇÃO GEMINI (TITULAR) ---
        try:
            # Nota: Ajustei para 0.1 para ele ser menos criativo na Fase 1
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
            self.gemini_model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                generation_config={"temperature": 0.1} 
            )
            self.gemini_ok = True
        except Exception as e:
            print(f"⚠️ Erro ao configurar Gemini: {e}")
            self.gemini_ok = False

        # --- CONFIGURAÇÃO GROQ (RESERVA DE LUXO) ---
        try:
            self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            # Pega do .env ou usa o Llama 3.3 como padrão
            self.groq_model = os.getenv("GROQ_MODEL")
            self.groq_ok = True
        except Exception as e:
            print(f"⚠️ Erro ao configurar Groq: {e}")
            self.groq_ok = False

    def _buscar_rag(self, query):
        """Simulação ou chamada real do Pinecone"""
        print(f"🔍 Buscando contexto para: {query}")
        # AQUI VAI SUA LÓGICA DE PINECONE
        # return index.query(...) 
        return f"[CONTEXTO RAG] O usuário perguntou sobre: {query}. (Aqui entraria o texto do PDF)"

    def _montar_prompt(self, query, contexto, fase):
        """Constrói o System Prompt adaptado para o CACD 2026"""
        
        # --- FASE 1: CLASSIFICADOR BINÁRIO (Robô) ---
        if fase == '1':
            return f"""
            ATUE COMO UM CLASSIFICADOR LÓGICO DE QUESTÕES DO CEBRASPE.
            
            --- CONTEXTO (FONTE DE VERDADE) ---
            {contexto}
            -----------------------------------
            
            INPUT DO USUÁRIO: "{query}"
            
            SUA TAREFA:
            1. Identifique os fatos chave (datas, nomes, conceitos).
            2. Verifique se o Contexto suporta esses fatos.
            3. Verifique se a relação de causa e efeito está correta.
            4. Procure por "pegadinhas" (ex: "apenas", "exceto", "nunca").
            
            REGRAS RIGÍDAS DE RESPOSTA (OUTPUT):
            1. Se a afirmação for verdadeira segundo o contexto -> Responda: "CERTO"
            2. Se a afirmação for falsa segundo o contexto -> Responda: "ERRADO"
            3. Se o contexto não mencionar o assunto -> Responda: "ERRO"
            
            LISTA DE PROIBIÇÕES (NÃO FAÇA ISSO):
            - NÃO dê bom dia ou saudações.
            - NÃO explique o motivo.
            - NÃO use pontuação final.
            - NÃO complete a frase (Ex: Não diga "O item está CERTO").
            
            Sua resposta deve conter EXATAMENTE UMA PALAVRA.
            """

        # --- FASE 2: TUTOR / LEDOR (Humano Culto) ---
        else:
            return f"""
            # PERSONA
            Você é um Tutor Especialista no CACD 2026 (Diplomacia).
            Sua resposta será convertida em áudio. Mantenha formalidade, ritmo de ditado e linguagem culta.

            --- CONTEXTO (FONTE DE VERDADE) ---
            {contexto}
            -----------------------------------

            # MODO 2: TREINO DISCURSIVO E DITADO
            - O usuário pediu uma redação, resumo ou questão.
            - SUA MISSÃO: Ditar um modelo de resposta (Standard Answer).
            
            LIMITES DE LINHAS (Edital 2026):
            * Redação (Port/Ing): 65 a 70 linhas.
            * Resumo (Port): Máx 30 linhas.
            * Discursiva (Conteúdo): 40 a 60 linhas.
            
            ESTILO DE FALA (LEITURA PARA DITADO):
            * Inicie com: "Aqui está uma sugestão de resposta modelo. Prepare-se para o ditado."
            * Dite o texto pausadamente.
            * VERBALIZE A PONTUAÇÃO (Fale "Vírgula", "Ponto final", "Abre aspas").

            INPUT DO USUÁRIO:
            {query}
            """

    def _chamar_gemini(self, prompt):
        print("🤖 Tentando Gemini...")
        response = self.gemini_model.generate_content(prompt)
        return response.text

    def _chamar_groq(self, prompt):
        print(f"⚡ Acionando Backup Groq: {self.groq_model}")
        
        try:
            # LÓGICA ESPECIAL PARA O MODELO DE RACIOCÍNIO (GPT-OSS-120B)
            # Verifica se o modelo configurado tem "oss" ou "120b" no nome
            if "oss" in self.groq_model or "120b" in self.groq_model:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.groq_model, # openai/gpt-oss-120b
                    
                    # Parâmetros exclusivos deste modelo
                    reasoning_effort="medium", 
                    temperature=1.0, # Precisa ser alta para raciocínio
                    max_completion_tokens=8192,
                    top_p=1,
                    stream=False,
                    stop=None
                )
            
            # LÓGICA PADRÃO (Llama 3, Mixtral, etc)
            else:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.groq_model,
                    temperature=0.1, # Precisa ser baixa para precisão
                    max_completion_tokens=4096,
                    top_p=1,
                    stream=False
                )

            return chat_completion.choices[0].message.content

        except Exception as e:
            print(f"❌ Erro Crítico no Groq Principal ({self.groq_model}): {e}")
            
            # FALLBACK DE SEGURANÇA: Se o 120b falhar, tenta o Llama 3 básico
            try:
                print("🔄 Tentando Fallback para Llama 3.3 Versatile...")
                fallback_resp = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    temperature=0.3
                )
                return fallback_resp.choices[0].message.content
            except:
                return "⚠️ Erro Fatal: Nem Gemini nem Groq responderam."

    def processar(self, inputs):
        user_input = inputs.get('user_input')
        fase = inputs.get('fase')
        prioridade = inputs.get('prioridade', 'groq')

        # 1. Busca RAG (O segredo do sucesso está aqui)
        contexto = self._buscar_rag(user_input)
        if not contexto:
            return "⚠️ Erro: Não encontrei material sobre isso na base de dados.", "Sistema"

        prompt_final = self._montar_prompt(user_input, contexto, fase)

        # Lógica de Chamada (Simplificada para focar no parsing)
        resposta_bruta = ""
        modelo_usado = ""

        # Tenta Groq Primeiro (exemplo)
        if prioridade == 'groq' and self.groq_ok:
            try:
                resposta_bruta = self._chamar_groq(prompt_final)
                modelo_usado = "Groq ⚡"
            except:
                pass # Tenta o próximo...
        
        # Se não tiver resposta, tenta Gemini... (sua lógica de fallback continua aqui)
        if not resposta_bruta and self.gemini_ok:
            resposta_bruta = self._chamar_gemini(prompt_final)
            modelo_usado = "Gemini 💎"

        if not resposta_bruta:
            return "Erro: IAs indisponíveis", "Offline"

        # --- O PULO DO GATO: LIMPEZA DA RESPOSTA (PARSING) ---
        if fase == '1':
            # Normaliza para maiúsculo para evitar erros de digitação da IA
            resp_upper = resposta_bruta.upper()
            
            # Procura a palavra chave final
            if "VEREDITO: CERTO" in resp_upper or "VEREDITO:CERTO" in resp_upper:
                return "CERTO", modelo_usado
            elif "VEREDITO: ERRADO" in resp_upper or "VEREDITO:ERRADO" in resp_upper:
                return "ERRADO", modelo_usado
            elif "VEREDITO: ERRO" in resp_upper:
                return "ERRO (Conteúdo não encontrado)", modelo_usado
            else:
                # Se a IA se perdeu no formato, retorna tudo para você auditar
                # Dica: Às vezes é bom ver o raciocínio quando ela erra
                return f"⚠️ Resposta fora do padrão:\n{resposta_bruta}", modelo_usado
        
        else:
            # Fase 2 retorna tudo (Ditado)
            return resposta_bruta, modelo_usado