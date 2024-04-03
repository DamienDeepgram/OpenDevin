import os

from deepgram import (
    DeepgramClient,
    ClientOptionsFromEnv,
    SpeakOptions,
)

from opendevin import config

DEEPGRAM_TTS_MODEL = config.get_or_default("DEEPGRAM_TTS_MODEL", "aura-asteria-en")
DEEPGRAM_TTS_API_KEY = config.get_or_default("DEEPGRAM_STT_API_KEY", "")

class TTS:
    # Declare deepgram as a class variable
    deepgram = None
    async def __init__(self,
            model=DEEPGRAM_TTS_MODEL,
            api_key=DEEPGRAM_TTS_API_KEY
    ):
        self.model_name = model if model else DEEPGRAM_TTS_MODEL
        self.api_key = api_key if api_key else DEEPGRAM_TTS_API_KEY

        # Ensure deepgram is initialized
        if TTS.deepgram is None:
            await TTS.initialize_deepgram(api_key)
    
    @classmethod
    async def initialize_deepgram(cls, api_key=DEEPGRAM_TTS_API_KEY):
        try:
            # Initialize the DeepgramClient
            cls.deepgram = DeepgramClient(api_key=DEEPGRAM_TTS_API_KEY)
        except Exception as e:
            print(f"Could not open socket: {e}")
            return

    @classmethod
    async def speak(text: str) -> bytes:
        try:
            filename = "test.mp3"
            print('here: ', DEEPGRAM_TTS_API_KEY)

            options = SpeakOptions(
                model=DEEPGRAM_TTS_MODEL,
            )

            response = cls.deepgram.speak.v("1").save(filename, text, options)

            # print(response.to_json(indent=4))

            return response

        except Exception as e:
            print(f"Exception: {e}")
    