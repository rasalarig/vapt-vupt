from flask import Flask, request, jsonify
import requests
import json
import time
import hashlib
import hmac
import uuid
from geopy.geocoders import Nominatim

app = Flask(__name__)

# Endpoint de Cotação
@app.route('/cotacao', methods=['POST'])
def faz_cotacao_lalamove():
    data = request.json
    endereco_origem = data.get('endereco_origem')
    endereco_destino = data.get('endereco_destino')

    if not endereco_origem or not endereco_destino:
        return jsonify({"error": "Endereço de origem e destino são necessários."}), 400

    body = construir_json_com_lat_lng(endereco_origem, endereco_destino)

    api_url = "https://rest.sandbox.lalamove.com/v3/quotations"
    api_key = 'pk_test_fa2676a55400efc369014e6fefcd4799'
    api_secret = 'sk_test_ZqzMBAveJ+S9EkM1tNJXn1wmhp/tY7igAjUfxAqMz1+y6tod2tRb7yBbrOL+D2nj'

    timestamp = int(time.time() * 1000)
    body_json = json.dumps(body)
    string_to_sign = f"{timestamp}\r\nPOST\r\n/v3/quotations\r\n\r\n{body_json}"

    signature = hmac.new(api_secret.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization_header = f"hmac {api_key}:{timestamp}:{signature}"

    headers = {
        "Authorization": authorization_header,
        "Content-Type": "application/json",
        "Market": "BR",
        "X-Request-ID": str(uuid.uuid4()),
        "X-Api-Key": api_key,
        "X-Timestamp": str(timestamp)
    }

    response = requests.post(api_url, json=body, headers=headers)
    response_data = response.json()

    if response.status_code == 200 or response.status_code == 201:
        return jsonify(response_data), 200
    else:
        return jsonify({"error": response_data}), response.status_code

def construir_json_com_lat_lng(endereco_origem, endereco_destino):
    geolocator = Nominatim(user_agent="geoapiSparqs")
    localizacao_origem = geolocator.geocode(endereco_origem)
    lat_origem = localizacao_origem.latitude
    lng_origem = localizacao_origem.longitude

    localizacao_destino = geolocator.geocode(endereco_destino)
    lat_destino = localizacao_destino.latitude
    lng_destino = localizacao_destino.longitude

    return {
        "data": {
            "serviceType": "CAR",
            "specialRequests": ["LOADING_1DRIVER_MAX030MIN"],
            "language": "pt_BR",
            "stops": [
                {
                    "coordinates": {"lat": str(lat_origem), "lng": str(lng_origem)},
                    "address": endereco_origem
                },
                {
                    "coordinates": {"lat": str(lat_destino), "lng": str(lng_destino)},
                    "address": endereco_destino
                }
            ],
            "isRouteOptimized": True,
            "item": {
                "quantity": "1",
                "weight": "LESS_THAN_3_KG",
                "categories": ["FOOD_DELIVERY", "OFFICE_ITEM"],
                "handlingInstructions": ["KEEP_UPRIGHT"]
            }
        }
    }

# Endpoint para visualizar a documentação
@app.route('/docs', methods=['GET'])
def docs():
    openapi_spec = """
    openapi: 3.0.0
    info:
      title: API de Integração com Transportadoras
      description: API para realizar cotações e pedidos com transportadoras como Lalamove.
      version: 1.0.0
    paths:
      /cotacao:
        post:
          summary: Realiza uma cotação de entrega
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    endereco_origem:
                      type: string
                      example: "Rua A, 123"
                    endereco_destino:
                      type: string
                      example: "Rua B, 456"
          responses:
            '200':
              description: Cotação realizada com sucesso
              content:
                application/json:
                  schema:
                    type: object
            '400':
              description: Requisição inválida
    """
    return openapi_spec, 200, {'Content-Type': 'text/yaml'}

if __name__ == '__main__':
    app.run(port=5000)
