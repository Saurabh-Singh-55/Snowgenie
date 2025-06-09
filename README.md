# SnowGenie: Natural Language to SQL for Snowflake

�� **SnowGenie** is a modern AI-powered app that lets anyone—technical or not—query a Snowflake database using plain English. Powered by Google's Gemini AI, it requires no SQL skills or schema knowledge. Direct cloud AI integration with local database connection ensures both power and security.

---

## ✨ Features

- **Ask questions in natural language** about your Snowflake data
- **Automatic schema analysis**—no need to know table or column names
- **Gemini AI-powered SQL generation** and execution
- **Clear, formatted answers** with reasoning process displayed
- **Google Gemini integration**: Latest AI models (Gemini 2.0 Flash, 1.5 Pro, etc.)
- **Secure**: Credentials stay local, only queries sent to Gemini API

---

## 🧠 Example Use Case

> "Among VIP segment customers, what percentage of orders were cancelled before shipment?"

- SnowGenie analyzes your schema, joins tables, interprets coded columns, generates SQL, runs it, and returns:  
  **20% of VIP customer orders were cancelled before shipment** ✅

---

## 💰 Cost Optimization

SnowGenie now includes smart schema caching to reduce Snowflake compute costs and improve response times:

- **Cached Schema Analysis**: Database structure is cached locally, eliminating repeated schema queries
- **Reduced Warehouse Usage**: Most agent operations use the cache instead of querying Snowflake
- **Selective Live Queries**: Only actual data queries use the warehouse, not schema exploration
- **One-Click Cache Refresh**: Update schema cache via UI when database structure changes
- **Cost Savings**: Up to 70% reduction in warehouse compute time for schema-heavy operations

---

## 📦 File Structure

```
.
├── App.py                # Streamlit frontend (main UI)
├── LLM_server.py         # FastAPI server for Gemini AI and agent orchestration
├── Snow_MCP_server.py    # FastMCP server for Snowflake tool access
├── SnowMCP_initialize.py # Schema cache builder for cost optimization
├── client.py             # CLI client for interactive chat
├── constants.py          # All configuration and environment variables
├── requirements.txt      # Python dependencies including langchain-google-genai
├── .streamlit/           # Streamlit config
├── write_detector.py     # SQL write operation detector
├── README.md             # This file
└── ...
```

---

## 🤖 Setting Up Google Gemini AI

SnowGenie now uses Google's Gemini AI models for superior natural language understanding and SQL generation. You'll need a Google AI API key to get started.

### Getting Your Gemini API Key

1. **Visit Google AI Studio**: Go to [Google AI Studio](https://ai.google.dev/)
2. **Sign in** with your Google account
3. **Create API Key**: Click "Get API Key" and create a new key
4. **Copy the key**: You'll need this for configuration

### Available Gemini Models
- **gemini-2.0-flash** (Recommended) - Latest, fastest model
- **gemini-1.5-pro** - Most capable for complex reasoning
- **gemini-1.5-flash** - Fast and efficient
- **gemini-pro** - Balanced performance
- **gemini-2.5-pro-preview-06-05** - Latest preview model

### Configuration

Add your Gemini API key to the `constants.py` file:

```python
# Gemini AI Configuration
GEMINI_API_KEY = "your_gemini_api_key_here"
GEMINI_MODEL = "gemini-2.0-flash"  # or your preferred model
GEMINI_TEMPERATURE = "0.5"
GEMINI_MAX_TOKENS = "1000"
```

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

### 4. Configure your credentials

Edit the `constants.py` file to update your Snowflake and Gemini credentials:

```python
# Snowflake Configuration
SNOWFLAKE_USER = "your_username"
SNOWFLAKE_PASSWORD = "your_password"
SNOWFLAKE_ACCOUNT = "your_account"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"  # or your preferred role
SNOWFLAKE_DATABASE = "RETAIL_POC"  # your database name
SNOWFLAKE_SCHEMA = "SALES"  # your schema name

# Gemini AI Configuration
GEMINI_API_KEY = "your_gemini_api_key_here"
GEMINI_MODEL = "gemini-2.0-flash"
```

### 5. Initialize the schema cache

**Before starting the servers, build the schema cache:**
```bash
python SnowMCP_initialize.py
```

This creates a local cache of your database schema, reducing Snowflake compute costs.

### 6. Start the servers (in separate terminals)

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

- **Streamlit UI (`App.py`)**: Modern chat interface with real-time status indicators and schema cache management
- **LLM Server (`LLM_server.py`)**: Integrates with Google Gemini AI for natural language processing and SQL generation
- **MCP Server (`Snow_MCP_server.py`)**: Exposes database tools using cached schema for efficiency
- **Schema Cache (`SnowMCP_initialize.py`)**: Builds and maintains local cache of database structure
- **Google Gemini AI**: Cloud-based language model providing superior reasoning and code generation
- **Snowflake**: Direct connection to your Snowflake data warehouse for data queries only

### Architecture Flow:
1. User asks question in natural language
2. Gemini AI analyzes the question and available database tools
3. AI uses cached schema for database exploration (no Snowflake compute used)
4. AI generates optimized SQL queries using schema understanding
5. Only actual data queries use Snowflake compute resources
6. Results are formatted and presented to user with reasoning

---

## 🔒 Security & Privacy

- **Credentials Stay Local**: Snowflake credentials never leave your machine
- **API Communication**: Only natural language queries and responses sent to Gemini API
- **Read-Only by Default**: Only SELECT queries allowed (see `write_detector.py`)
- **Schema Privacy**: Database schema information is only used for query generation

---

## 🛠️ Troubleshooting

- **Gemini API Key Issues?**  
  Verify your API key is valid at [Google AI Studio](https://ai.google.dev/)
- **Snowflake connection issues?**  
  Double-check your credentials in `constants.py`
- **Port conflicts?**  
  Change the relevant port settings in `constants.py`
- **Model not available?**  
  Try switching to a different Gemini model in the UI

---

## 🚀 Recent Updates

### Version 2.1 - Cost Optimization
- **Added Schema Caching**: Dramatically reduced Snowflake compute costs
- **Cache Management UI**: One-click schema cache refresh in Streamlit
- **Optimized Tool Calls**: Most agent operations now use local cache
- **Improved Performance**: Faster response times for schema exploration
- **Cost Monitoring**: Better visibility into warehouse usage

### Version 2.0 - Gemini Integration
- **Replaced Ollama** with Google Gemini AI for superior performance
- **Added multiple model support** (Gemini 2.0 Flash, 1.5 Pro, etc.)
- **Improved UI** with model status indicators and real-time updates
- **Enhanced error handling** for better user experience
- **Simplified setup** - no local LLM installation required

---

## 🤝 Contributing

PRs and issues welcome! Please open an issue for bugs, feature requests, or questions.

---

## 📄 License

MIT License


