import requests
import json
import time
import hashlib
import hmac
import uuid
import os
from geopy.geocoders import Nominatim

def faz_cotacao_lalamove(endereco_origem, endereco_destino):
   
    body = construir_json_com_lat_lng(endereco_origem, endereco_destino)

    api_url = f"{os.getenv('LALAMOVE_BASE_URL', 'https://rest.sandbox.lalamove.com').rstrip('/')}/v3/quotations"
    api_key = os.getenv('LALAMOVE_API_KEY')
    api_secret = os.getenv('LALAMOVE_API_SECRET')

    if not api_key or not api_secret:
        raise RuntimeError('Defina LALAMOVE_API_KEY e LALAMOVE_API_SECRET nas variaveis de ambiente.')


    # Timestamp em milissegundos
    timestamp = int(time.time() * 1000)

    # Convertendo o corpo da requisição para JSON
    body_json = json.dumps(body)

    # Criar a string a ser assinada
    string_to_sign = f"{timestamp}\r\nPOST\r\n/v3/quotations\r\n\r\n{body_json}"

    # Criar a assinatura HMAC-SHA256
    signature = hmac.new(api_secret.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()

    # Criar o cabeçalho de autorização
    authorization_header = f"hmac {api_key}:{timestamp}:{signature}"


    # Cabeçalhos da requisição
    headers = {
        "Authorization": authorization_header,
        "Content-Type": "application/json",
        "Market": "BR",
        "X-Request-ID": str(uuid.uuid4()),  # Corrigido para gerar um UUID único
        "X-Api-Key": api_key,
        "X-Timestamp": str(timestamp)
    }

    # Fazer a chamada à API
    response = requests.post(api_url, json=body, headers=headers, timeout=25)
    response_data = response.json()

    # Verificar a resposta
    if response.status_code == 200 or response.status_code == 201:
        # A resposta está em formato JSON
        quotation_result = response.json()

        # Armazenando os dados em variáveis
        valor = response_data["data"]["priceBreakdown"]["total"]
        distancia = response_data["data"]["distance"]["value"]
        endereco_origem = response_data["data"]["stops"][0]["address"]
        endereco_destino = response_data["data"]["stops"][1]["address"]
        stop_id_0 = response_data["data"]["stops"][0]["stopId"]
        stop_id_1 = response_data["data"]["stops"][1]["stopId"]
        expiraEm = response_data["data"]["expiresAt"]
        quotation_id = response_data["data"]["quotationId"]

        # Exibindo os dados armazenadosaddress
        print(f"Valor: {valor}")
        print(f"Distância: {distancia} metros")
        print(f"Endereço de Origem: {endereco_origem}")
        print(f"Endereço de Destino: {endereco_destino}")
        print(f"StopId - 0: {stop_id_0}")
        print(f"StopId - 1: {stop_id_1}")
        print(f"Quotation ID: {quotation_id}")
        
        print(f"Expira em: {expiraEm}")

        return quotation_result
    else:
        print(f"Erro na chamada da API. Código de status: {response.status_code}")
        print(response.text)
        return response.text


def construir_json_com_lat_lng(endereco_origem, endereco_destino):
    # Criar um objeto geolocalizador usando Nominatim
    geolocator = Nominatim(user_agent="geoapiSparqs")
    
    # Obter a localização do endereço de origem
    localizacao_origem = geolocator.geocode(endereco_origem)
    lat_origem = localizacao_origem.latitude
    lng_origem = localizacao_origem.longitude

    # Obter a localização do endereço de destino
    localizacao_destino = geolocator.geocode(endereco_destino)
    lat_destino = localizacao_destino.latitude
    lng_destino = localizacao_destino.longitude

    # Construir o JSON com as coordenadas e endereços
    body = {
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
    return body


