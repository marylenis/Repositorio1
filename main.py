from src.paking_agent.agent import ParkingAgent
from src.api.app import app
import uvicorn
def main():
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
