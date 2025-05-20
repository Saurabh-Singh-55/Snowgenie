# SnowGenie: Natural Language to SQL for Snowflake

🚀 **SnowGenie** is a local-first app that lets anyone—technical or not—query a Snowflake database using plain English. No SQL skills or schema knowledge required. Everything runs on your machine: LLM, tool server, and database connection. No cloud dependencies.

---

## ✨ Features

- **Ask questions in natural language** about your Snowflake data.
- **Automatic schema analysis**—no need to know table or column names.
- **LLM-powered SQL generation** and execution.
- **Clear, formatted answers**—no manual querying.
- **Runs 100% locally**: Ollama for LLM, FastMCP for tool orchestration, direct Snowflake DB connection, and a Streamlit UI.

---

## 🧠 Example Use Case

> "Among VIP segment customers, what percentage of orders were cancelled before shipment?"

- The app figures out the schema, joins tables, interprets coded columns, generates the SQL, runs it, and returns:  
  **20%** ✅

---

## 📦 File Structure

```
.
├── App.py                # Streamlit frontend (main UI)
├── LLM_server.py         # FastAPI server for LLM and agent orchestration
├── Snow_MCP_server.py    # FastMCP server for Snowflake tool access
├── client.py             # CLI client for interactive chat
├── constants.py          # All configuration and environment variables
├── requirements.txt      # Python dependencies
├── .streamlit/           # Streamlit config
├── write_detector.py     # SQL write operation detector
├── README.md             # This file
└── ...
```

---

## 🤖 Setting Up Ollama

SnowGenie requires Ollama to be installed and running as it powers the local LLM functionality. Follow these steps to set up Ollama before proceeding with the main application setup:

### Installing Ollama

#### For macOS:
```bash
# Using Homebrew
brew install ollama

# OR using the official install script
curl -sS https://ollama.ai/install.sh | bash
```

#### For Windows:
1. Download the Ollama installer from the [official website](https://ollama.ai)
2. Run the downloaded installer and follow the installation wizard

#### For Linux:
```bash
curl -sS https://ollama.ai/install.sh | bash
```

### Starting Ollama and Pulling the Required Model

1. Start the Ollama service:
```bash
ollama serve
```

2. Pull the required model (we use qwen3:32b by default, but you can configure other models in your `.env`):
```bash
ollama pull qwen3:32b
```

3. Verify Ollama is working correctly:
```bash
ollama list
```

You should see the downloaded model in the list. Note that models require sufficient RAM to run properly:
- 7B models: at least 8GB RAM
- 13B models: at least 16GB RAM
- 32B+ models: at least 32GB RAM

For more information and advanced options, visit the [Ollama documentation](https://ollama.ai/docs).

---

## ⚡ Quickstart

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/SnowGenie.git
cd SnowGenie
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Copy `.env.example` to `.env` and fill in your Snowflake credentials and any overrides for ports, model names, etc.

```env
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account
# ... (see constants.py for all options)
```

### 5. Start the servers (in separate terminals)

**a. Start the Snowflake MCP server:**
```bash
python Snow_MCP_server.py
```

**b. Start the LLM server:**
```bash
python LLM_server.py
```

**c. (Optional) Start the CLI client:**
```bash
python client.py
```

**d. Start the Streamlit UI:**
```bash
streamlit run App.py
```

---

## 🖥️ How it Works

- **Streamlit UI (`App.py`)**: User-friendly chat interface.
- **LLM Server (`LLM_server.py`)**: Handles natural language, generates SQL, orchestrates tool calls.
- **MCP Server (`Snow_MCP_server.py`)**: Exposes database tools (list tables, describe schema, run queries) to the agent.
- **Ollama**: Local LLM backend (make sure Ollama is running and the model is pulled).
- **Snowflake**: Connects directly to your Snowflake instance.

---

## 🔒 Security

- All credentials are local and never sent to the cloud.
- Only read-only queries are allowed by default (see `write_detector.py`).

---

## 🛠️ Troubleshooting

- **Ollama not running?**  
  Start it with `ollama serve` and pull your desired model (e.g., `ollama pull qwen3:32b`).
- **Snowflake connection issues?**  
  Double-check your `.env` settings.
- **Port conflicts?**  
  Change the relevant port in your `.env` or `constants.py`.

---

## 🤝 Contributing

PRs and issues welcome! Please open an issue for bugs, feature requests, or questions.

---

## 📄 License

MIT License


