from SupervisorAgent import SupervisorAgent
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    agent = SupervisorAgent()
    agent.run()