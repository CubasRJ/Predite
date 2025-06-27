📊 Sistema de Monitoramento Preditivo Industrial

Um sistema completo para monitoramento e análise preditiva de máquinas industriais com integração em tempo real, relatórios automatizados e assistente por voz.

✨ Funcionalidades
Monitoramento em Tempo Real

Gráficos interativos de temperatura, vibração e corrente

Alertas automáticos baseados em limites pré-definidos

Visualização histórica dos parâmetros operacionais

Assistente IA Integrado

Chat especializado em manutenção preditiva

Pesquisa automática de manuais técnicos

Diagnóstico de problemas e recomendações

Acessibilidade por Voz

Controle por comandos de voz (navegação, relatórios)

Leitura em voz alta dos dados críticos

Ativação por atalho de teclado (Ctrl+0)

Relatórios Automatizados

Geração de PDFs com análise completa

Envio programado por e-mail

Comparativo com especificações técnicas

🛠️ Arquitetura do Sistema
🔌 Componente Arduino (Coleta de Dados)
O código Arduino é responsável pela coleta dos dados dos sensores e envio para o Google Sheets:
Arduino.ino

Principais características:

Leitura de temperatura via sensor DS18B20

Medição de vibração via sensor SW18010P (contagem de pulsos)

Medição de corrente via sensor SCT-013

Conexão WiFi segura com credenciais protegidas

Sincronização de horário via NTP

Envio periódico de dados para Google Sheets

Integração com Arduino Cloud para monitoramento remoto

📊 Script Google Apps (Processamento de Dados)
O script do Google Sheets processa os dados recebidos e os organiza na planilha:
App Script.gs

Principais características:

Cria abas dinâmicas para cada máquina monitorada

Validação robusta dos dados recebidos

Tratamento de erros detalhado

Formatação automática de datas e valores

Integração direta com Google Sheets

📦 Instalação
Configuração do Arduino:

bash
# Instale as bibliotecas necessárias
# Via PlatformIO:
pio lib install "OneWire" "DallasTemperature" "EmonLib"
Configuração do Google Script:

Crie um novo projeto no Google Apps Script

Cole o código fornecido

Implante como uma aplicação web

Atualize a URL no código Arduino

Configuração do Dashboard:

bash
git clone https://github.com/seu-usuario/monitoramento-preditivo.git
cd monitoramento-preditivo
pip install -r requirements.txt
streamlit run teste.py

📸 Diagrama de Funcionamento:
![deepseek_mermaid_20250627_ad7904](https://github.com/user-attachments/assets/e47a9347-ae09-4989-befa-e48c39ff0862)

📌 Casos de Uso
Manutenção preventiva em fábricas

Monitoramento remoto de equipamentos

Análise de desempenho de máquinas

Treinamento de equipes de manutenção

Auditoria de conformidade industrial

✉️ Contato
Daniel Cuiabano- dani.cuiabano@gmail.com

Link do Projeto: (https://github.com/CubasRJ/Predite)
