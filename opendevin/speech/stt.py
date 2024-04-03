import os
import uuid
import asyncio
import websockets
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

from opendevin import config

DEEPGRAM_STT_MODEL = config.get_or_default("DEEPGRAM_STT_MODEL", "nova-2-general")
DEEPGRAM_STT_API_KEY = config.get_or_default("DEEPGRAM_STT_API_KEY", "")

class STT:
    # Declare deepgram, dg_connection as a class variable
    deepgram = None
    dg_connection = None

    async def __init__(self,
            model=DEEPGRAM_STT_MODEL,
            api_key=DEEPGRAM_STT_API_KEY
    ):
        self.model_name = model if model else DEEPGRAM_STT_MODEL
        self.api_key = api_key if api_key else DEEPGRAM_STT_API_KEY

        # Ensure dg_connection is initialized
        if STT.dg_connection is None:
            await STT.initialize_dg_connection(api_key)
    
    @classmethod
    async def initialize_dg_connection(cls, api_key=DEEPGRAM_STT_API_KEY):
        try:
            # Initialize the DeepgramClient
            cls.deepgram = DeepgramClient(api_key)
            
            # Initialize dg_connection as a class variable
            cls.dg_connection = await cls.deepgram.listen.asynclive.v("1")

            async def on_open(self, open, **kwargs):
                print(f"\n\n{open}\n\n")

            async def on_message(self, result, **kwargs):
                sentence = result.channel.alternatives[0].transcript
                if len(sentence) == 0:
                    return
                print(f"speaker: {sentence}")

            async def on_metadata(self, metadata, **kwargs):
                print(f"\n\n{metadata}\n\n")

            async def on_speech_started(self, speech_started, **kwargs):
                print(f"\n\n{speech_started}\n\n")

            async def on_utterance_end(self, utterance_end, **kwargs):
                print(f"\n\n{utterance_end}\n\n")

            async def on_error(self, error, **kwargs):
                print(f"\n\n{error}\n\n")

            async def on_close(self, close, **kwargs):
                print(f"\n\n{close}\n\n")

            cls.dg_connection.on(LiveTranscriptionEvents.Open, on_open)
            cls.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            cls.dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            cls.dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
            cls.dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
            cls.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            cls.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

            # connect to websocket
            options: LiveOptions = LiveOptions(
                model=DEEPGRAM_STT_MODEL,
                language="en-US",
            )

            print("\n\nPress Ctrl+C to stop...\n")
            if await cls.dg_connection.start(options) is False:
                print("Failed to connect to Deepgram")
                return
        except Exception as e:
            print(f"Could not open socket: {e}")
            return
    
        
    @classmethod
    async def speak(cls, audio: bytes):
        # Ensure dg_connection exists
        if cls.dg_connection is not None:
            await cls.dg_connection.send(audio)
        else:
            print("dg_connection is not initialized.")
