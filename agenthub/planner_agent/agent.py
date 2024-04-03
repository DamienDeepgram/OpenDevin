from typing import List
from .prompt import get_prompt, parse_response

from opendevin.agent import Agent
from opendevin.action import AgentFinishAction
from opendevin.llm.llm import LLM
from opendevin.speech.stt import STT
from opendevin.speech.tts import TTS
from opendevin.state import State
from opendevin.action import Action

class PlannerAgent(Agent):
    def __init__(self, llm: LLM, stt: STT, tts: TTS):
        super().__init__(llm, stt, tts)

    def step(self, state: State) -> Action:
        if state.plan.task.state in ['completed', 'verified', 'abandoned']:
            return AgentFinishAction()
        prompt = get_prompt(state.plan, state.history)
        messages = [{"content": prompt, "role": "user"}]
        resp = self.llm.completion(messages=messages)
        action_resp = resp['choices'][0]['message']['content']
        action = parse_response(action_resp)
        return action

    def search_memory(self, query: str) -> List[str]:
        return []

