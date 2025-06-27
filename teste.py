import pandas as pd
import gspread
from gspread import Worksheet
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import locale
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import io
from fpdf import FPDF
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64
import json
from functools import lru_cache
import plotly.graph_objects as go
import re
import warnings
import PyPDF2
import pyttsx3
import speech_recognition as sr
import keyboard
from threading import Thread
import queue
import pyaudio
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from io import BytesIO
import matplotlib.pyplot as plt

# Ignorar warnings específicos
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# ========== CONFIGURAÇÕES GERAIS ========== #
GOOGLE_CREDS_FILE = "service_account.json"
SPREADSHEET_ID = "1qakkGdVJidgakvy476RUcAp1rkU74TfPOY7sq4TQXzk"

# Configuração segura da API Key
OPENAI_API_KEY = "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"
client = OpenAI(api_key=OPENAI_API_KEY)

# Configuração de localização
try:
    locale.setlocale(locale.LC_NUMERIC, "pt_BR.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_NUMERIC, "Portuguese_Brazil.1252")

# ========== FUNÇÕES AUXILIARES ========== #
@st.cache_resource
def conectar_google_sheets():
    """Conecta ao Google Sheets e retorna todas as abas com tratamento de erro"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                 "https://www.googleapis.com/auth/drive"]
        
        # Verifica se o arquivo de credenciais existe
        if not os.path.exists(GOOGLE_CREDS_FILE):
            raise FileNotFoundError(f"Arquivo de credenciais '{GOOGLE_CREDS_FILE}' não encontrado")
            
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID)
        return sheet.worksheets()
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Sheets: {str(e)}")
        return None

@st.cache_data
def converter_valor_decimal(valor):
    """Converte valores para formato decimal brasileiro com tratamento robusto"""
    try:
        if pd.isna(valor) or valor is None:
            return None
            
        valor_str = str(valor).strip()
        # Remove caracteres não numéricos exceto pontos e vírgulas
        valor_str = ''.join(c for c in valor_str if c.isdigit() or c in [',', '.'])
        
        # Verifica se há múltiplos pontos ou vírgulas
        if valor_str.count(',') > 1 or valor_str.count('.') > 1:
            return None
            
        # Substitui pontos por nada e vírgulas por ponto
        if ',' in valor_str and '.' in valor_str:
            if valor_str.find(',') > valor_str.find('.'):  # 1.234,56
                valor_str = valor_str.replace('.', '')
                valor_str = valor_str.replace(',', '.')
            else:  # 1,234.56
                valor_str = valor_str.replace(',', '')
        elif ',' in valor_str:
            valor_str = valor_str.replace(',', '.')
            
        return float(valor_str)
    except Exception as e:
        st.warning(f"Erro ao converter valor '{valor}': {str(e)}")
        return None

def processar_dados_maquina(aba):
    """Processa os dados de uma máquina específica"""
    try:
        dados = aba.get_all_records()
        df = pd.DataFrame(dados)
        
        # Padroniza nomes de colunas
        df.columns = df.columns.str.strip().str.lower()
        
        # Converte data/hora
        df["data/hora"] = pd.to_datetime(df["data/hora"], errors="coerce", dayfirst=True)
        
        # Converte valores numéricos
        df["temperatura"] = df["temperatura"].apply(converter_valor_decimal)
        df["vibracao (hz)"] = df["vibracao (hz)"].apply(converter_valor_decimal)
        df["corrente (a)"] = df["corrente (a)"].apply(converter_valor_decimal)
        
        # Remove linhas com valores nulos
        df = df.dropna()
        
        # Verifica alertas
        alertas = []
        ultimo = df.iloc[-1]
        
        dados_maquina = {
            "Temperatura": f"{ultimo['temperatura']:.1f} °C",
            "Vibração": f"{ultimo['vibracao (hz)']:.1f} Hz",
            "Corrente": f"{ultimo['corrente (a)']:.1f} A",
            "Última Leitura": ultimo["data/hora"].strftime("%d/%m/%Y %H:%M")
        }
        
        return {
            "df": df,
            "dados_maquina": dados_maquina,
            "alertas": alertas
        }
    except Exception as e:
        st.error(f"Erro ao processar dados da máquina {aba.title}: {str(e)}")
        return None

def gerar_relatorio_completo(dados_maquinas, specs=None, usar_manual=True):
    """Gera um relatório PDF completo com os dados das máquinas"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name='Titulo', 
                             fontSize=16, 
                             leading=20,
                             spaceAfter=12,
                             alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='Subtitulo', 
                             fontSize=12, 
                             textColor=colors.HexColor('#2a5885'),
                             spaceAfter=6))
    styles.add(ParagraphStyle(name='CabecalhoSecao', 
                             fontSize=12, 
                             textColor=colors.HexColor('#0c5460'),
                             spaceAfter=6))
    styles.add(ParagraphStyle(name='TextoNormal', 
                             fontSize=10,
                             leading=12,
                             spaceAfter=6))
    styles.add(ParagraphStyle(name='Alerta', 
                             fontSize=10,
                             textColor=colors.HexColor('#856404'),
                             backColor=colors.HexColor('#fff3cd'),
                             leading=12,
                             spaceAfter=6))
    
    elements = []
    
    # Cabeçalho do relatório
    logo_path = "logo.png"  # Substitua pelo caminho do seu logo ou remova
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2*inch, height=1*inch)
        elements.append(logo)
    
    elements.append(Paragraph("RELATÓRIO DE MANUTENÇÃO PREDITIVA", styles['Titulo']))
    elements.append(Paragraph(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Center']))
    elements.append(Spacer(1, 24))
    
    # Conteúdo para cada máquina
    for dados in dados_maquinas:
        # Título da máquina
        elements.append(Paragraph(dados['nome_maquina'], styles['Subtitulo']))
        elements.append(Spacer(1, 12))
        
        # Dados técnicos
        elements.append(Paragraph("DADOS TÉCNICOS", styles['CabecalhoSecao']))
        
        # Tabela de dados técnicos
        tech_data = [
            ["Temperatura", dados['dados_maquina'].get('Temperatura', 'N/A')],
            ["Vibração", dados['dados_maquina'].get('Vibração', 'N/A')],
            ["Corrente", dados['dados_maquina'].get('Corrente', 'N/A')],
            ["Última Leitura", dados['dados_maquina'].get('Última Leitura', 'N/A')]
        ]
        
        tech_table = Table(tech_data, colWidths=[2*inch, 3*inch])
        tech_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fafafa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
        ]))
        elements.append(tech_table)
        elements.append(Spacer(1, 12))
        
        # Especificações técnicas - Tratamento corrigido
        machine_specs = {}
        if specs:
            # Caso specs seja uma lista de configurações de máquinas
            if isinstance(specs, list):
                for m in specs:
                    if isinstance(m, dict) and m.get('nome') == dados['nome_maquina']:
                        machine_specs = m.get('specs', {})
                        break
            # Caso specs seja um dicionário direto
            elif isinstance(specs, dict):
                machine_specs = specs.get(dados['nome_maquina'], {})
        
        if machine_specs:
            elements.append(Paragraph("ESPECIFICAÇÕES TÉCNICAS", styles['CabecalhoSecao']))
            
            # Campos padrão que queremos mostrar
            spec_fields = [
                ('Fabricante', 'fabricante'),
                ('Modelo', 'modelo'),
                ('Temperatura Máxima', 'temperatura_max'),
                ('Vibração Máxima', 'vibracao_max'),
                ('Corrente Nominal', 'corrente_nominal'),
                ('Potência Nominal', 'potencia_nominal'),
                ('Ano de Fabricação', 'ano_fabricacao'),
                ('Número de Série', 'numero_serie')
            ]
            
            spec_data = []
            for display_name, field_name in spec_fields:
                if field_name in machine_specs:
                    value = machine_specs[field_name]
                    # Formata valores numéricos com unidades
                    if field_name == 'temperatura_max' and isinstance(value, (int, float)):
                        value = f"{value}°C"
                    elif field_name == 'vibracao_max' and isinstance(value, (int, float)):
                        value = f"{value}Hz"
                    elif field_name == 'corrente_nominal' and isinstance(value, (int, float)):
                        value = f"{value}A"
                    elif field_name == 'potencia_nominal' and isinstance(value, (int, float)):
                        value = f"{value}kW"
                    
                    spec_data.append([display_name, value])
            
            if spec_data:
                spec_table = Table(spec_data, colWidths=[2*inch, 3*inch])
                spec_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f4f8')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0c5460')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5fbfe')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#c4e3f3')),
                ]))
                elements.append(spec_table)
                elements.append(Spacer(1, 12))
        
        # Informações do manual técnico
        if usar_manual and dados.get('manual_info'):
            elements.append(Paragraph("INFORMAÇÕES DO MANUAL TÉCNICO", styles['CabecalhoSecao']))
            
            manual_text = ""
            if dados['manual_info'].get('especificacoes'):
                manual_text += "<b>Especificações:</b><br/>"
                for k, v in dados['manual_info']['especificacoes'].items():
                    manual_text += f"• {k}: {v}<br/>"
                manual_text += "<br/>"
            
            if dados['manual_info'].get('manutencao', {}).get('procedimentos'):
                manual_text += "<b>Procedimentos de Manutenção:</b><br/>"
                for item in dados['manual_info']['manutencao']['procedimentos']:
                    manual_text += f"• {item}<br/>"
            
            elements.append(Paragraph(manual_text, styles['TextoNormal']))
            elements.append(Spacer(1, 12))
        
        # Alertas
        if dados.get('alertas'):
            elements.append(Paragraph("ALERTAS", styles['CabecalhoSecao']))
            
            alert_text = ""
            for alerta in dados['alertas']:
                alert_text += f"• {alerta}<br/>"
            
            elements.append(Paragraph(alert_text, styles['Alerta']))
            elements.append(Spacer(1, 12))
        
        # Análise preditiva
        if dados.get('analise_ia'):
            elements.append(Paragraph("ANÁLISE PREDITIVA", styles['CabecalhoSecao']))
            
            # Formata a análise para quebrar linhas corretamente
            analise_formatada = dados['analise_ia'].replace('\n', '<br/>')
            elements.append(Paragraph(analise_formatada, styles['TextoNormal']))
            elements.append(Spacer(1, 12))
        
        # Gráficos (se houver dados)
        if 'df' in dados and isinstance(dados['df'], pd.DataFrame) and not dados['df'].empty:
            elements.append(Paragraph("GRÁFICOS DE TENDÊNCIA", styles['CabecalhoSecao']))
            
            # Gera gráficos para cada métrica
            metrics = ['Temperatura', 'Vibração', 'Corrente']
            for metric in metrics:
                if metric in dados['df'].columns:
                    try:
                        fig, ax = plt.subplots(figsize=(8, 3))
                        dados['df'].plot(x='data/hora', y=metric, ax=ax, legend=False)
                        ax.set_title(f'{metric} ao longo do tempo')
                        ax.set_ylabel(metric)
                        ax.grid(True)
                        
                        img_buffer = BytesIO()
                        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
                        plt.close()
                        
                        img_buffer.seek(0)
                        img = Image(img_buffer, width=6*inch, height=2.5*inch)
                        elements.append(img)
                        elements.append(Spacer(1, 12))
                    except Exception as e:
                        print(f"Erro ao gerar gráfico para {metric}: {str(e)}")
        
        elements.append(Spacer(1, 24))
    
    # Rodapé
    elements.append(Paragraph("Relatório gerado automaticamente pelo Sistema de Manutenção Preditiva", 
                            ParagraphStyle(name='Rodape', 
                                          fontSize=8,
                                          textColor=colors.gray,
                                          alignment=TA_CENTER)))
    
    # Construir o PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def enviar_email(destinatario, assunto, corpo_html, pdf_bytes=None):
    """Envia e-mail com relatório em anexo"""
    try:
        # Configuração do e-mail
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDS_FILE,
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Cria mensagem
        message = MIMEMultipart()
        message['to'] = destinatario
        message['subject'] = assunto
        
        # Corpo HTML
        part = MIMEText(corpo_html, 'html')
        message.attach(part)
        
        # Anexo PDF
        if pdf_bytes:
            part = MIMEApplication(pdf_bytes, Name="relatorio.pdf")
            part['Content-Disposition'] = 'attachment; filename="relatorio.pdf"'
            message.attach(part)
        
        # Converte para raw e envia
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={'raw': raw_message}
        ).execute()
        
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {str(e)}")
        return False

def pesquisar_especificacoes(modelo):
    """Pesquisa especificações técnicas online"""
    try:
        prompt = f"""
        Pesquise as especificações técnicas completas para o modelo: {modelo}
        Retorne em formato JSON com:
        - fabricante
        - tensao_nominal
        - corrente_nominal
        - potencia_nominal
        - temperatura_maxima
        - vibracao_maxima
        - manual_link (se disponível)
        """
        
        resposta = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(resposta.choices[0].message.content)
    except Exception as e:
        st.error(f"Erro ao pesquisar especificações: {str(e)}")
        return None

# ========== SISTEMA DE COMANDOS DE VOZ AVANÇADO ========== #
class SistemaVoz:
    def __init__(self):
        self.audio_engine = None
        self.reconhecedor = sr.Recognizer()
        self.fila_comandos = queue.Queue()
        self.ativado = False
        self.monitorando_teclado = False
        self.mic_disponivel = False
        self.inicializar_audio()
        self.verificar_microfone()
        self.iniciar_monitoramento_teclado()
        self.ultimo_comando = None

    def inicializar_audio(self):
        """Inicializa o motor de voz"""
        try:
            self.audio_engine = pyttsx3.init()
            voices = self.audio_engine.getProperty('voices')
            for voice in voices:
                if 'pt_BR' in voice.languages or 'pt-br' in voice.languages:
                    self.audio_engine.setProperty('voice', voice.id)
                    break
            self.audio_engine.setProperty('rate', 150)
        except Exception as e:
            st.error(f"Erro ao inicializar motor de voz: {str(e)}")
            self.ativado = False

    def verificar_microfone(self):
        """Verifica se há microfone disponível"""
        try:
            p = pyaudio.PyAudio()
            info = p.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            
            for i in range(0, numdevices):
                if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                    self.mic_disponivel = True
                    break
                    
            p.terminate()
        except Exception as e:
            st.warning(f"Não foi possível verificar microfones: {str(e)}")
            self.mic_disponivel = False

    def iniciar_monitoramento_teclado(self):
        """Inicia thread para monitorar atalhos de teclado"""
        if not self.monitorando_teclado:
            self.monitorando_teclado = True
            Thread(target=self._monitorar_teclado, daemon=True).start()

    def _monitorar_teclado(self):
        """Monitora combinação Ctrl+0 para ativar/desativar acessibilidade"""
        while True:
            if keyboard.is_pressed('ctrl+0'):
                self.ativado = not self.ativado
                if self.ativado:
                    self.falar("Modo de acessibilidade ativado. Você pode falar comandos como 'ir para gráficos', 'gerar relatório' ou 'mostrar chat'.")
                else:
                    self.falar("Modo de acessibilidade desativado.")
                time.sleep(1)  # Evita múltiplas ativações
            time.sleep(0.1)

    def ouvir_comando(self, timeout=5):
        """Ouve comandos de voz do usuário"""
        if not self.ativado or not self.mic_disponivel:
            return None
            
        with sr.Microphone() as source:
            try:
                self.reconhecedor.adjust_for_ambient_noise(source)
                audio = self.reconhecedor.listen(source, timeout=timeout, phrase_time_limit=10)
                
                try:
                    texto = self.reconhecedor.recognize_google(audio, language='pt-BR')
                    st.session_state.ultimo_comando_voz = texto
                    return texto
                except sr.UnknownValueError:
                    self.falar("Não entendi o comando. Por favor, repita.")
                    return None
                except sr.RequestError as e:
                    self.falar(f"Erro no serviço de reconhecimento de voz: {str(e)}")
                    return None
                    
            except Exception as e:
                st.error(f"Erro no reconhecimento de voz: {str(e)}")
                return None

    def interpretar_comando(self, comando):
        """Interpreta o comando de voz e retorna a ação correspondente"""
        comando = comando.lower()
        
        # Mapeamento direto de comandos simples
        comandos_simples = {
            'ir para gráficos': 'navegar gráficos',
            'mostrar gráficos': 'navegar gráficos',
            'gráficos': 'navegar gráficos',
            'ir para chat': 'navegar chat',
            'mostrar chat': 'navegar chat',
            'chat': 'navegar chat',
            'ir para relatórios': 'navegar relatórios',
            'mostrar relatórios': 'navegar relatórios',
            'relatórios': 'navegar relatórios',
            'gerar relatório': 'gerar relatório',
            'atualizar': 'atualizar',
            'sair': 'sair'
        }
        
        if comando in comandos_simples:
            return {
                'acao': comandos_simples[comando],
                'resposta_audio': f"Executando: {comando}",
                'tipo': 'navegação' if 'navegar' in comandos_simples[comando] else 'ação'
            }
        
        # Comandos mais complexos usam IA
        try:
            prompt = f"""Interprete este comando de voz para um sistema de monitoramento preditivo:
            
            Comando: "{comando}"
            
            Possíveis ações:
            - Navegação entre páginas (chat, gráficos, relatórios)
            - Geração de relatórios
            - Atualização de dados
            - Configurações do sistema
            
            Retorne um JSON com:
            - "acao": comando do sistema (ex: "navegar gráficos")
            - "resposta_audio": confirmação em voz alta
            - "tipo": tipo da ação ("navegação", "relatório", "ação")
            """
            
            resposta = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            return json.loads(resposta.choices[0].message.content)
        except Exception as e:
            st.error(f"Erro ao interpretar comando: {str(e)}")
            return None

    def processar_comandos(self):
        """Processa os comandos na fila"""
        if not self.ativado:
            return
            
        while not self.fila_comandos.empty():
            comando = self.fila_comandos.get()
            try:
                if comando.startswith("navegar "):
                    pagina = comando.split(" ")[1]
                    st.session_state.pagina_selecionada = pagina.capitalize()
                    st.rerun()
                elif comando == "gerar relatório":
                    st.session_state.pagina_selecionada = "Relatórios"
                    st.rerun()
                elif comando == "atualizar":
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar comando: {str(e)}")

    def falar(self, texto):
        """Faz a leitura em voz alta do texto"""
        if not texto or not self.audio_engine or not self.ativado:
            return
            
        try:
            if self.audio_engine._inLoop:
                self.audio_engine.endLoop()
                
            self.audio_engine.say(texto)
            Thread(target=self.audio_engine.runAndWait, daemon=True).start()
        except Exception as e:
            st.warning(f"Erro ao falar: {str(e)}")

    def iniciar_monitoramento_teclado(self):
        """Inicia thread para monitorar atalhos de teclado"""
        if not self.monitorando_teclado:
            self.monitorando_teclado = True
            Thread(target=self._monitorar_teclado, daemon=True).start()

    def _monitorar_teclado(self):
        """Monitora combinação Ctrl+9 para verificar microfone e Ctrl+0 para acessibilidade"""
        while True:
            if keyboard.is_pressed('ctrl+9'):
                self.verificar_microfone()
                if self.mic_disponivel:
                    self.falar("Microfone detectado. Por favor, diga 'Alô' para testar.")
                    time.sleep(5)  # Espera por resposta
                else:
                    self.falar("Microfone não detectado. Por favor, conecte um microfone.")
                time.sleep(1)
                
            if keyboard.is_pressed('ctrl+0'):
                self.ativado = not self.ativado
                if self.ativado:
                    self.falar("Modo de acessibilidade ativado. Pressione Ctrl+0 novamente para desativar.")
                else:
                    self.falar("Modo de acessibilidade desativado.")
                time.sleep(1)
            time.sleep(0.1)

    def processar_comandos(self):
        """Processa comandos na fila de execução"""
        while not self.fila_comandos.empty():
            comando = self.fila_comandos.get()
            try:
                if comando.startswith("navegar "):
                    pagina = comando.split(" ")[1]
                    st.session_state.pagina_selecionada = pagina.capitalize()
                    st.rerun()
                elif comando == "gerar relatório":
                    st.session_state.pagina_selecionada = "Relatórios"
                    st.rerun()
                elif comando == "mostrar gráficos":
                    st.session_state.pagina_selecionada = "Gráficos"
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar comando: {str(e)}")

# ========== FUNÇÕES DE PROCESSAMENTO DE MANUAIS ========== #
def extrair_texto_pdf(uploaded_file):
    """Extrai texto de um PDF uploadado"""
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {str(e)}")
        return None

def processar_manual(texto):
    """Processa o texto do manual para extrair informações relevantes"""
    try:
        prompt = f"""
        Você é um especialista em manuais técnicos de equipamentos industriais. 
        Extraia as seguintes informações deste manual:
        
        1. Especificações técnicas principais (tensão, corrente, potência, etc.)
        2. Parâmetros operacionais normais
        3. Limites máximos e mínimos de operação
        4. Procedimentos de manutenção recomendados
        5. Possíveis códigos de erro e soluções
        
        Retorne em formato JSON com a seguinte estrutura:
        {{
            "especificacoes": {{
                "tensao_nominal": "string",
                "corrente_nominal": "float",
                "potencia_nominal": "float",
                "temperatura_maxima": "float",
                "vibracao_maxima": "float"
            }},
            "parametros_operacao": {{
                "faixa_temperatura_normal": "string",
                "faixa_vibracao_normal": "string",
                "faixa_corrente_normal": "string"
            }},
            "manutencao": {{
                "periodicidade": "string",
                "procedimentos": ["string"],
                "pecas_substituicao": ["string"]
            }},
            "codigos_erro": {{
                "codigo": "descricao"
            }}
        }}
        
        Manual:
        {texto[:20000]}  # Limita a 20k tokens para a API
        """
        
        resposta = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        return json.loads(resposta.choices[0].message.content)
    except Exception as e:
        st.error(f"Erro ao processar manual: {str(e)}")
        return None

def configuracao_inicial():
    """Configuração inicial do sistema"""
    st.title("⚙️ Configuração Inicial do Sistema")
    
    with st.form("config_form"):
        st.write("### Informações Básicas")
        email = st.text_input("E-mail para relatórios:", placeholder="seu@email.com")
        periodo_dias = st.selectbox("Enviar relatórios a cada:", [1, 7, 15, 30], index=2)
        
        st.write("### Configuração de Máquinas")
        num_maquinas = st.number_input("Número de máquinas a monitorar:", min_value=1, max_value=10, value=3)
        
        maquinas_config = []
        for i in range(num_maquinas):
            with st.expander(f"Máquina {i+1}", expanded=i==0):
                nome = st.text_input(f"Nome da Máquina {i+1}", key=f"nome_{i}")
                aba = st.text_input(f"Nome da aba no Google Sheets {i+1}", key=f"aba_{i}")
                modo = st.selectbox(f"Modo de Monitoramento {i+1}", 
                                   ["Monitoramento Básico", "Monitoramento Avançado"], 
                                   key=f"modo_{i}")
                
                # Upload do manual técnico
                uploaded_file = st.file_uploader(f"Manual Técnico (PDF) {i+1}", 
                                               type=["pdf"], 
                                               key=f"manual_{i}")
                
                specs = None
                if uploaded_file:
                    texto = extrair_texto_pdf(uploaded_file)
                    if texto:
                        manual_info = processar_manual(texto)
                        if manual_info:
                            st.session_state[f"manual_info_{aba}"] = manual_info
                            specs = manual_info.get('especificacoes', {})
                            st.success("Manual processado com sucesso!")
                
                maquinas_config.append({
                    "nome": nome,
                    "aba": aba,
                    "modo": modo,
                    "specs": specs
                })
        
        submitted = st.form_submit_button("Salvar Configuração")
        
        if submitted:
            if not email or not all(m['nome'] for m in maquinas_config) or not all(m['aba'] for m in maquinas_config):
                st.error("Por favor, preencha todos os campos obrigatórios")
                return
            
            st.session_state.configurado = True
            st.session_state.config_email = email
            st.session_state.config_periodo_dias = periodo_dias
            st.session_state.maquinas_config = maquinas_config
            
            # Inicializa o sistema de voz se não existir
            if 'sistema_voz' not in st.session_state:
                st.session_state.sistema_voz = SistemaVoz()
            
            st.success("Configuração salva com sucesso!")
            time.sleep(2)
            st.rerun()

# ========== PÁGINA DE CHAT ========== #
def pagina_chat():
    """Interface de chat com assistente IA"""
    st.title("🤖 Assistente de Manutenção Preditiva Avançado")
    
    # Verifica se o modo de acessibilidade está ativado
    if st.session_state.sistema_voz.ativado:
        st.session_state.sistema_voz.falar("Página do assistente de voz. Você pode fazer perguntas sobre o sistema ou pedir ajuda.")

    # Inicialização do histórico de mensagens
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = [
            {
                "role": "system",
                "content": """Você é um especialista em manutenção preditiva industrial com conhecimento técnico avançado. 
                Siga estas diretrizes:
                1. Analise dados de máquinas com precisão técnica
                2. Forneça recomendações em português com:
                   - Diagnósticos baseados em dados
                   - Ações corretivas priorizadas
                   - Análise de causa raiz detalhada
                   - Sugestões de peças com códigos de referência
                   - Estimativas de tempo para falha com margens de erro
                3. Consulte especificações técnicas online quando necessário
                4. Adapte o nível técnico conforme solicitado"""
            },
            {
                "role": "assistant", 
                "content": "Olá! Sou seu assistente especializado em manutenção preditiva. Posso analisar dados de máquinas, pesquisar especificações técnicas e fornecer recomendações precisas. Como posso ajudar hoje?"
            }
        ]
    
    # Estilo otimizado do chat
    st.markdown("""
    <style>
    .chat-message { 
        padding: 1rem; 
        border-radius: 0.5rem; 
        margin-bottom: 1rem;
        animation: fadeIn 0.3s ease-in-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .user-message { background-color: #2d3748; color: white; }
    .assistant-message { 
        background-color: #4a5568; 
        color: white;
        border-left: 4px solid #4299e1;
    }
    .stSpinner > div { justify-content: center; }
    </style>
    """, unsafe_allow_html=True)
    
    # Exibir histórico de mensagens com cache
    @st.cache_data(show_spinner=False)
    def display_messages(messages):
        for msg in messages[1:]:
            classe = "user-message" if msg["role"] == "user" else "assistant-message"
            st.markdown(f'<div class="chat-message {classe}">{msg["content"]}</div>', 
                       unsafe_allow_html=True)
    
    display_messages(st.session_state.mensagens)
    
    # Entrada do usuário otimizada
    with st.form(key="chat_form"):
        pergunta = st.text_area("Sua mensagem:", 
                              placeholder="Descreva a máquina, problema ou informe o modelo para pesquisa técnica...",
                              key="input_chat",
                              value=st.session_state.get('input_chat', ''))
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            nivel_detalhe = st.selectbox("Nível de detalhe:", 
                                        ["Resumido", "Detalhado", "Técnico Avançado"], 
                                        index=1)
        with col2:
            pesquisar_online = st.checkbox("Pesquisar especificações online", value=True)
        with col3:
            enviar = st.form_submit_button("Enviar", use_container_width=True)
    
    if enviar and pergunta:
        # Adiciona pergunta ao histórico
        user_message = {"role": "user", "content": pergunta}
        st.session_state.mensagens.append(user_message)
        
        # Container para resposta progressiva
        resposta_container = st.empty()
        resposta_completa = ""
        
        try:
            # Obter dados das máquinas de forma assíncrona
            with st.spinner("Coletando dados das máquinas..."):
                abas = conectar_google_sheets()
                contexto_maquinas = "\n\nDados Atuais das Máquinas:\n"
                
                # Verifica se há configurações de máquinas salvas
                maquinas_config = st.session_state.get('maquinas_config', [])
                
                for i, aba in enumerate(abas[:3]):  # Limita a 3 máquinas
                    dados = processar_dados_maquina(aba)
                    if dados:
                        # Obtém o nome configurado da máquina ou usa o padrão
                        nome_configurado = next(
                            (m['nome'] for m in maquinas_config if m['aba'] == aba.title),
                            aba.title
                        )
                        
                        # Obtém informações do manual se disponível
                        manual_info = st.session_state.get(f"manual_info_{aba.title}", None)
                        
                        contexto_maquinas += f"\n=== {nome_configurado} ===\n"
                        contexto_maquinas += f"- Status: {dados.get('status', 'N/A')}\n"
                        contexto_maquinas += f"- Temperatura: {dados['dados_maquina'].get('Temperatura', 'N/A')}°C\n"
                        contexto_maquinas += f"- Vibração: {dados['dados_maquina'].get('Vibração', 'N/A')} mm/s\n"
                        contexto_maquinas += f"- Corrente: {dados['dados_maquina'].get('Corrente', 'N/A')} A\n"
                        
                        # Adiciona informações do manual se disponível
                        if manual_info:
                            contexto_maquinas += "\nInformações do Manual Técnico:\n"
                            if 'especificacoes' in manual_info:
                                contexto_maquinas += "Especificações:\n"
                                for k, v in manual_info['especificacoes'].items():
                                    contexto_maquinas += f"- {k}: {v}\n"
                            
                            if 'parametros_operacao' in manual_info:
                                contexto_maquinas += "\nParâmetros de Operação:\n"
                                for k, v in manual_info['parametros_operacao'].items():
                                    contexto_maquinas += f"- {k}: {v}\n"
                            
                            if 'manutencao' in manual_info:
                                contexto_maquinas += "\nManutenção:\n"
                                if 'procedimentos' in manual_info['manutencao']:
                                    contexto_maquinas += "Procedimentos:\n"
                                    for item in manual_info['manutencao']['procedimentos']:
                                        contexto_maquinas += f"- {item}\n"
            
            # Configuração dinâmica do prompt
            nivel_instrucao = {
                "Resumido": "Resposta concisa (máx. 3 parágrafos), focada em ações imediatas.",
                "Detalhado": "Resposta completa com análise técnica, recomendações e peças sugeridas.",
                "Técnico Avançado": "Resposta detalhada com: análise de causa raiz, especificações técnicas, opções de manutenção, e estimativas de falha com cálculos."
            }
            
            # Adiciona instrução de pesquisa se necessário
            pesquisa_instrucao = ""
            if pesquisar_online:
                pesquisa_instrucao = """Se o usuário mencionar um modelo de máquina ou componente:
                1. Pesquise especificações técnicas atualizadas
                2. Inclua parâmetros operacionais recomendados
                3. Compare com os dados atuais fornecidos
                4. Cite fontes quando possível"""
            
            prompt = f"""
            {nivel_instrucao[nivel_detalhe]}
            {pesquisa_instrucao}
            
            Contexto:
            {contexto_maquinas}
            
            Pergunta do usuário:
            {pergunta}
            
            Estruture sua resposta com:
            1. Diagnóstico técnico
            2. Gravidade do problema (baixa/média/alta)
            3. Ações recomendadas (curto/médio/longo prazo)
            4. Peças sugeridas (com códigos quando possível)
            5. Estimativa de tempo para falha (com margem de erro)
            """
            # Configuração da chamada à API
            with st.spinner("Analisando e gerando resposta..."):
                response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=st.session_state.mensagens + [{"role": "user", "content": prompt}],
                    temperature=0.3 if nivel_detalhe == "Técnico Avançado" else 0.7,
                    stream=True  # Habilita streaming para resposta progressiva
                )
                
                # Processa a resposta em tempo real
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        resposta_completa += chunk.choices[0].delta.content
                        resposta_container.markdown(f'<div class="chat-message assistant-message">{resposta_completa}▌</div>', 
                                                 unsafe_allow_html=True)
                
                # Atualiza o histórico e exibe a resposta final
                st.session_state.mensagens.append({"role": "assistant", "content": resposta_completa})
                resposta_container.markdown(f'<div class="chat-message assistant-message">{resposta_completa}</div>', 
                                          unsafe_allow_html=True)
                
                # Leitura em voz alta da resposta se acessibilidade ativada
                if st.session_state.sistema_voz.ativado:
                    st.session_state.sistema_voz.falar(resposta_completa)
                
        except Exception as e:
            st.error(f"Erro ao processar sua solicitação: {str(e)}")
            st.session_state.mensagens.append({
                "role": "assistant", 
                "content": f"Desculpe, ocorreu um erro. Por favor, tente novamente. Detalhes: {str(e)}"
            })
            st.rerun()

# ========== PÁGINA DE RELATÓRIOS ========== #
def pagina_relatorios():
    """Interface para geração e envio de relatórios com especificações técnicas"""
    st.title("📊 Relatórios de Manutenção Avançado")
    
    # Verifica se o modo de acessibilidade está ativado
    if st.session_state.sistema_voz.ativado:
        st.session_state.sistema_voz.falar("Página de relatórios. Aqui você pode gerar e enviar relatórios de manutenção.")
    
    # Verifica se o e-mail foi configurado
    if "config_email" not in st.session_state or not st.session_state.config_email:
        st.warning("Por favor, configure um e-mail na página inicial")
        if st.session_state.sistema_voz.ativado:
            st.session_state.sistema_voz.falar("Por favor, configure um e-mail na página inicial.")
        return
    
    # Mostrar resumo das máquinas configuradas
    if 'maquinas_config' in st.session_state:
        st.write("### Máquinas Configuradas")
        for maquina in st.session_state.maquinas_config:
            with st.expander(f"{maquina['nome']} ({maquina['aba']})", expanded=False):
                st.write(f"**Modo:** {maquina['modo']}")
                if maquina.get('specs'):
                    cols = st.columns(2)
                    cols[0].metric("Temp. Máx", f"{maquina['specs'].get('temperatura_max', 'N/A')}°C")
                    cols[0].metric("Vib. Máx", f"{maquina['specs'].get('vibracao_max', 'N/A')}Hz")
                    cols[1].metric("Corr. Nom.", f"{maquina['specs'].get('corrente_nominal', 'N/A')}A")
                    cols[1].metric("Potência", f"{maquina['specs'].get('potencia_nominal', 'N/A')}kW")
                
                if st.session_state.get(f"manual_info_{maquina['aba']}"):
                    st.success("✅ Manual técnico disponível para esta máquina")
    
    # Configurações do relatório
    with st.expander("⚙️ Configurações do Relatório", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            periodo = st.selectbox("Período do relatório:", 
                                 ["Últimas 24 horas", "Última semana", "Último mês", "Personalizado"])
            
            if periodo == "Personalizado":
                data_inicio = st.date_input("Data inicial")
                data_fim = st.date_input("Data final")
        
        with col2:
            formato = st.selectbox("Formato do relatório:", 
                                 ["Completo", "Apenas anomalias", "Resumido"])
            incluir_analise_ia = st.checkbox("Incluir análise preditiva", value=True)
            usar_manual = st.checkbox("Incluir informações do manual técnico", value=True)
    
    # Botão para gerar relatório
    if st.button("📄 Gerar Relatório", type="primary"):
        with st.spinner("Processando máquinas e gerando relatório..."):
            try:
                abas = conectar_google_sheets()
                if not abas:
                    st.error("Falha ao conectar ao Google Sheets")
                    if st.session_state.sistema_voz.ativado:
                        st.session_state.sistema_voz.falar("Falha ao conectar ao Google Sheets.")
                    return
                
                dados_maquinas = []
                conteudo_email = """
                <h1 style="color: #2a5885;">Relatório de Manutenção Preditiva</h1>
                <p>Data: {}</p>
                <p>Período: {}</p>
                <hr style="border: 1px solid #eee;">
                """.format(
                    datetime.now().strftime('%d/%m/%Y %H:%M'),
                    periodo if periodo != "Personalizado" else f"{data_inicio} a {data_fim}"
                )
                
                # Obter configurações das máquinas
                maquinas_config = st.session_state.get('maquinas_config', [])
                
                for aba in abas:
                    dados = processar_dados_maquina(aba)
                    if dados:
                        # Obtém o nome configurado da máquina
                        nome_configurado = next(
                            (m['nome'] for m in maquinas_config if m['aba'] == aba.title),
                            aba.title
                        )
                        dados['nome_maquina'] = nome_configurado
                        
                        # Obtém as especificações configuradas
                        specs = next(
                            (m['specs'] for m in maquinas_config if m['aba'] == aba.title and m['specs']),
                            {}
                        )
                        
                        # Obtém informações do manual se disponível
                        manual_info = st.session_state.get(f"manual_info_{aba.title}", None)
                        
                        # Filtra por período se necessário
                        if periodo == "Últimas 24 horas":
                            cutoff = datetime.now() - timedelta(hours=24)
                            dados['df'] = dados['df'][dados['df']['data/hora'] >= cutoff]
                        elif periodo == "Última semana":
                            cutoff = datetime.now() - timedelta(weeks=1)
                            dados['df'] = dados['df'][dados['df']['data/hora'] >= cutoff]
                        elif periodo == "Último mês":
                            cutoff = datetime.now() - timedelta(days=30)
                            dados['df'] = dados['df'][dados['df']['data/hora'] >= cutoff]
                        elif periodo == "Personalizado":
                            dados['df'] = dados['df'][
                                (dados['df']['data/hora'].dt.date >= data_inicio) & 
                                (dados['df']['data/hora'].dt.date <= data_fim)
                            ]
                        
                        # Aplica filtro de formato
                        if formato == "Apenas anomalias" and not dados.get('alertas'):
                            continue
                            
                        dados_maquinas.append(dados)
                        
                        # Adiciona ao conteúdo do e-mail
                        conteudo_email += f"""
                        <h2 style="color: #2a5885;">{nome_configurado}</h2>
                        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
                            <h3>Dados Técnicos</h3>
                            <p><b>Temperatura:</b> {dados['dados_maquina'].get('Temperatura', 'N/A')}</p>
                            <p><b>Vibração:</b> {dados['dados_maquina'].get('Vibração', 'N/A')}</p>
                            <p><b>Corrente:</b> {dados['dados_maquina'].get('Corrente', 'N/A')}</p>
                            <p><b>Última Leitura:</b> {dados['dados_maquina'].get('Última Leitura', 'N/A')}</p>
                        """
                        
                        # Seção de especificações técnicas
                        if specs:
                            conteudo_email += """
                            <div style="background: #e8f4f8; padding: 10px; border-radius: 5px; margin: 10px 0;">
                                <h3 style="color: #0c5460;">Especificações Técnicas</h3>
                                <table style="width:100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 5px; border: 1px solid #ddd;"><b>Fabricante</b></td>
                                        <td style="padding: 5px; border: 1px solid #ddd;">{specs.get('fabricante', 'N/A')}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 5px; border: 1px solid #ddd;"><b>Modelo</b></td>
                                        <td style="padding: 5px; border: 1px solid #ddd;">{specs.get('modelo', 'N/A')}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 5px; border: 1px solid #ddd;"><b>Temp. Máx</b></td>
                                        <td style="padding: 5px; border: 1px solid #ddd;">{specs.get('temperatura_max', 'N/A')}°C</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 5px; border: 1px solid #ddd;"><b>Vib. Máx</b></td>
                                        <td style="padding: 5px; border: 1px solid #ddd;">{specs.get('vibracao_max', 'N/A')}Hz</td>
                                    </tr>
                                </table>
                            </div>
                            """.format(specs=specs)
                        
                        # Seção do manual técnico
                        if usar_manual and manual_info:
                            conteudo_email += """
                            <div style="background: #e8f8f4; padding: 10px; border-radius: 5px; margin: 10px 0;">
                                <h3 style="color: #0c5460;">Informações do Manual Técnico</h3>
                            """
                            
                            if 'especificacoes' in manual_info:
                                conteudo_email += "<h4>Especificações</h4><ul>"
                                for k, v in manual_info['especificacoes'].items():
                                    conteudo_email += f"<li><b>{k}:</b> {v}</li>"
                                conteudo_email += "</ul>"
                            
                            if 'manutencao' in manual_info and 'procedimentos' in manual_info['manutencao']:
                                conteudo_email += "<h4>Procedimentos de Manutenção</h4><ul>"
                                for item in manual_info['manutencao']['procedimentos']:
                                    conteudo_email += f"<li>{item}</li>"
                                conteudo_email += "</ul>"
                            
                            conteudo_email += "</div>"
                        
                        if dados.get('alertas'):
                            conteudo_email += """
                            <div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0;">
                                <h3 style="color: #856404;">Alertas</h3>
                                <ul>
                            """
                            for alerta in dados['alertas']:
                                conteudo_email += f"<li>{alerta}</li>"
                            conteudo_email += "</ul></div>"
                        
                        if incluir_analise_ia:
                            # Gera análise preditiva se necessário
                            if not dados.get('analise_ia'):
                                with st.spinner(f"Gerando análise preditiva para {nome_configurado}..."):
                                    prompt = f"""
                                    Analise os dados da máquina {nome_configurado} e forneça:
                                    1. Diagnóstico técnico resumido
                                    2. Recomendações de manutenção
                                    3. Estimativa de vida útil restante
                                    
                                    Dados:
                                    - Temperatura: {dados['dados_maquina'].get('Temperatura', 'N/A')}
                                    - Vibração: {dados['dados_maquina'].get('Vibração', 'N/A')}
                                    - Corrente: {dados['dados_maquina'].get('Corrente', 'N/A')}
                                    
                                    """
                                    
                                    # Adiciona informações do manual se disponível
                                    if manual_info:
                                        prompt += f"\nInformações do Manual Técnico:\n{json.dumps(manual_info, indent=2)}\n"
                                    
                                    response = client.chat.completions.create(
                                        model="gpt-4-turbo",
                                        messages=[{"role": "system", "content": "Você é um especialista em manutenção preditiva."},
                                                 {"role": "user", "content": prompt}],
                                        temperature=0.5
                                    )
                                    dados['analise_ia'] = response.choices[0].message.content
                            
                            conteudo_email += f"""
                            <div style="background: #e7f5fe; padding: 10px; border-radius: 5px; margin: 10px 0;">
                                <h3 style="color: #0c5460;">Análise Preditiva</h3>
                                <p>{dados['analise_ia'].replace('\n', '<br>')}</p>
                            </div>
                            """
                        
                        conteudo_email += "</div><hr style='border: 1px solid #eee; margin: 20px 0;'>"
                
                if dados_maquinas:
                    # Gera o PDF com as especificações
                    pdf_bytes = gerar_relatorio_completo(dados_maquinas, specs=pesquisar_especificacoes, usar_manual=usar_manual)
                    
                    # Envia o email
                    if enviar_email(
                        st.session_state.config_email,
                        f"Relatório de Manutenção - {datetime.now().strftime('%d/%m/%Y')}",
                        conteudo_email,
                        pdf_bytes=pdf_bytes
                    ):
                        st.success("✅ Relatório enviado com sucesso para {}".format(st.session_state.config_email))
                        if st.session_state.sistema_voz.ativado:
                            st.session_state.sistema_voz.falar(f"Relatório enviado com sucesso para {st.session_state.config_email}")
                    
                    # Botão para download
                    st.download_button(
                        label="⬇️ Baixar Relatório (PDF)",
                        data=pdf_bytes,
                        file_name=f"relatorio_manutencao_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
                    
                    # Mostra prévia do relatório
                    with st.expander("👁️ Prévia do Relatório", expanded=True):
                        st.markdown(conteudo_email, unsafe_allow_html=True)
                else:
                    st.warning("Nenhum dado encontrado com os filtros selecionados")
                    if st.session_state.sistema_voz.ativado:
                        st.session_state.sistema_voz.falar("Nenhum dado encontrado com os filtros selecionados.")
            
            except Exception as e:
                st.error(f"Falha ao gerar relatório: {str(e)}")
                if st.session_state.sistema_voz.ativado:
                    st.session_state.sistema_voz.falar(f"Falha ao gerar relatório: {str(e)}")

# ========== PÁGINA DE GRÁFICOS ========== #
def pagina_graficos():
    """Mostra gráficos interativos por máquina com configurações personalizadas"""
    st.title("📈 Monitoramento em Tempo Real")

    # Verifica se o modo de acessibilidade está ativado
    if st.session_state.sistema_voz.ativado:
        st.session_state.sistema_voz.falar("Página de gráficos. Aqui você pode visualizar os dados de monitoramento em tempo real.")
    
    # Configuração de estilo
    st.markdown("""
    <style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .alert-critical {
        border-left: 4px solid #dc3545;
        background-color: #f8d7da;
    }
    .alert-warning {
        border-left: 4px solid #ffc107;
        background-color: #fff3cd;
    }
    </style>
    """, unsafe_allow_html=True)
    
    try:
        abas = conectar_google_sheets()
        if not abas:
            st.error("Falha ao conectar ao Google Sheets")
            if st.session_state.sistema_voz.ativado:
                st.session_state.sistema_voz.falar("Falha ao conectar ao Google Sheets.")
            return
    except Exception as e:
        st.error(f"Erro na conexão: {str(e)}")
        if st.session_state.sistema_voz.ativado:
            st.session_state.sistema_voz.falar(f"Erro na conexão com o Google Sheets.")
        return

    if 'maquinas_config' in st.session_state:
        maquina_opcoes = [f"{m['nome']} ({m['aba']})" for m in st.session_state.maquinas_config]
        
        # Verifica se há comando de voz para seleção de máquina
        if 'ultimo_comando_voz' in st.session_state:
            comando = st.session_state.ultimo_comando_voz.lower()
            maquina_selecionada_completa = None
            
            # Procura por nome de máquina no comando
            for opcao in maquina_opcoes:
                if opcao.split("(")[0].strip().lower() in comando:
                    maquina_selecionada_completa = opcao
                    break
            
            if maquina_selecionada_completa:
                st.success(f"Máquina selecionada por voz: {maquina_selecionada_completa}")
                if st.session_state.sistema_voz.ativado:
                    st.session_state.sistema_voz.falar(f"Mostrando gráficos para {maquina_selecionada_completa}")
            else:
                st.warning(f"Nenhuma máquina encontrada para: {st.session_state.ultimo_comando_voz}")
                if st.session_state.sistema_voz.ativado:
                    st.session_state.sistema_voz.falar(f"Não encontrei a máquina {st.session_state.ultimo_comando_voz}")
            
            # Remove o comando de voz após processar
            del st.session_state.ultimo_comando_voz
        else:
            maquina_selecionada_completa = st.selectbox("Selecione a máquina:", maquina_opcoes, key="grafico_maquina")
        
        maquina_selecionada = maquina_selecionada_completa.split("(")[-1].replace(")", "")
    else:
        maquina_selecionada = st.selectbox("Selecione a máquina:", [aba.title for aba in abas], key="grafico_maquina")

    config_maquina = None
    if 'maquinas_config' in st.session_state:
        config_maquina = next((m for m in st.session_state.maquinas_config if m['aba'] == maquina_selecionada), None)

    with st.expander("⚙️ Configurações do Gráfico", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            modo_live = st.checkbox("🔴 Modo Live (atualiza a cada segundo)", value=False)
        with col2:
            if st.button("🔄 Atualizar Agora", use_container_width=True):
                st.rerun()
            mostrar_estatisticas = st.checkbox("Mostrar estatísticas detalhadas", value=True)

    # Implementação alternativa do modo Live
    if modo_live:
        if 'ultima_att' not in st.session_state:
            st.session_state.ultima_att = datetime.now()
        else:
            agora = datetime.now()
            delta = (agora - st.session_state.ultima_att).total_seconds()
            if delta >= 1:
                st.session_state.ultima_att = agora
                st.rerun()

    placeholder = st.empty()
    status_text = st.empty()

    cores = {
        'temperatura': '#FF6B6B',
        'vibracao': '#4CC9F0',
        'corrente': '#F9C74F',
        'limite': '#7209B7',
        'fundo': '#F8F9FA'
    }

    try:
        aba = next(a for a in abas if a.title == maquina_selecionada)
        dados = aba.get_all_records()
        df = pd.DataFrame(dados)

        df.columns = df.columns.str.strip().str.lower()
        df["data/hora"] = pd.to_datetime(df["data/hora"], errors="coerce", dayfirst=True)
        df["temperatura"] = df["temperatura"].apply(converter_valor_decimal)
        df["vibracao (hz)"] = df["vibracao (hz)"].apply(converter_valor_decimal)
        df["corrente (a)"] = df["corrente (a)"].apply(converter_valor_decimal)
        df = df.dropna()

        if len(df) < 2:
            placeholder.warning("Dados insuficientes para análise")
            if st.session_state.sistema_voz.ativado:
                st.session_state.sistema_voz.falar("Dados insuficientes para análise.")
            return

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df["data/hora"],
            y=df["temperatura"],
            name="Temperatura (°C)",
            line=dict(color=cores['temperatura'], width=2),
            mode='lines+markers',
            marker=dict(size=4)
        ))

        fig.add_trace(go.Scatter(
            x=df["data/hora"],
            y=df["vibracao (hz)"],
            name="Vibração (Hz)",
            line=dict(color=cores['vibracao'], width=2),
            mode='lines+markers',
            marker=dict(size=4)
        ))

        fig.add_trace(go.Scatter(
            x=df["data/hora"],
            y=df["corrente (a)"],
            name="Corrente (A)",
            line=dict(color=cores['corrente'], width=2),
            mode='lines+markers',
            marker=dict(size=4)
        ))

        if config_maquina and config_maquina.get('specs'):
            specs = config_maquina['specs']

            fig.add_hline(y=specs['temperatura_max'], line_dash="dot", line_color=cores['temperatura'], annotation_text="Lim. Temp.", annotation_position="bottom right")
            fig.add_hline(y=specs['vibracao_max'], line_dash="dot", line_color=cores['vibracao'], annotation_text="Lim. Vibração", annotation_position="bottom right")
            fig.add_hline(y=specs['corrente_nominal'], line_dash="dot", line_color=cores['corrente'], annotation_text="Corr. Nominal", annotation_position="bottom right")

            fig.add_hrect(y0=0, y1=specs['temperatura_max'], line_width=0, fillcolor=cores['temperatura'], opacity=0.1)
            fig.add_hrect(y0=0, y1=specs['vibracao_max'], line_width=0, fillcolor=cores['vibracao'], opacity=0.1)
            fig.add_hrect(y0=0, y1=specs['corrente_nominal']*1.2, line_width=0, fillcolor=cores['corrente'], opacity=0.1)

        nome_exibicao = config_maquina['nome'] if config_maquina else maquina_selecionada
        horario_atualizacao = datetime.now().strftime('%d/%m %H:%M:%S')
        fig.update_layout(
            title=f"<b>{nome_exibicao}</b> - Monitoramento em Tempo Real ({horario_atualizacao})",
            title_font_size=20,
            title_x=0.05,
            title_y=0.9,
            xaxis_title="Data/Hora",
            yaxis_title="Valores",
            plot_bgcolor=cores['fundo'],
            paper_bgcolor=cores['fundo'],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=80, b=20)
        )

        placeholder.plotly_chart(fig, use_container_width=True)

        ultima_atualizacao = datetime.now().strftime('%H:%M:%S')
        status_text.success(f"Última atualização: {ultima_atualizacao} | Dados até: {df['data/hora'].iloc[-1].strftime('%d/%m/%Y %H:%M')}")

        # Leitura em voz alta dos principais valores
        if st.session_state.sistema_voz.ativado:
            ultimo = df.iloc[-1]
            mensagem_audio = f"""
                Últimos valores para {nome_exibicao}:
                Temperatura: {ultimo['temperatura']:.1f} graus,
                Vibração: {ultimo['vibracao (hz)']:.1f} Hertz,
                Corrente: {ultimo['corrente (a)']:.1f} Ampères
            """
            st.session_state.sistema_voz.falar(mensagem_audio)

    except StopIteration:
        st.error(f"Máquina {maquina_selecionada} não encontrada nas planilhas")
        if st.session_state.sistema_voz.ativado:
            st.session_state.sistema_voz.falar(f"Máquina {maquina_selecionada} não encontrada nas planilhas.")
    except Exception as e:
        st.error(f"Erro ao processar dados: {str(e)}")
        if st.session_state.sistema_voz.ativado:
            st.session_state.sistema_voz.falar("Erro ao processar dados.")

# ========== CONFIGURAÇÃO PRINCIPAL ========== #
def main():
    """Função principal da aplicação"""
    st.set_page_config(
        page_title="Sistema de Monitoramento Preditivo",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="🏭"
    )
    
    # Inicializa o sistema de voz
    if 'sistema_voz' not in st.session_state:
        st.session_state.sistema_voz = SistemaVoz()
    
     # ========== INDICADOR VISUAL DO MODO DE ACESSIBILIDADE ========== #
    st.markdown("""
    <style>
    .modulo-acessibilidade {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #4CAF50;
        color: white;
        padding: 10px 15px;
        border-radius: 20px;
        z-index: 9999;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    </style>
    """, unsafe_allow_html=True)

    if st.session_state.sistema_voz.ativado:
        st.markdown('<div class="modulo-acessibilidade">🎤 Modo de Voz Ativo</div>', unsafe_allow_html=True)
    
    # Verifica comandos de voz continuamente
    if st.session_state.sistema_voz.ativado:
        comando = st.session_state.sistema_voz.ouvir_comando()
        if comando:
            acao = st.session_state.sistema_voz.interpretar_comando(comando)
            if acao:
                st.session_state.sistema_voz.falar(acao['resposta_audio'])
                st.session_state.sistema_voz.fila_comandos.put(acao['acao'])
        
        st.session_state.sistema_voz.processar_comandos()
    
    # Verifica se a configuração inicial foi feita
    if "configurado" not in st.session_state or not st.session_state.configurado:
        configuracao_inicial()
        return
    
    # Menu de navegação com acessibilidade
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Monitoramento", width=150)
        st.title("Navegação")
        st.write(f"📧 E-mail configurado: {st.session_state.config_email}")
        st.write(f"⏱️ Relatórios a cada: {st.session_state.config_periodo_dias} dias")
        
        if 'maquinas_config' in st.session_state and st.session_state.maquinas_config:
            st.write("### Máquinas Monitoradas")
            for maquina in st.session_state.maquinas_config:
                status = "🟢" if maquina['modo'] == "Monitoramento Básico" else "🔵"
                st.write(f"{status} {maquina['nome']}")

        pagina = st.radio(
            "Selecione a página:",
            ["Chat", "Gráficos", "Relatórios"],
            index=["Chat", "Gráficos", "Relatórios"].index(st.session_state.get('pagina_selecionada', 'Gráficos')),
            key="pagina_selecionada"
        )

        st.markdown("---")
        st.markdown("**Desenvolvido por:**")
        st.markdown("Daniel Ladeira Cuiabano e Francisco Perez")
        st.markdown("v0.0.2 Alpha")

        # Status da acessibilidade
        if st.session_state.sistema_voz.ativado:
            st.success("♿ Modo de acessibilidade ativado")
            if st.button("🔇 Desativar Acessibilidade"):
                st.session_state.sistema_voz.ativado = False
                st.rerun()
        else:
            if st.button("♿ Ativar Acessibilidade"):
                st.session_state.sistema_voz.ativado = True
                st.session_state.sistema_voz.falar("Modo de acessibilidade ativado. Pressione Ctrl+0 para desativar.")
                st.rerun()

    # Mostra a página selecionada
    if st.session_state.pagina_selecionada == "Chat":
        pagina_chat()
    elif st.session_state.pagina_selecionada == "Gráficos":
        pagina_graficos()
    elif st.session_state.pagina_selecionada == "Relatórios":
        pagina_relatorios()

if __name__ == "__main__":
    main()