from flask import Flask, request, jsonify, make_response
import requests
import json
import time
import hashlib
import hmac
import uuid
import re
import math
import os
from datetime import datetime, timedelta, timezone
from geopy.geocoders import Nominatim
from flask_cors import CORS


def load_local_env_once():
    env_path = os.path.join(os.path.dirname(__file__), '.env.local')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


load_local_env_once()


def try_parse_lat_lng(value):
    if not isinstance(value, str):
        return None

    parts = [part.strip() for part in value.split(',')]
    if len(parts) != 2:
        return None

    try:
        lat = float(parts[0])
        lng = float(parts[1])
    except ValueError:
        return None

    if lat < -90 or lat > 90 or lng < -180 or lng > 180:
        return None

    return lat, lng


def resolve_coordinates(raw_value, geolocator, field_name):
    parsed = try_parse_lat_lng(raw_value)
    if parsed is not None:
        return parsed

    # Tenta variacoes do endereco para reduzir ambiguidades comuns.
    candidates = [
        raw_value,
        f"{raw_value}, Sao Paulo, SP, Brasil",
        f"{raw_value}, Brasil",
    ]

    seen = set()
    for query in candidates:
        normalized = query.strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)

        try:
            location = geolocator.geocode(
                query,
                country_codes='br',
                exactly_one=True,
                addressdetails=False,
                timeout=10,
            )
        except Exception:
            location = None

        if location:
            return location.latitude, location.longitude

    raise ValueError(
        f"Nao foi possivel geocodificar {field_name}. "
        "Tente informar endereco com numero, cidade e UF (ex.: Rua Augusta, 200, Sao Paulo, SP)."
    )


def resolve_coordinates_with_reference(raw_value, geolocator, field_name, ref_lat=None, ref_lng=None):
    parsed = try_parse_lat_lng(raw_value)
    if parsed is not None:
        return parsed

    if ref_lat is not None and ref_lng is not None:
        locations = geolocator.geocode(raw_value, country_codes='br', exactly_one=False, limit=5)
        if locations:
            best = min(
                locations,
                key=lambda loc: ((loc.latitude - ref_lat) ** 2) + ((loc.longitude - ref_lng) ** 2),
            )
            return best.latitude, best.longitude

    return resolve_coordinates(raw_value, geolocator, field_name)


def geocode_candidates(geolocator, candidates, ref_lat=None, ref_lng=None):
    for candidate in candidates:
        if not candidate:
            continue

        try:
            if isinstance(candidate, dict):
                locations = geolocator.geocode(candidate, exactly_one=False, limit=5, addressdetails=False, timeout=10)
            else:
                locations = geolocator.geocode(candidate, country_codes='br', exactly_one=False, limit=5, addressdetails=False, timeout=10)
        except Exception:
            locations = None

        if not locations:
            continue

        if not isinstance(locations, list):
            locations = [locations]

        if ref_lat is not None and ref_lng is not None:
            best = min(
                locations,
                key=lambda loc: ((loc.latitude - ref_lat) ** 2) + ((loc.longitude - ref_lng) ** 2),
            )
        else:
            best = locations[0]

        return best.latitude, best.longitude, candidate

    return None, None, None


def normalize_cep(cep):
    if not isinstance(cep, str):
        return None

    digits = ''.join(ch for ch in cep if ch.isdigit())
    if len(digits) != 8:
        return None

    return digits


def sanitize_address_for_geocode(value):
    if not isinstance(value, str):
        return value

    cleaned = value.strip()

    # Remove sufixos comuns vindos da UI, como "- CEP 01311-000".
    cleaned = re.sub(r"\s*-?\s*CEP\s*\d{5}-?\d{3}\s*$", "", cleaned, flags=re.IGNORECASE)

    # Colapsa espacos repetidos e remove virgulas sobrando no fim.
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned


def compose_address(logradouro='', numero='', bairro='', cidade='', uf='', cep=''):
    first = logradouro.strip()
    if numero and numero.strip():
        first = f"{first}, {numero.strip()}" if first else numero.strip()

    tail_parts = [part.strip() for part in [bairro, cidade, uf] if part and part.strip()]
    tail = ', '.join(tail_parts)

    pieces = [part for part in [first, tail] if part]
    composed = ', '.join(pieces)

    if cep and cep.strip():
        composed = f"{composed} - CEP {cep.strip()}" if composed else f"CEP {cep.strip()}"

    return composed


def iso_z(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.00Z')


def haversine_distance_m(lat1, lon1, lat2, lon2):
    radius_m = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_m * c


def build_loggi_quote(payload_body, service_type, language, special_requests):
    stops = payload_body["data"]["stops"]
    origin = stops[0]
    destination = stops[1]

    lat1 = float(origin["coordinates"]["lat"])
    lng1 = float(origin["coordinates"]["lng"])
    lat2 = float(destination["coordinates"]["lat"])
    lng2 = float(destination["coordinates"]["lng"])

    distance_m = max(1, int(round(haversine_distance_m(lat1, lng1, lat2, lng2))))
    distance_km = distance_m / 1000

    base_map = {
        "MOTORCYCLE": 11.50,
        "CAR": 14.00,
        "VAN": 22.00,
    }
    base = base_map.get(service_type, 14.00)
    extra_mileage = distance_km * 1.55
    extra_requests = max(0, len(special_requests) - 1) * 4.50
    total = base + extra_mileage + extra_requests

    now = datetime.now(timezone.utc)
    schedule_at = now + timedelta(minutes=2)
    expires_at = now + timedelta(minutes=5)

    estimated_minutes = max(12, int(round(distance_km * 2.8 + 8)))

    return {
        "provider": "LOGGI",
        "data": {
            "distance": {
                "unit": "m",
                "value": str(distance_m),
            },
            "expiresAt": iso_z(expires_at),
            "scheduleAt": iso_z(schedule_at),
            "isRouteOptimized": bool(payload_body["data"].get("isRouteOptimized", True)),
            "language": (language or "pt_BR").upper(),
            "serviceType": service_type,
            "specialRequests": special_requests,
            "quotationId": f"LOGGI-{uuid.uuid4().hex[:12].upper()}",
            "estimatedDeliveryMinutes": estimated_minutes,
            "priceBreakdown": {
                "currency": "BRL",
                "base": f"{base:.2f}",
                "extraMileage": f"{extra_mileage:.2f}",
                "specialRequests": f"{extra_requests:.2f}",
                "total": f"{total:.2f}",
                "totalBeforeOptimization": f"{total:.2f}",
                "totalExcludePriorityFee": f"{total:.2f}",
            },
            "stops": [
                {
                    "address": origin["address"],
                    "coordinates": origin["coordinates"],
                    "stopId": f"LOGGI-STOP-{uuid.uuid4().hex[:10].upper()}",
                },
                {
                    "address": destination["address"],
                    "coordinates": destination["coordinates"],
                    "stopId": f"LOGGI-STOP-{uuid.uuid4().hex[:10].upper()}",
                },
            ],
        },
    }

app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    return response


@app.route('/health', methods=['GET'])
def healthcheck():
    return jsonify({"status": "ok"}), 200

# Endpoint de Cotação
@app.route('/cotacao', methods=['POST', 'OPTIONS'])
def faz_cotacao():
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'POST,OPTIONS'
        return response

    data = request.json or {}
    endereco_origem = data.get('endereco_origem')
    endereco_destino = data.get('endereco_destino')
    endereco_origem_label = data.get('endereco_origem_label') or endereco_origem
    endereco_destino_label = data.get('endereco_destino_label') or endereco_destino
    provider = (data.get('provider') or 'lalamove').strip().lower()
    if provider == 'loggy':
        provider = 'loggi'

    if not endereco_origem or not endereco_destino:
        response = make_response(jsonify({"error": "Endereço de origem e destino são necessários."}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    try:
        service_type = (data.get('service_type') or 'CAR').strip().upper()
        language = (data.get('language') or 'pt_BR').strip()
        market = (data.get('market') or 'BR').strip().upper()

        special_requests = data.get('special_requests', ["LOADING_1DRIVER_MAX030MIN"])

        body = construir_json_com_lat_lng(
            endereco_origem=endereco_origem,
            endereco_destino=endereco_destino,
            endereco_origem_label=endereco_origem_label,
            endereco_destino_label=endereco_destino_label,
            service_type=service_type,
            special_requests=special_requests,
            language=language,
            is_route_optimized=data.get('is_route_optimized', True),
            item=data.get('item', {}),
        )
    except ValueError as e:
        response = make_response(jsonify({"error": str(e)}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    if provider == 'loggi':
        response_data = build_loggi_quote(
            payload_body=body,
            service_type=service_type,
            language=language,
            special_requests=special_requests if isinstance(special_requests, list) else [],
        )
        flask_response = make_response(jsonify(response_data), 200)
        flask_response.headers['Access-Control-Allow-Origin'] = '*'
        return flask_response

    lalamove_base_url = os.getenv('LALAMOVE_BASE_URL', 'https://rest.sandbox.lalamove.com').rstrip('/')
    api_url = f"{lalamove_base_url}/v3/quotations"
    api_key = os.getenv('LALAMOVE_API_KEY')
    api_secret = os.getenv('LALAMOVE_API_SECRET')

    if not api_key or not api_secret:
        response = make_response(jsonify({
            "error": (
                "Credenciais da Lalamove nao configuradas. "
                "Defina LALAMOVE_API_KEY e LALAMOVE_API_SECRET no ambiente."
            )
        }), 500)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    timestamp = int(time.time() * 1000)
    body_json = json.dumps(body)
    string_to_sign = f"{timestamp}\r\nPOST\r\n/v3/quotations\r\n\r\n{body_json}"

    signature = hmac.new(api_secret.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization_header = f"hmac {api_key}:{timestamp}:{signature}"

    headers = {
        "Authorization": authorization_header,
        "Content-Type": "application/json",
        "Market": market,
        "X-Request-ID": str(uuid.uuid4()),
        "X-Api-Key": api_key,
        "X-Timestamp": str(timestamp)
    }

    response = requests.post(api_url, json=body, headers=headers, timeout=25)
    response_data = response.json()

    if response.status_code == 200 or response.status_code == 201:
        if isinstance(response_data, dict):
            response_data["provider"] = "LALAMOVE"

        flask_response = make_response(jsonify(response_data), 200)
        flask_response.headers['Access-Control-Allow-Origin'] = '*'
        return flask_response

    errors = response_data.get('errors') if isinstance(response_data, dict) else None
    if response.status_code == 422 and isinstance(errors, list):
        has_out_of_service = any(
            isinstance(error, dict) and error.get('id') == 'ERR_OUT_OF_SERVICE_AREA'
            for error in errors
        )
        if has_out_of_service:
            response_data['hint'] = (
                "Origem ou destino fora da area de atendimento da Lalamove. "
                "Use pontos em cidade atendida e, se possivel, informe no formato lat,lng."
            )

    flask_response = make_response(jsonify({"error": response_data}), response.status_code)
    flask_response.headers['Access-Control-Allow-Origin'] = '*'
    return flask_response


@app.route('/geocode', methods=['POST', 'OPTIONS'])
def geocode_address():
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'POST,OPTIONS'
        return response

    data = request.json or {}
    endereco = data.get('endereco')
    cidade_uf = (data.get('cidade_uf') or '').strip()
    ref_lat = data.get('ref_lat')
    ref_lng = data.get('ref_lng')
    logradouro = (data.get('logradouro') or '').strip()
    numero = (data.get('numero') or '').strip()
    bairro = (data.get('bairro') or '').strip()
    cidade = (data.get('cidade') or '').strip()
    uf = (data.get('uf') or '').strip()
    cep = (data.get('cep') or '').strip()

    try:
        ref_lat = float(ref_lat) if ref_lat is not None else None
        ref_lng = float(ref_lng) if ref_lng is not None else None
    except (ValueError, TypeError):
        ref_lat = None
        ref_lng = None

    if not endereco and not logradouro:
        response = make_response(jsonify({"error": "Endereco e obrigatorio."}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    endereco_consulta = sanitize_address_for_geocode((endereco or '').strip())
    cep_normalized = normalize_cep(cep) if cep else None

    if logradouro:
        endereco_consulta = compose_address(
            logradouro=logradouro,
            numero=numero,
            bairro=bairro,
            cidade=cidade,
            uf=uf,
            cep=cep_normalized or cep,
        )

    if cidade_uf and cidade_uf.lower() not in endereco_consulta.lower():
        endereco_consulta = f"{endereco_consulta}, {cidade_uf}, Brasil"

    geolocator = Nominatim(user_agent="geoapiSparqs")
    street = f"{logradouro}, {numero}" if logradouro and numero else logradouro
    structured_query = {
        "street": street,
        "city": cidade,
        "state": uf,
        "postalcode": cep_normalized,
        "country": "Brasil",
    }
    structured_query = {k: v for k, v in structured_query.items() if v}

    candidates = []
    if structured_query:
        candidates.append(structured_query)

    candidates.append(endereco_consulta)
    if cidade_uf:
        candidates.append(f"{endereco_consulta}, {cidade_uf}")

    lat, lng, used_query = geocode_candidates(
        geolocator,
        candidates,
        ref_lat=ref_lat,
        ref_lng=ref_lng,
    )

    if lat is None or lng is None:
        response = make_response(jsonify({
            "error": (
                "Nao foi possivel geocodificar o endereco informado. "
                "Tente informar endereco com numero, cidade e UF (ex.: Rua Augusta, 200, Sao Paulo, SP)."
            ),
            "endereco_consultado": endereco_consulta,
            "logradouro": logradouro,
            "cidade": cidade,
            "uf": uf,
            "cep": cep,
        }), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    response = make_response(jsonify({
        "lat": lat,
        "lng": lng,
        "endereco_consultado": endereco_consulta,
        "query_utilizada": used_query,
    }), 200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/cep/<cep>', methods=['GET', 'OPTIONS'])
def lookup_cep(cep):
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
        return response

    normalized = normalize_cep(cep)
    if not normalized:
        response = make_response(jsonify({"error": "CEP invalido. Informe 8 digitos."}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    try:
        via_cep = requests.get(f"https://viacep.com.br/ws/{normalized}/json/", timeout=10)
        via_cep.raise_for_status()
        data = via_cep.json()
    except Exception:
        response = make_response(jsonify({"error": "Falha ao consultar ViaCEP."}), 502)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    if data.get('erro'):
        response = make_response(jsonify({"error": "CEP nao encontrado."}), 404)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    logradouro = data.get('logradouro', '').strip()
    bairro = data.get('bairro', '').strip()
    localidade = data.get('localidade', '').strip()
    uf = data.get('uf', '').strip()

    endereco_base = compose_address(
        logradouro=logradouro,
        numero='',
        bairro=bairro,
        cidade=localidade,
        uf=uf,
        cep=data.get('cep', ''),
    )

    response_payload = {
        "cep": data.get('cep'),
        "logradouro": logradouro,
        "complemento": data.get('complemento', '').strip(),
        "bairro": bairro,
        "cidade": localidade,
        "uf": uf,
        "endereco_base": endereco_base,
        "endereco_completo": endereco_base,
    }

    response = make_response(jsonify(response_payload), 200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/reverse-geocode', methods=['POST', 'OPTIONS'])
def reverse_geocode():
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'POST,OPTIONS'
        return response

    data = request.json or {}
    lat = data.get('lat')
    lng = data.get('lng')

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        response = make_response(jsonify({"error": "Latitude/longitude invalidas."}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    geolocator = Nominatim(user_agent="geoapiSparqs")
    try:
        location = geolocator.reverse(
            (lat, lng),
            exactly_one=True,
            language='pt-BR',
            addressdetails=True,
            zoom=18,
        )
    except Exception:
        location = None

    if not location:
        response = make_response(jsonify({"error": "Nao foi possivel obter endereco pela localizacao."}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    address = location.raw.get('address', {}) if isinstance(location.raw, dict) else {}
    road = address.get('road') or address.get('pedestrian') or address.get('footway') or ''
    house_number = address.get('house_number') or ''
    suburb = address.get('suburb') or address.get('neighbourhood') or ''
    city = address.get('city') or address.get('town') or address.get('village') or address.get('municipality') or ''
    state = address.get('state') or ''
    postcode = address.get('postcode') or ''

    endereco_completo = compose_address(
        logradouro=road,
        numero=house_number,
        bairro=suburb,
        cidade=city,
        uf=state,
        cep=postcode,
    )

    response_payload = {
        "lat": lat,
        "lng": lng,
        "logradouro": road,
        "numero": house_number,
        "bairro": suburb,
        "cidade": city,
        "uf": state,
        "cep": postcode,
        "endereco_base": compose_address(
            logradouro=road,
            numero='',
            bairro=suburb,
            cidade=city,
            uf=state,
            cep=postcode,
        ),
        "endereco_completo": endereco_completo,
    }

    response = make_response(jsonify(response_payload), 200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


def construir_json_com_lat_lng(
    endereco_origem,
    endereco_destino,
    endereco_origem_label=None,
    endereco_destino_label=None,
    service_type='CAR',
    special_requests=None,
    language='pt_BR',
    is_route_optimized=True,
    item=None,
):
    geolocator = Nominatim(user_agent="geoapiSparqs")
    lat_origem, lng_origem = resolve_coordinates(endereco_origem, geolocator, 'o endereco de origem')
    lat_destino, lng_destino = resolve_coordinates(endereco_destino, geolocator, 'o endereco de destino')

    if special_requests is None:
        special_requests = ["LOADING_1DRIVER_MAX030MIN"]

    if item is None:
        item = {}

    categories = item.get("categories")
    if not isinstance(categories, list) or len(categories) == 0:
        categories = ["FOOD_DELIVERY", "OFFICE_ITEM"]

    handling_instructions = item.get("handlingInstructions")
    if not isinstance(handling_instructions, list) or len(handling_instructions) == 0:
        handling_instructions = ["KEEP_UPRIGHT"]

    special_requests = special_requests if isinstance(special_requests, list) else []
    special_requests = [value for value in special_requests if value]
    if len(special_requests) == 0:
        special_requests = ["LOADING_1DRIVER_MAX030MIN"]

    normalized_item = {
        "quantity": item.get("quantity") or "1",
        "weight": item.get("weight") or "LESS_THAN_3_KG",
        "categories": categories,
        "handlingInstructions": handling_instructions,
    }

    return {
        "data": {
            "serviceType": service_type,
            "specialRequests": special_requests,
            "language": language,
            "stops": [
                {
                    "coordinates": {"lat": str(lat_origem), "lng": str(lng_origem)},
                    "address": endereco_origem_label or endereco_origem
                },
                {
                    "coordinates": {"lat": str(lat_destino), "lng": str(lng_destino)},
                    "address": endereco_destino_label or endereco_destino
                }
            ],
            "isRouteOptimized": bool(is_route_optimized),
            "item": normalized_item
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
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')))
