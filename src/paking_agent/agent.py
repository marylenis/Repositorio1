from langchain_community.chat_models import ChatOpenAI
from src.paking_agent.prompt import parking_agent_prompt, get_parking_data_prompt
from src.paking_agent.models import ParkingData
from dotenv import load_dotenv
import json

load_dotenv()


class Agent:
    """ Class to handle the agent """
    def __init__(self, system_prompt: str):
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0)
        self.messages = [{"role": "system", "content": system_prompt}]
        self.first_message = True

    def get_response(self, user_input):
        """ Get response from LLM """
        self.messages.append({"role": "user", "content": user_input})
        response = self.llm.invoke(self.messages).content
        self.messages.append({"role": "assistant", "content": response})
        return response


class ParkingAgent(Agent):
    """ Class to handle the parking agent """
    def __init__(self):
        super().__init__(parking_agent_prompt)  
        self.first_message = True


class GetParkingDataAgent(Agent):
    """ Class to handle the get parking data agent """
    def __init__(self):
        super().__init__(get_parking_data_prompt)
        self.first_message = True
        
    def extract_parking_data(self, conversation_text: str) -> ParkingData:
        """
        Analiza el texto de la conversación y extrae los datos en un objeto ParkingData
        Args:
            conversation_text: Texto de la conversación a analizar
        Returns:
            ParkingData: Objeto con la información estructurada del parqueadero
        """
        # Si el texto es muy corto o no relevante, devolvemos un objeto vacío
        if len(conversation_text.strip()) <= 2:
            return ParkingData(
                parking_name="",
                location="",
                services=[],
                additional_services=[],
                additional_information="",
                confirmation=False
            )
            
        try:
            # Enviamos la conversación al LLM para que extraiga la información
            response = self.get_response(conversation_text)
            
            # Limpiamos la respuesta de cualquier texto adicional que pueda haber
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Intentamos parsear la respuesta JSON
            try:
                data_dict = json.loads(response)
            except json.JSONDecodeError:
                # Si falla, intentamos una última vez limpiando más la respuesta
                response = ''.join(line.strip() for line in response.splitlines())
                data_dict = json.loads(response)
            
            # Aseguramos que todos los campos requeridos estén presentes
            default_data = {
                "parking_name": "",
                "location": "",
                "services": [],
                "additional_services": [],
                "additional_information": "",
                "confirmation": False
            }
            
            # Combinamos los datos por defecto con los extraídos
            data_dict = {**default_data, **data_dict}
            
            # Convertimos null a valores por defecto
            for key in data_dict:
                if data_dict[key] is None:
                    if isinstance(default_data[key], list):
                        data_dict[key] = []
                    elif isinstance(default_data[key], bool):
                        data_dict[key] = False
                    else:
                        data_dict[key] = ""
            
            # Creamos y retornamos el objeto ParkingData
            return ParkingData(**data_dict)
            
        except Exception as e:
            # Si algo falla, devolvemos un objeto vacío y propagamos el error
            raise ValueError(f"Error al parsear la respuesta del LLM: {str(e)}")





