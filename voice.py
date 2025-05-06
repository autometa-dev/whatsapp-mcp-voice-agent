import logging
import asyncio
import os
from typing import AsyncIterable

from dotenv import load_dotenv
from livekit.agents import JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.job import AutoSubscribe
from livekit.agents.llm import LLM
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import cartesia, openai, silero
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

from whatsapp_agent import run_mcp_agent_query

load_dotenv()

logger = logging.getLogger("voice-assistant")

# Define a simple wrapper class that conforms to the expected LLM interface
# for the VoicePipelineAgent, but calls our WhatsApp agent logic instead.
class WhatsAppMCPAgentWrapper(LLM):
    def __init__(self, mcp_config_path: str = "mcp_config.json"):
        super().__init__(capabilities={'chat': True})
        self._mcp_config_path = mcp_config_path
        self._cleanup_llm = ChatOpenAI(model="gpt-4o-mini")

        # Initialize MCP Client and Agent here
        self._mcp_client = None
        self._mcp_agent = None
        try:
            if not os.path.exists(self._mcp_config_path):
                 raise FileNotFoundError(f"MCP configuration file not found at: {self._mcp_config_path}")

            self._mcp_client = MCPClient.from_config_file(self._mcp_config_path)
            base_llm = ChatOpenAI(model="gpt-4o-mini") # LLM for the agent itself
            self._mcp_agent = MCPAgent(llm=base_llm, client=self._mcp_client, max_steps=10)
            logger.info("MCP Client and Agent initialized successfully.")
        except FileNotFoundError as e:
            logger.error(f"Failed to initialize MCP: {e}")
            # Agent will fail later if _mcp_agent is None
        except Exception as e:
            logger.error(f"Unexpected error initializing MCP: {e}", exc_info=True)

    async def aclose(self):
        """Clean up MCP client sessions."""
        if self._mcp_client and self._mcp_client.sessions:
            logger.info("Attempting to close MCP client sessions from wrapper...")
            try:
                # Added timeout potentially prevent hanging
                await asyncio.wait_for(self._mcp_client.close_all_sessions(), timeout=10.0)
                logger.info("MCP sessions closed successfully.")
            except asyncio.TimeoutError:
                logger.error("Timed out waiting for MCP sessions to close.")
            except Exception as e:
                # Log specifically if it's the cancel scope error
                if "Attempted to exit cancel scope" in str(e):
                     logger.warning(f"Known cancel scope issue during MCP session close: {e}")
                else:
                     logger.error(f"Error closing MCP sessions: {e}", exc_info=True)
        else:
            logger.info("No active MCP client or sessions found to close.")

        self._mcp_client = None # Mark as closed
        self._mcp_agent = None

    async def chat(self, history: list | None = None, **kwargs) -> AsyncIterable[str]: # Return AsyncIterable
        logger.debug(f"WhatsAppMCPAgentWrapper received history: {history}")
        logger.debug(f"WhatsAppMCPAgentWrapper received kwargs: {kwargs}")

        # Check if MCP agent initialized correctly
        if not self._mcp_agent:
            logger.error("MCP Agent was not initialized.")
            yield "Sorry, the backend agent is not available."
            return

        user_input = ""
        chat_ctx = kwargs.get('chat_ctx')
        if chat_ctx and chat_ctx.messages:
            last_message = chat_ctx.messages[-1]
            if last_message.role == "user" and isinstance(last_message.content, str):
                user_input = last_message.content

        if not user_input:
             if history and len(history) > 0 and history[-1].role == "user":
                 user_input = history[-1].text
             elif isinstance(kwargs.get('prompt'), str):
                 user_input = kwargs['prompt']
             elif isinstance(kwargs.get('message'), str):
                 user_input = kwargs['message']
             elif isinstance(kwargs.get('input'), str):
                 user_input = kwargs['input']
             elif isinstance(kwargs.get('text'), str):
                 user_input = kwargs['text']

        if not user_input:
            logger.warning("Could not extract user input in WhatsAppMCPAgentWrapper.chat")
            yield "Sorry, I could not understand the input."
            return

        logger.info(f"Sending to MCP Agent: {user_input}")
        raw_mcp_result = None
        try:
            logger.info("BEFORE awaiting run_mcp_agent_query")
            try:
                # Call the simplified query function with the stored agent
                raw_mcp_result = await run_mcp_agent_query(self._mcp_agent, user_input)
            except asyncio.CancelledError:
                logger.warning("LLM task cancelled while awaiting run_mcp_agent_query.")
                yield "Processing cancelled."
                return
            except Exception as inner_e: # Catch broader exceptions here
                logger.error(f"Exception during run_mcp_agent_query or its internal processing: {inner_e}", exc_info=True)
                # Check if it's the tool parsing error we saw
                if "Tool execution returned no content" in str(inner_e):
                     yield "Sorry, the tool failed to provide a result."
                else:
                     yield "Sorry, an error occurred while getting the agent response."
                return

            logger.info(f"AFTER awaiting run_mcp_agent_query. Result type: {type(raw_mcp_result)}, Value: {str(raw_mcp_result)[:100]}...")

            if not isinstance(raw_mcp_result, str):
                 logger.error(f"run_mcp_agent_query did not return a string, got: {type(raw_mcp_result)}")
                 yield "Sorry, an internal error occurred."
                 return

            logger.info(f"Received raw result from MCP Agent: {raw_mcp_result[:100]}...")

            # 2. Clean up the result using another LLM call
            cleanup_prompt = (
                f"Please rephrase the following text into a concise and natural-sounding summary "
                f"suitable for a voice assistant to speak. Omit technical details like IDs unless essential. "
                f"Focus on the core message content and sender information if available.\n\n"
                f"Original text:\n{raw_mcp_result}"
            )
            logger.info("Sending raw result to cleanup LLM")
            try:
                cleanup_response = await self._cleanup_llm.ainvoke(cleanup_prompt)
                final_response = cleanup_response.content
            except asyncio.CancelledError:
                logger.warning("LLM task cancelled while awaiting cleanup LLM.")
                yield "Processing cancelled during cleanup."
                return
            except Exception as cleanup_e:
                logger.error(f"Exception during cleanup LLM call: {cleanup_e}", exc_info=True)
                yield "Sorry, an error occurred while finalizing the response."
                return

            logger.info(f"Final cleaned response: {final_response}")
            # 3. Yield the final cleaned response
            yield final_response

        except FileNotFoundError as e:
             logger.error(f"MCP Config Error during init or call: {e}")
             yield "Sorry, there was a configuration problem."
        except Exception as e:
            # Catch broader exceptions outside the specific awaits
            logger.error(f"Outer error in chat wrapper: {e}", exc_info=True)
            yield "Sorry, a general error occurred."

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Instantiate our WhatsApp agent wrapper
    whatsapp_llm_wrapper = WhatsAppMCPAgentWrapper(mcp_config_path="mcp_config.json")

    # Define and register the cleanup callback
    async def _cleanup():
        await whatsapp_llm_wrapper.aclose()
    ctx.add_shutdown_callback(_cleanup)

    logger.info(f"Connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"Starting voice assistant for participant {participant.identity}")

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT(),
        llm=whatsapp_llm_wrapper,
        tts=cartesia.TTS(
            model="sonic-preview", # Reverted to original model
            # Add your Cartesia API Key if needed, or ensure it's in .env
            # api_key="YOUR_CARTESIA_API_KEY",
            voice="794f9389-aac1-45b6-b726-9d9369183238", # Use 'voice' instead of 'voice_id'
        ),
        # llm=whatsapp_llm_wrapper, # Pass our wrapper as the llm
        # Remove chat_ctx as the wrapper/MCP agent handles context/state
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
