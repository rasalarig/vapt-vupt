from flask import Flask, request, jsonify
import stripe
from flask_cors import CORS
import os



app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Permitir todas as origens para a rota /api/*



# Carrega credenciais via variaveis de ambiente.
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Configure sua chave secreta do Stripe

@app.route('/pagamento/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        if not stripe.api_key:
            return jsonify(error='STRIPE_SECRET_KEY nao configurada no ambiente'), 500

        # Obtém o amount e description do corpo da requisição
        req_json = request.get_json()
        amount = req_json.get('amount')
        description = req_json.get('description')

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': description,
                    },
                    'unit_amount': amount,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='http://localhost:8100/tabs/tab2',
            cancel_url='http://localhost:4200/payment-cancel',
        )

        # Retorna o ID da sessão criada
        return jsonify(id=session.id)
    except Exception as e:
        return jsonify(error=str(e)), 400
    

@app.route('/pagamento/webhook', methods=['POST'])
def webhook():
    if not endpoint_secret:
        return jsonify(error='STRIPE_WEBHOOK_SECRET nao configurada no ambiente'), 500

    event = None
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Handle the event
    print('Unhandled event type {}'.format(event['type']))

    return jsonify(success=True)

if __name__ == '__main__':
    app.run(port=5000)