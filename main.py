import os
import json
import time
from flask import Flask, request, jsonify
import requests
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def conectar_planilha():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            
        client = gspread.authorize(creds)
        sheet_id = "1Rkdx3-Hs-TgAIHSpHha7UK-4irJwlZes0c8DoeHHn50"
        planilha = client.open_by_key(sheet_id)
        return planilha.worksheet("Cobranças Banho e Tosa")
    except Exception as e:
        return None

def carregar_credenciais_meta():
    phone_number_id = os.environ.get("PHONE_NUMBER_ID")
    access_token = os.environ.get("ACCESS_TOKEN")
    
    if phone_number_id and access_token:
        return {"phone_number_id": phone_number_id, "access_token": access_token}
    
    try:
        with open("credentials_meta.json", "r") as f:
            return json.load(f)
    except:
        return {}

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Miauau API rodando!"})

@app.route("/verificar-e-enviar", methods=["GET", "POST"])
def verificar_e_enviar():
    aba = conectar_planilha()
    if not aba:
        return jsonify({"erro": "Não foi possível conectar à planilha."}), 500

    creds_meta = carregar_credenciais_meta()
    phone_number_id = creds_meta.get("phone_number_id")
    access_token = creds_meta.get("access_token")

    if not phone_number_id or not access_token:
        return jsonify({"erro": "Credenciais da Meta não configuradas."}), 400

    try:
        # Pega todas as linhas como lista pura para inspecionar
        linhas = aba.get_all_values()
        
        if not linhas or len(linhas) < 2:
            return jsonify({"aviso": "A planilha está vazia ou tem apenas o cabeçalho.", "conteudo_lido": linhas})

        cabecalho = [h.strip().lower() for h in linhas[0]]
        
        # Tenta achar a posição da coluna "status" e "tutor"
        try:
            idx_status = cabecalho.index("status")
            idx_tutor = cabecalho.index("tutor")
            idx_telefone = cabecalho.index("telefone")
            idx_valor = cabecalho.index("valor")
            idx_pet = cabecalho.index("pet")
        except ValueError as e:
            return jsonify({"erro": f"Coluna não encontrada no cabeçalho: {e}. Cabeçalhos lidos: {cabecalho}"})

        mensagens_enviadas = 0

        # Varre da linha 2 em diante (índice 1 em diante na lista)
        for i in range(1, len(linhas)):
            linha = linhas[i]
            
            # Garante que a linha tem colunas suficientes
            if len(linha) <= idx_status:
                continue
                
            status = linha[idx_status].strip().lower()
            
            if status == "enviar":
                nome_cliente = linha[idx_tutor] if len(linha) > idx_tutor else "Cliente"
                telefone = linha[idx_telefone].strip() if len(linha) > idx_telefone else ""
                valor = linha[idx_valor] if len(linha) > idx_valor else "0,00"
                pet = linha[idx_pet] if len(linha) > idx_pet else "seu pet"

                mensagem = (
                    f"Olá, {nome_cliente}! Passando para lembrar do acerto referente ao banho e tosa do(a) {pet} no valor de R$ {valor}. "
                    f"Segue a chave Pix para pagamento: [Sua Chave Pix]. Qualquer dúvida, estamos à disposição!"
                )

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
                    aba.update_cell(i + 1, idx_status + 1, "enviado")
                    mensagens_enviadas += 1
                
                time.sleep(1)

        return jsonify({"sucesso": True, "mensagens_enviadas": mensagens_enviadas, "cabecalhos_detectados": cabecalho})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
