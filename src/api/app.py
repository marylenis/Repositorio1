from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Response
import requests
import os
import logging
from src.paking_agent.agent import ParkingAgent, GetParkingDataAgent
from supabase import create_client, Client
from typing import Dict

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppState:
    def __init__(self):
        self.avoid_response = False
        self.current_question: str = ""
        self.saved_data = False
        self.existing_answers = {
            "nombre_de_parqueadero": False,
            "ubicacion": False,
            "servicios": False,
            "servicios_adicionales": False,
            "informacion_adicional": False
        }

async def get_existing_answers(client_id: str) -> dict:
    """Get existing answers from Supabase for a client"""
    try:
        response = supabase.table("answers").select("question", "answer").eq("client_id", client_id).execute()
        
        # Initialize the answers dictionary with default values
        answers = {
            "nombre_de_parqueadero": False,
            "ubicacion": False,
            "servicios": False,
            "servicios_adicionales": False,
            "informacion_adicional": False
        }
        
        # Update with existing data
        if response.data:
            for row in response.data:
                answers[row['question']] = True
            
        logger.info(f"Retrieved existing answers for client {client_id}: {answers}")
        return answers
        
    except Exception as e:
        logger.error(f"Error retrieving existing answers: {str(e)}")
        raise

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, AppState] = {}
    
    async def get_session(self, phone_number: str) -> AppState:
        if phone_number not in self.sessions:
            # Create new session
            session = AppState()
            
            try:
                # Get existing answers from Supabase
                existing_answers = await get_existing_answers(phone_number)
                session.existing_answers = existing_answers
                
                # If we have any answers, mark as saved
                session.saved_data = any(existing_answers.values())
                
                # If we have all answers, mark avoid_response as True
                if all(existing_answers.values()):
                    session.avoid_response = True
                
            except Exception as e:
                logger.error(f"Error initializing session with existing data: {str(e)}")
            
            self.sessions[phone_number] = session
            
        return self.sessions[phone_number]

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase credentials not found in environment variables")

# Ensure URL is properly formatted
supabase_url = supabase_url.rstrip('/')  # Remove trailing slashes if any

try:
    # Initialize with service role key
    supabase: Client = create_client(supabase_url, supabase_key)
    logger.info("Successfully connected to Supabase")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise

# Initialize session manager
session_manager = SessionManager()

# Other configurations
whatsapp_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
whatsapp_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
parking_agent = ParkingAgent()
get_parking_data_agent = GetParkingDataAgent()

async def save_answer(client_id: str, question: str, answer: str):
    """Save answer to Supabase"""
    try:
        data = {
            "client_id": client_id,
            "question": question,
            "answer": answer
        }
        
        # Using execute() to get the response
        response = supabase.table("answers").insert(data).execute()
        
        if not response.data:
            raise Exception("No data returned from insert operation")
            
        logger.info(f"Successfully saved answer to database for client {client_id}")
        return response.data[0]
        
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        # Log additional details for debugging
        logger.error(f"Attempted to save: client_id={client_id}, question={question}")
        # Re-raise the exception to be handled by the caller
        raise

@app.post("/send-whatsapp-template")
async def send_whatsapp_template(
    phone_number: str,
    template_name: str = "parking_setup_start",
    language_code: str = "es",
    image_id: str = "505488948947747"
):
    
    if not whatsapp_phone_number_id or not whatsapp_access_token:
        raise HTTPException(status_code=500, detail="WhatsApp API credentials not configured")
    
    # WhatsApp Cloud API endpoint
    url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_number_id}/messages"
    
    # Prepare the request payload with image header component
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            },
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {
                                "id": image_id
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    # Set headers with access token
    headers = {
        "Authorization": f"Bearer {whatsapp_access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Send the request to WhatsApp Cloud API
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error sending WhatsApp template: {str(e)}")

@app.post("/upload-whatsapp-image")
async def upload_whatsapp_image(
    file: UploadFile = File(...),
    messaging_product: str = Form("whatsapp")
):

    
    if not whatsapp_phone_number_id or not whatsapp_access_token:
        raise HTTPException(status_code=500, detail="WhatsApp API credentials not configured")
    
    # WhatsApp Cloud API media upload endpoint
    url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_number_id}/media"
    
    # Read file content
    file_content = await file.read()
    
    # Prepare the multipart form data
    files = {
        'file': (file.filename, file_content, file.content_type)
    }
    
    data = {
        'messaging_product': messaging_product,
        'type': file.content_type
    }
    
    # Set headers with access token
    headers = {
        "Authorization": f"Bearer {whatsapp_access_token}"
    }
    
    try:
        # Send the request to WhatsApp Cloud API
        response = requests.post(url, files=files, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image to WhatsApp: {str(e)}")

@app.post("/webhook")
async def webhook(request: Request):
    """
    Handle incoming webhook notifications from WhatsApp.
    This endpoint receives message status updates and incoming messages.
    """
    try:
        # Get the request body
        body = await request.json()
        logger.info(f"Received webhook: {body}")
        
        # Get the first change from the webhook
        change = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
        
        # Handle different types of webhooks
        if "messages" in change:
            # Handle incoming messages
            logger.info("Received incoming message")
            message = change.get("messages", [{}])[0]
            phone_number = message.get("from", "")
            
            if message.get("type") == "text":
                message_text = message.get("text", {}).get("body", "")
                if message_text and phone_number:
                    logger.info(f"Received message from {phone_number}: {message_text}")
                    
                    # Get or create session for this phone number
                    session = await session_manager.get_session(phone_number)
                    
                    if session.avoid_response:
                        # Si avoid_response es True, enviamos el mensaje de finalización
                        await send_whatsapp_message(
                            phone_number, 
                            "El proceso de onboarding ha finalizado, si quieres obtener más información hazlo por la plataforma de back office."
                        )
                        return {"status": "success"}
                    
                    try:
                        # Get response from parking agent
                        response_text = parking_agent.get_response(message_text)
                        
                        # Only try to extract parking data if we have a meaningful message
                        if len(message_text) > 1:
                            try:
                                # Get parking data
                                parking_data = get_parking_data_agent.extract_parking_data(message_text)
                                logger.info(f"Extracted parking data: {parking_data}")
                                
                                # Save structured data to Supabase if not already saved
                                if parking_data.parking_name and not session.existing_answers["nombre_de_parqueadero"]:
                                    await save_answer(phone_number, "nombre_de_parqueadero", parking_data.parking_name)
                                    session.existing_answers["nombre_de_parqueadero"] = True
                                
                                if parking_data.location and not session.existing_answers["ubicacion"]:
                                    await save_answer(phone_number, "ubicacion", parking_data.location)
                                    session.existing_answers["ubicacion"] = True
                                
                                if parking_data.services and not session.existing_answers["servicios"]:
                                    await save_answer(phone_number, "servicios", ", ".join(parking_data.services))
                                    session.existing_answers["servicios"] = True
                                
                                if parking_data.additional_services and not session.existing_answers["servicios_adicionales"]:
                                    await save_answer(phone_number, "servicios_adicionales", ", ".join(parking_data.additional_services))
                                    session.existing_answers["servicios_adicionales"] = True
                                
                                if parking_data.additional_information and not session.existing_answers["informacion_adicional"]:
                                    await save_answer(phone_number, "informacion_adicional", parking_data.additional_information)
                                    session.existing_answers["informacion_adicional"] = True
                                
                                # Verificar si tenemos toda la información requerida
                                required_fields = ["nombre_de_parqueadero", "ubicacion", "servicios"]
                                has_required_fields = all(session.existing_answers[field] for field in required_fields)
                                
                                # Solo activamos avoid_response si tenemos todos los campos requeridos Y hay confirmación
                                if has_required_fields and parking_data.confirmation:
                                    session.avoid_response = True
                                    logger.info(f"All required information collected and confirmed for {phone_number}")
                                elif not has_required_fields and parking_data.confirmation:
                                    # Si intenta confirmar pero faltan campos requeridos, lo notificamos
                                    missing_fields = [field for field in required_fields if not session.existing_answers[field]]
                                    logger.info(f"Attempted confirmation but missing fields: {missing_fields}")
                                    # Aquí podríamos modificar response_text para indicar qué información falta

                            except Exception as e:
                                logger.warning(f"Could not extract parking data: {str(e)}")
                        
                        # Send response back to user
                        await send_whatsapp_message(phone_number, response_text)
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        # Send error message to user
                        await send_whatsapp_message(phone_number, "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo.")
            
        elif "statuses" in change:
            # Handle message status updates
            status = change.get("statuses", [{}])[0]
            logger.info(f"Message status update: {status.get('status')} for message {status.get('id')}")
            
        # Return a 200 OK response to acknowledge receipt
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def send_whatsapp_message(to: str, message: str):
    """Helper function to send WhatsApp messages"""
    url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_number_id}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {
            "body": message
        }
    }
    
    headers = {
        "Authorization": f"Bearer {whatsapp_access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Message sent successfully to {to}")
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Handle the verification request from WhatsApp when setting up the webhook.
    """
    # Get query parameters
    params = dict(request.query_params)
    
    # WhatsApp sends a verification token that you need to echo back
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    # You should set this verification token in your WhatsApp Business Account
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    
    # Check if mode and token are correct
    if mode == "subscribe" and token == verify_token:
        logger.info("Webhook verified successfully")
        # Return the challenge to verify the webhook
        return Response(content=challenge)
    else:
        logger.warning("Webhook verification failed")
        return Response(content="Verification failed", status_code=403)







