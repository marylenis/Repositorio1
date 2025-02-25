from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Response
import requests
import os
import logging
from src.paking_agent.agent import ParkingAgent

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

whatsapp_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
whatsapp_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
parking_agent = ParkingAgent()
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
        
        # Check if this is an incoming message
        if "messages" in body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}):
            logger.info("Received incoming message")
            
            # Extract the message text and sender's phone number
            message = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [{}])[0].get("text", {}).get("body", "")
            phone_number = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [{}])[0].get("from", "")
            
            if message and phone_number:
                logger.info(f"Received message from {phone_number}: {message}")

                # Send a response back to the user
                url = f"https://graph.facebook.com/v17.0/{whatsapp_phone_number_id}/messages"
                
                # Simple text response
                response_text = parking_agent.get_response(message)
                
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": phone_number,
                    "type": "text",
                    "text": {
                        "body": response_text
                    }
                }
                
                headers = {
                    "Authorization": f"Bearer {whatsapp_access_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(url, json=payload, headers=headers)
                logger.info(f"Response sent to {phone_number}: {response.status_code}")
                logger.info(f"Response content: {response.text}")
        
        # For message status updates
        if "statuses" in body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}):
            logger.info("Received message status update")
            
        # Return a 200 OK response to acknowledge receipt
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return Response(content=f"Error processing webhook: {str(e)}", status_code=500)

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
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_verification_token")
    
    # Check if mode and token are correct
    if mode == "subscribe" and token == verify_token:
        logger.info("Webhook verified successfully")
        # Return the challenge to verify the webhook
        return Response(content=challenge)
    else:
        logger.warning("Webhook verification failed")
        return Response(content="Verification failed", status_code=403)







