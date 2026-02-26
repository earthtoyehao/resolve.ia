import os
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv
import requests

load_dotenv()

# --- CLASSE AUXILIAR DE FERRAMENTAS (WIKIPÉDIA) ---
class WikiTool:
    def __init__(self):
        # Endpoint oficial da Wikipédia em Português
        self.api_url = "https://pt.wikipedia.org/w/api.php"

    def search(self, query):
        """
        Faz uma busca direta na API da Wikipédia e retorna o resumo.
        """
        try:
            # 1. Limpeza da query (para não buscar "Item 102 União Europeia")
            termos_ignorados = ["julgue", "item", "texto de apoio", "texto base", "no que se refere", "acerca de"]
            query_limpa = query.lower()
            for termo in termos_ignorados:
                query_limpa = query_limpa.replace(termo, "")
            
            query_limpa = query_limpa.strip()

            # Se a query ficar vazia ou muito curta, aborta para não gastar tempo
            if len(query_limpa) < 5:
                return ""

            print(f"🌍 WikiTool: Buscando por '{query_limpa}'...")

            # 2. Parâmetros da API MediaWiki
            params = {
                "action": "query",
                "format": "json",
                "titles": query_limpa,
                "prop": "extracts",
                "explaintext": 1,   # Traz texto puro, sem HTML
                "exintro": 1,       # Traz APENAS a introdução (resumo)
                "redirects": 1      # Segue redirecionamentos automaticamente
            }

            # 3. Requisição HTTP
            response = requests.get(self.api_url, params=params, timeout=2) # Timeout curto
            response.raise_for_status()
            data = response.json()

            # 4. Processamento da Resposta
            pages = data['query']['pages']
            page_id = next(iter(pages))
            
            if page_id == "-1":
                return ""

            extract = pages[page_id].get('extract', '')

            if not extract:
                return ""

            # Retorna formatado para entrar no Contexto
            return f"\n[FONTE WIKIPÉDIA - ATUALIDADES/FATOS]: {extract[:800]}..."

        except Exception as e:
            print(f"⚠️ Erro na WikiTool: {e}")
            return ""

# --- CLASSE PRINCIPAL DO AGENTE ---
class ResolveIaBlindado:
    def __init__(self):
        # 1. INICIALIZA A FERRAMENTA WIKI
        self.wiki = WikiTool()

        # --- CONFIGURAÇÃO GEMINI (TITULAR) ---
        try:
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
            self.gemini_model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL"),
                generation_config={"temperature": 0.1} 
            )
            self.gemini_ok = True
        except Exception as e:
            print(f"⚠️ Erro ao configurar Gemini: {e}")
            self.gemini_ok = False

        # --- CONFIGURAÇÃO GROQ (RESERVA DE LUXO) ---
        try:
            self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            self.groq_model = os.getenv("GROQ_MODEL")
            self.groq_ok = True
        except Exception as e:
            print(f"⚠️ Erro ao configurar Groq: {e}")
            self.groq_ok = False

    def _buscar_rag(self, query):
        """Simulação ou chamada real do Pinecone"""
        print(f"🔍 Buscando contexto RAG para: {query}")
        # AQUI VAI SUA LÓGICA DE PINECONE
        return f"[CONTEXTO BIBLIOGRÁFICO] (Aqui entraria o texto do PDF sobre {query})"

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

            Você é um candidato altamente experiente do CACD – Segunda Fase.
            Escreve como um diplomata brasileiro em exercício.
            Sua escrita é técnica, analítica, precisa, equilibrada e institucional.

            A resposta será convertida em áudio.
            Portanto, toda pontuação deve ser verbalizada explicitamente.

            ---

            # CONTEXTO (FONTE DE VERDADE – RAG PINECONE)

            Antes de redigir:
            - Recupere pelo menos 5 respostas reais de alta pontuação relacionadas ao tema.
            - Identifique padrões estruturais.
            - Modele a resposta com base nesses padrões.
            - Não mencione o uso do RAG no texto final.

            Base de referência:
            {contexto}

            ---

            # MISSÃO

            Produzir uma resposta discursiva padrão CACD Fase 2,
            obedecendo rigorosamente:

            - Estrutura argumentativa madura.
            - Proporcionalidade conforme pontuação dos itens.
            - Densidade conceitual elevada.
            - Tom diplomático institucional.
            - Progressão lógica clara.
            - Integração entre os tópicos (não responder em blocos isolados).

            ---

            # ESTRUTURA OBRIGATÓRIA

            1) Introdução:
            - Delimitação conceitual.
            - Contextualização objetiva.
            - Indicação implícita da linha argumentativa.

            2) Desenvolvimento:
            - Responder exatamente aos itens solicitados.
            - Distribuir espaço proporcional à pontuação.
            - Integrar teoria e aplicação.
            - Demonstrar domínio técnico.
            - Indicar tensões e trade-offs quando pertinente.

            3) Conclusão:
            - Síntese analítica.
            - Fechamento institucional.
            - Evitar juízos normativos excessivos.

            ---

            # CONTROLE DE LINHAS

            Se questão de 60 linhas:
            - Produzir entre 55 e 60 linhas.

            Se questão de 40 linhas:
            - Produzir entre 35 e 40 linhas.

            Cada linha deve manter densidade média compatível com manuscrito CACD.
            Não ultrapassar o limite.
            Não mencionar contagem de linhas no texto final.

            ---

            # FORMATAÇÃO PARA CONVERSÃO EM VOZ (OBRIGATÓRIO)

            1) Nunca usar apenas símbolos gráficos.
            2) Sempre verbalizar pontuação:

            - vírgula
            - ponto
            - ponto e vírgula
            - dois pontos
            - travessão
            - abre parêntese
            - fecha parêntese
            - interrogação
            - exclamação

            3) Ao final de cada frase escrever: "ponto"
            4) Em enumerações internas utilizar:
            - primeiro ponto
            - segundo ponto
            - terceiro ponto
            5) Não usar abreviações.
            6) Não usar marcadores visuais ou tópicos numerados.

            Exemplo correto:
            A política externa brasileira vírgula historicamente vírgula caracteriza-se pelo universalismo ponto

            ---

            # CRITÉRIOS CEBRASPE

            A resposta deve demonstrar:

            - Precisão conceitual.
            - Correção terminológica.
            - Capacidade analítica.
            - Coerência argumentativa.
            - Encadeamento lógico.
            - Linguagem formal e impessoal.

            Evitar:

            - Generalizações vagas.
            - Afirmações não fundamentadas.
            - Repetições desnecessárias.
            - Tom opinativo.

            ---

            # ESTRATÉGIA DIPLOMÁTICA

            - Reconhecer complexidades.
            - Demonstrar ponderação.
            - Indicar implicações institucionais.
            - Evitar conclusões categóricas quando o tema for controverso.
            - Valorizar estabilidade normativa e previsibilidade sistêmica.

            ---

            # INPUT DO USUÁRIO

            {query}

            Produza agora a resposta completa, obedecendo integralmente todas as instruções acima.
            """

    def _chamar_gemini(self, prompt):
        print("🤖 Tentando Gemini...")
        response = self.gemini_model.generate_content(prompt)
        return response.text

    def _chamar_groq(self, prompt):
        print(f"⚡ Acionando Backup Groq: {self.groq_model}")
        try:
            # LÓGICA ESPECIAL PARA O MODELO DE RACIOCÍNIO (GPT-OSS-120B)
            if "oss" in self.groq_model or "120b" in self.groq_model:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.groq_model,
                    reasoning_effort="medium", 
                    temperature=1.0,
                    max_completion_tokens=8192,
                    top_p=1,
                    stream=False,
                    stop=None
                )
            else:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.groq_model,
                    temperature=0.1,
                    max_completion_tokens=4096,
                    top_p=1,
                    stream=False
                )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"❌ Erro Crítico no Groq ({self.groq_model}): {e}")
            return None # Retorna None para o loop tentar o próximo

    def _corrigir_transcricao(self, texto_sujo):
        """
        Agente Editor: Transforma transcrição "crua" em texto culto.
        """
        if not texto_sujo or len(texto_sujo) < 5:
            return texto_sujo

        print(f"🧹 Agente Editor: Analisando '{texto_sujo}'...")
        
        prompt_revisao = f"""
        ATUE COMO UM REVISOR DE TEXTO DE ELITE PARA O CONCURSO DE DIPLOMACIA (CACD).
        Você receberá uma transcrição bruta de áudio.
        Sua missão é converter em texto formal, pontuado e gramaticalmente perfeito.
        
        INPUT BRUTO: "{texto_sujo}"
        
        DIRETRIZES:
        1. PONTUAÇÃO INTELIGENTE: Adicione vírgulas, pontos e maiúsculas.
        2. CORREÇÃO FONÉTICA: Corrija palavras ouvidas errado pelo contexto.
        3. PADRONIZAÇÃO:
           - "e tem"/"aí tem" + número -> "Item X".
           - "texto de apoio" -> "Texto de Apoio".
        4. MAIÚSCULAS: Nomes próprios e siglas (ONU, OEA).

        OUTPUT: APENAS o texto revisado.
        """
        
        try:
            # Usa Groq Llama 3 (Rápido)
            if self.groq_ok:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_revisao}],
                    model="llama-3.3-70b-versatile",
                    temperature=0.1,
                    max_completion_tokens=1024
                )
                return chat_completion.choices[0].message.content.strip()
            return texto_sujo 
        except Exception as e:
            print(f"⚠️ Falha Editor: {e}")
            return texto_sujo

    def processar(self, inputs):
        user_input = inputs.get('user_input')
        fase = inputs.get('fase')
        prioridade = inputs.get('prioridade', 'gemini')

        # 1. Busca dados do RAG (Base Oficial)
        contexto_rag = self._buscar_rag(user_input)
        
        # 2. Busca dados da WIKIPÉDIA (Complemento de Atualidades)
        # Só ativa se o input for maior que 15 chars (evita "olá", "sim", etc)
        contexto_wiki = ""
        if len(user_input) > 15:
             contexto_wiki = self.wiki.search(user_input)

        # 3. Consolidação do Contexto (RAG + Wiki)
        # O prompt recebe tudo junto e trata como "Contexto"
        contexto_final = f"{contexto_rag}\n{contexto_wiki}"

        # 4. Monta o Prompt Único (com o contexto turbinado)
        prompt_final = self._montar_prompt(user_input, contexto_final, fase)

        # 5. Define a ordem de execução
        ordem_tentativa = []
        if prioridade == 'groq':
            ordem_tentativa = [
                ('groq', self.groq_ok, self._chamar_groq, "Groq ⚡"),
                ('gemini', self.gemini_ok, self._chamar_gemini, "Gemini 💎")
            ]
        else:
            ordem_tentativa = [
                ('gemini', self.gemini_ok, self._chamar_gemini, "Gemini 💎"),
                ('groq', self.groq_ok, self._chamar_groq, "Groq ⚡")
            ]

        # 6. Loop de Execução
        errors = []
        for nome, status_ok, funcao_chamar, label_visual in ordem_tentativa:
            if status_ok:
                try:
                    print(f"🔄 Tentando via {nome}...")
                    resposta = funcao_chamar(prompt_final)
                    
                    if resposta: # Garante que não voltou None ou Vazio
                        resposta = resposta.strip()
                        return resposta, label_visual
                    else:
                         errors.append(f"{nome} retornou vazio.")

                except Exception as e:
                    msg_erro = f"Falha em {nome}: {e}"
                    print(f"❌ {msg_erro}")
                    errors.append(msg_erro)
            else:
                errors.append(f"{nome} off.")

        return f"⚠️ FALHA TOTAL: Nenhum modelo respondeu.\nErros: {errors}", "Offline 🔴"