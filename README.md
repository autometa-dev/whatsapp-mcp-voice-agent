# Voice Assistant

A simple voice assistant using LiveKit, Cartesia, OpenAI, Silero, and a Multi-Content Processor (MCP) for WhatsApp integration.

## Prerequisites

- Python >=3.13
- `uv` (Python packager and virtual environment manager)

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd voice-assistant
    ```

2.  **Create and activate a virtual environment (using uv):**
    ```bash
    uv venv
    source .venv/bin/activate  # On Linux/macOS
    # .\.venv\Scripts\activate    # On Windows
    ```

3.  **Install dependencies:**
    ```bash
    uv sync
    ```

4.  **Set up Environment Variables:**

    Create a file named `.env` in the root of the project and add the following environment variables with your actual values.
    You can copy the example below:

    ```env
    LIVEKIT_URL=
    LIVEKIT_API_KEY=
    LIVEKIT_API_SECRET=
    CARTESIA_API_KEY=
    OPENAI_API_KEY=
    ```

    -   `LIVEKIT_URL`: Your LiveKit server URL.
    -   `LIVEKIT_API_KEY`: Your LiveKit API key.
    -   `LIVEKIT_API_SECRET`: Your LiveKit API secret.
    -   `CARTESIA_API_KEY`: Your Cartesia API key for Text-to-Speech.
    -   `OPENAI_API_KEY`: Your OpenAI API key for Speech-to-Text and LLM operations.

5.  **Configure WhatsApp MCP (Multi-Content Processor):**

    This project uses an MCP to interact with WhatsApp. You need to have your WhatsApp MCP server running and configured.

    Update the `mcp_config.json` file in the root of this project with the correct paths for your MCP setup:

    ```json
    {
      "mcpServers": {
        "whatsapp": {
          "command": "{{PATH_TO_UV}}",
          "args": [
            "--directory",
            "{{PATH_TO_SRC}}/whatsapp-mcp/whatsapp-mcp-server",
            "run",
            "main.py"
          ]
        }
      }
    }
    ```

    -   Replace `{{PATH_TO_UV}}` with the absolute path to your `uv` executable. You can find this by running `which uv` (on Linux/macOS) or `where uv` (on Windows) in your terminal.
    -   Replace `{{PATH_TO_SRC}}` with the absolute path to the directory containing your `whatsapp-mcp` project. For example, if your `whatsapp-mcp` project is in `/Users/me/dev/whatsapp-mcp`, then this value should be `/Users/me/dev`. The final path in the config will be `/Users/me/dev/whatsapp-mcp/whatsapp-mcp-server`.

## Running the Assistant

1.  **(Optional) Download necessary model files (e.g., for Silero VAD):**
    The `voice.py` script might have a command or automatically download necessary models on first run. The example below shows a hypothetical command if your `voice.py` supported it.
    ```bash
    # If your voice.py has a download command, e.g.:
    # uv run python voice.py download-files
    ```
    Currently, the `voice.py` script uses `livekit.agents.cli.run_app`, which typically handles its own setup for plugins like Silero.

2.  **Start the voice assistant:**
    ```bash
    uv run voice-assistant-cli
    ```
    This uses the `voice-assistant-cli` script defined in `pyproject.toml`.

## Connecting to the Playground

Once the assistant is running, you can load the [LiveKit Agents Playground](https://agents-playground.livekit.io/) in your browser and connect to your local agent.

---

*Note: This README assumes you have `uv` installed and configured in your system PATH.*