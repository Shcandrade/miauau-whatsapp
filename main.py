import os
import json
import time
from flask import Flask, request, jsonify
import requests
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# Configuração do escopo do Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def conectar_planilha():
    """Conecta ao Google Sheets usando credenciais da Service Account (arquivo ou variável de ambiente)"""
    try:
        # Se houver uma variável de ambiente com o JSON da service account (ideal para nuvem)
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            # Caso contrário, tenta ler do arquivo local (para testes no computador)
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            
        client = gspread.authorize(creds)
        
        # Pega o nome da planilha pelas variáveis de ambiente ou usa um padrão
        nome_planilha = os.environ.get("NOME_PLANILHA", "Miauau Banho e Tosa")
        planilha = client.open(nome_planilha)
        return planilha.sheet1 # Pega a primeira aba da planilha
    except Exception as e:
        print(f"Erro ao conectar na planilha: {e}")
        return None

def carregar_credenciais_meta():
    """Carrega as credenciais da API do WhatsApp da Meta"""
    phone_number_id = os.environ.get("PHONE_NUMBER_ID")
    access_token = os.environ.get("ACCESS_TOKEN")
    
    if phone_number_id and access_token:
        return {"phone_number_id": phone_number_id, "access_token": access_token}
    
    # Fallback para arquivo local de credenciais da meta se houver
    try:
        with open("credentials_meta.json", "r") as f:
            return json.load(f)
    except:
        return {}

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Miauau API com Google Sheets rodando com sucesso!"})

@app.route("/verificar-e-enviar", methods=["GET", "POST"])
def verificar_e_enviar():
    """Rota que varre a planilha procurando por 'enviar' e dispara as mensagens"""
aba = conectar_planilha()
    if not aba:
        return jsonify({"erro": "Não foi possível conectar à planilha do Google Sheets."}), 500

    creds_meta = carregar_credenciais_meta()
    phone_number_id = creds_meta.get("phone_number_id")
    access_token = creds_meta.get("access_token")

    if not phone_number_id or not access_token:
        return jsonify({"erro": "Credenciais da Meta (WhatsApp) não configuradas."}), 400

    try:
        # Pega todos os registros da planilha
        registros = aba.get_all_records()
        mensagens_enviadas = 0

        # Percorre cada linha da planilha
        for index, linha in enumerate(registros, start=2): # Começa na linha 2 (considerando cabeçalho na linha 1)
            status = str(linha.get("Status", "")).strip().lower()
            
            # Se o status digitado for 'enviar'
            if status == "enviar":
                nome_cliente = linha.get("Nome", "Cliente")
                telefone = str(linha.get("Telefone", "")).strip()
                valor = linha.get("Valor", "0,00")
                pet = linha.get("Pet", "seu pet")

                # Monta a mensagem personalizada
                mensagem = (
                    f"Olá, {nome_cliente}! Passando para lembrar do acerto referente ao banho e tosa do(a) {pet} no valor de R$ {valor}. "
                    f"Segue a chave Pix para pagamento: [Sua Chave Pix]. Qualquer dúvida, estamos à disposição!"
                )

                # Dispara via API da Meta
                url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "to": telefone,
                    "type": "text",
                    "text": {"body": mensagem}
                }

                response = requests.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    # Atualiza o status na planilha para 'enviado' para não repetir
                    # Supondo que a coluna de status seja a coluna 'Status'
                    # Descobrimos o número da coluna 'Status' dinamicamente ou por índice
                    celula_status = aba.find("Status")
                    if celula_status:
                        aba.update_cell(index, celula_status.col, "enviado")
                    mensagens_enviadas += 1
                
                # Pequena pausa para evitar bloqueios de taxa da API
                time.sleep(1)

        return jsonify({"sucesso": True, "mensagens_enviadas": mensagens_enviadas})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
