
from langchain_community.chat_models import ChatOpenAI
from src.paking_agent.prompt import parking_agent_prompt
from dotenv import load_dotenv

load_dotenv()


class ParkingAgent:
    """ Class to handle the parking agent """
    def __init__(self):
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0)
        self.messages = [{"role": "system", "content": parking_agent_prompt}]
        self.first_message = True

    def get_response(self, user_input):

        self.messages.append({"role": "user", "content": user_input})
        response = self.llm.invoke(self.messages).content
        self.messages.append({"role": "assistant", "content": response})
        return response
