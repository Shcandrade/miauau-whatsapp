import os
import json
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Carrega as credenciais de forma segura (do arquivo local ou das Variáveis de Ambiente da nuvem)
def load_credentials():
    # Tenta pegar das variáveis de ambiente do Render primeiro
    phone_number_id = os.environ.get("PHONE_NUMBER_ID")
    access_token = os.environ.get("ACCESS_TOKEN")
    
    if phone_number_id and access_token:
        return {
            "phone_number_id": phone_number_id,
            "access_token": access_token
        }
    
    # Se não estiver nas variáveis de ambiente, tenta ler do arquivo local (para testes no PC)
    try:
        with open("credentials.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Aviso: credentials.json não encontrado e variáveis de ambiente não definidas: {e}")
        return {}

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Miauau API rodando com sucesso!", "service": "Banho e Tosa"})

@app.route("/enviar-cobranca", methods=["POST"])
def enviar_cobranca():
    creds = load_credentials()
    
    phone_number_id = creds.get("phone_number_id")
    access_token = creds.get("access_token")
    
    if not phone_number_id or not access_token:
        return jsonify({"erro": "Credenciais incompletas. Verifique as variáveis de ambiente ou o credentials.json"}), 400

    dados = request.json
    telefone_cliente = dados.get("telefone") # Ex: 5524999999999
    nome_cliente = dados.get("nome", "Cliente")
    valor = dados.get("valor", "0,00")

    # Mensagem padrão de cobrança do banho e tosa
    mensagem = (
        f"Olá, {nome_cliente}! Passando para lembrar do acerto referente ao banho e tosa do seu pet no valor de R$ {valor}. "
        f"Segue a chave Pix para pagamento: [Sua Chave Pix]. Qualquer dúvida, estamos à disposição!"
    )

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_cliente,
        "type": "text",
        "text": {"body": mensagem}
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return jsonify({"sucesso": True, "resposta_meta": response.json()})
    else:
        return jsonify({"sucesso": False, "erro": response.text}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
