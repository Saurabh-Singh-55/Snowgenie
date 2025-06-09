from langchain_google_vertexai import ChatVertexAI

# --- Configuration ---
# You can change the model name to any compatible Gemini model.
MODEL_NAME = "gemini-1.0-pro"
# Your GCP Project ID is needed for some LangChain functionalities.
PROJECT_ID = "it-cloud-gcp-san-singh-gemini"

def query_gemini_with_langchain(model_name: str, project_id: str, prompt: str):
    """
    Uses LangChain with Vertex AI to query a Gemini model.
    Authentication is handled automatically by the library via the
    GOOGLE_APPLICATION_CREDENTIALS environment variable.
    """
    print("▶️  Initializing LangChain with Vertex AI...")
    
    # No api_key parameter is needed. Authentication is automatic!
    llm = ChatVertexAI(
        model_name=model_name,
        temperature=0
    )

    print(f"▶️  Sending prompt: '{prompt}'")
    # Use the .invoke() method to send the prompt to the model
    response = llm.invoke(prompt)

    print("✅ Received response from Gemini via LangChain.")
    print("-" * 40)
    return response.content


if __name__ == "__main__":
    my_prompt = "Explain the difference between Google AI Studio and Vertex AI in one paragraph."
    
    try:
        model_response = query_gemini_with_langchain(MODEL_NAME, PROJECT_ID, my_prompt)
        print("\nGemini's Response:")
        print(model_response)
    except Exception as e:
        print(f"❌ An error occurred: {e}")