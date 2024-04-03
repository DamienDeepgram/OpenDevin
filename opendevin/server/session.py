import asyncio
import os
from typing import Optional

from fastapi import WebSocketDisconnect

from opendevin import config
from opendevin.action import (
    Action,
    NullAction,
)
from opendevin.observation import NullObservation
from opendevin.agent import Agent
from opendevin.controller import AgentController
from opendevin.llm.llm import LLM
from opendevin.speech.stt import STT
from opendevin.speech.tts import TTS
from opendevin.observation import Observation, UserMessageObservation

DEEPGRAM_API_KEY = config.get_or_none("DEEPGRAM_API_KEY")
DEEPGRAM_STT_MODEL = config.get_or_none("DEEPGRAM_STT_MODEL")
DEEPGRAM_TTS_MODEL = config.get_or_none("DEEPGRAM_TTS_MODEL")
DEFAULT_API_KEY = config.get_or_none("LLM_API_KEY")
DEFAULT_BASE_URL = config.get_or_none("LLM_BASE_URL")
DEFAULT_WORKSPACE_DIR = config.get_or_default("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
LLM_MODEL = config.get_or_default("LLM_MODEL", "gpt-4-0125-preview")
CONTAINER_IMAGE = config.get_or_default("SANDBOX_CONTAINER_IMAGE", "ghcr.io/opendevin/sandbox")

class Session:
    """Represents a session with an agent.

    Attributes:
        websocket: The WebSocket connection associated with the session.
        controller: The AgentController instance for controlling the agent.
        agent: The Agent instance representing the agent.
        agent_task: The task representing the agent's execution.
    """
    def __init__(self, websocket):
        """Initializes a new instance of the Session class.

        Args:
            websocket: The WebSocket connection associated with the session.
        """
        self.websocket = websocket
        self.controller: Optional[AgentController] = None
        self.agent: Optional[Agent] = None
        self.agent_task = None

    async def send_error(self, message):
        """Sends an error message to the client.

        Args:
            message: The error message to send.
        """
        await self.send({"error": True, "message": message})

    async def send_message(self, message):
        """Sends a message to the client.

        Args:
            message: The message to send.
        """
        await self.send({"message": message})

    async def send(self, data):
        """Sends data to the client.

        Args:
            data: The data to send.
        """
        if self.websocket is None:
            return
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            print("Error sending data to client", e)

    async def start_listening(self):
        """Starts listening for messages from the client."""
        try:
            while True:
                try:
                    data = await self.websocket.receive_json()
                except ValueError:
                    await self.send_error("Invalid JSON")
                    continue

                action = data.get("action", None)
                if action is None:
                    await self.send_error("Invalid event")
                    continue
                if action == "initialize":
                    await self.create_controller(data)
                elif action == "start":
                    await self.start_task(data)
                elif action == "speak":
                    await self.speak(data)
                elif action == "listen":
                    await self.listen(data)
                else:
                    if self.controller is None:
                        await self.send_error("No agent started. Please wait a second...")
                    elif action == "chat":
                        self.controller.add_history(NullAction(), UserMessageObservation(data["message"]))
                    else:
                        await self.send_error("I didn't recognize this action:" + action)

        except WebSocketDisconnect as e:
            self.websocket = None
            if self.agent_task:
                self.agent_task.cancel()
            print("Client websocket disconnected", e)

    async def create_controller(self, start_event=None):
        """Creates an AgentController instance.

        Args:
            start_event: The start event data (optional).
        """
        directory = DEFAULT_WORKSPACE_DIR
        if start_event and "directory" in start_event["args"]:
            directory = start_event["args"]["directory"]
        agent_cls = "MonologueAgent"
        if start_event and "agent_cls" in start_event["args"]:
            agent_cls = start_event["args"]["agent_cls"]
        model = LLM_MODEL
        if start_event and "model" in start_event["args"]:
            model = start_event["args"]["model"]
        api_key = DEFAULT_API_KEY
        if start_event and "api_key" in start_event["args"]:
            api_key = start_event["args"]["api_key"]
        deepgram_tts_model = DEEPGRAM_TTS_MODEL
        if start_event and "deepgram_tts_model" in start_event["args"]:
            deepgram_tts_model = start_event["args"]["deepgram_tts_model"]
        deepgram_stt_model = DEEPGRAM_STT_MODEL
        if start_event and "deepgram_stt_model" in start_event["args"]:
            deepgram_stt_model = start_event["args"]["deepgram_stt_model"]
        deepgram_api_key = DEEPGRAM_API_KEY
        if start_event and "deepgram_api_key" in start_event["args"]:
            deepgram_api_key = start_event["args"]["deepgram_api_key"]
        api_base = DEFAULT_BASE_URL
        if start_event and "api_base" in start_event["args"]:
            api_base = start_event["args"]["api_base"]
        container_image = CONTAINER_IMAGE
        if start_event and "container_image" in start_event["args"]:
            container_image = start_event["args"]["container_image"]
        max_iterations = 100
        if start_event and "max_iterations" in start_event["args"]:
            max_iterations = start_event["args"]["max_iterations"]
        if not os.path.exists(directory):
            print(f"Workspace directory {directory} does not exist. Creating it...")
            os.makedirs(directory)
        directory = os.path.relpath(directory, os.getcwd())
        llm = LLM(model=model, api_key=api_key, base_url=api_base)
        stt = STT(model=deepgram_stt_model, api_key=deepgram_api_key)
        tts = STT(model=deepgram_tts_model, api_key=deepgram_api_key)
        AgentCls = Agent.get_cls(agent_cls)
        self.agent = AgentCls(llm, stt, tts)
        try:
            self.controller = AgentController(self.agent, workdir=directory, max_iterations=max_iterations, container_image=container_image, callbacks=[self.on_agent_event])
        except Exception:
            print("Error creating controller.")
            await self.send_error("Error creating controller. Please check Docker is running using `docker ps`.")
            return
        await self.send({"action": "initialize", "message": "Control loop started."})

    async def start_task(self, start_event):
        """Starts a task for the agent.

        Args:
            start_event: The start event data.
        """
        if "task" not in start_event["args"]:
            await self.send_error("No task specified")
            return
        await self.send_message("Starting new task...")
        task = start_event["args"]["task"]
        if self.controller is None:
            await self.send_error("No agent started. Please wait a second...")
            return
        try:
            self.agent_task = await asyncio.create_task(self.controller.start_loop(task), name="agent loop")
        except Exception:
            await self.send_error("Error during task loop.")

    def on_agent_event(self, event: Observation | Action):
        """Callback function for agent events.

        Args:
            event: The agent event (Observation or Action).
        """
        if isinstance(event, NullAction):
            return
        if isinstance(event, NullObservation):
            return
        event_dict = event.to_dict()
        asyncio.create_task(self.send(event_dict), name="send event in callback")

    def speak(self, event: Observation | Action):
        """Speak text

        Args:
            text: The text to speak
        """
        event_dict = event.to_dict()
        self.agent.speak(event_dict)
        # asyncio.create_task(self.send(event_dict), name="send event in callback")

    def listen(self, event: Observation | Action):
        """Transcribe speech

        Args:
            audio: Audio to transcribe
        """
        event_dict = event.to_dict()
        self.agent.listen(event_dict)
        # asyncio.create_task(self.send(event_dict), name="send event in callback")