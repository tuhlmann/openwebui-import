# openwebui-import

This repository contains helper scripts for importing exported chat history from different providers into Open WebUI.

The long-term goal is a shared import toolkit that normalizes conversations, attachments, and provider-specific metadata into a format that Open WebUI can ingest reliably.

## Status

The currently implemented workflow is for Gemini.

It covers:

- extracting Gemini conversations
- preserving uploaded assets
- handling generated images
- preparing intermediate and final JSON files for Open WebUI import
- uploading referenced files into Open WebUI

Imports from ChatGPT and Claude are planned, but are not implemented yet.

The Gemini-specific workflow is documented in [GEMINI_IMPORT.md](/Users/tuhlmann/entw/aktuell/openwebui-import/GEMINI_IMPORT.md).

## Disclaimer

These scripts are provided as is.

They were used to transfer my own conversations and worked for that purpose in my setup, but no guarantees are given.

Use them at your own risk. I do not accept liability for data loss, broken imports, or damage to your Open WebUI data if something goes wrong.

## Repository Layout

- `gemini/`: scripts and intermediate artifacts for the Gemini import pipeline
- `doc/tasks/`: planning notes and task documents for follow-up work

## Python Environment

This project uses `uv` to create the local Python virtual environment.

Create the environment:

```bash
uv venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install the dependency currently used by the upload and cleanup scripts:

```bash
uv pip install requests
```
