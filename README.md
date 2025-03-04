# Voice Assistant

```
$ uv sync
```

You need to set up the following environment variables:

```
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
CARTESIA_API_KEY=...
OPENAI_API_KEY=...
```

Then, run the assistant:

```
$ uv run python voice.py download-files
$ uv run python voice.py start
```

Finally, you can load the [hosted playground](https://agents-playground.livekit.io/) and connect it.