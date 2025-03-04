import logging

from dotenv import load_dotenv
from livekit.agents import JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.job import AutoSubscribe
from livekit.agents.llm import (
    ChatContext,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import cartesia, openai, silero

load_dotenv()

logger = logging.getLogger("voice-assistant")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    llm = openai.LLM(model="gpt-4o-mini")

    chat_context = ChatContext().append(
        role="system",
        text=(
            "You are a funny, witty assistant."
            "Respond with short and concise answers. Avoid using unpronouncable punctuation or emojis."
        ),
    )

    logger.info(f"Connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"Starting voice assistant for participant {participant.identity}")

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT(),
        llm=llm,
        tts=cartesia.TTS(
            model="sonic",
            voice="794f9389-aac1-45b6-b726-9d9369183238",
        ),
        chat_ctx=chat_context,
    )

    agent.start(ctx.room, participant)

    await agent.say(
        "Hey there! How can I help you today?",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    print("Starting voice agent...")
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
