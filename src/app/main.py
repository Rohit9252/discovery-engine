import sys
import os
# Ensure the root 'discovery-engine' directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Discovery Engine", page_icon="🔍", layout="wide")

def load_css():
    """Injects a clean, light Google Material aesthetic into Streamlit and fixes text contrast."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    /* Clean Light Background */
    .stApp, .stApp > header {
        background-color: #F8F9FA !important;
        color: #202124 !important;
    }
    
    /* Standard Text for Headers */
    h1, h2, h3, h4, h5, h6, p, span, div {
        color: #202124;
    }
    
    /* Chart Background Fix */
    [data-testid="stVegaLiteChart"] canvas {
        background-color: #FFFFFF !important;
        border-radius: 12px;
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3);
    }
    
    /* Clean Chat Bubbles */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E8EAED !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.1) !important;
        margin-bottom: 20px !important;
        padding: 1.5rem !important;
    }
    
    /* Force chat text to be dark (fixes white-on-white bug) */
    [data-testid="stChatMessage"] * {
        color: #202124 !important;
    }
    
    /* User Chat Bubble differentiation */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: #E8F0FE !important;
        border-color: #D2E3FC !important;
    }
    
    /* Floating Chat Input Container */
    [data-testid="stChatInput"] {
        border-radius: 24px !important;
        border: 1px solid #DADCE0 !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 1px 3px rgba(60,64,67,0.15) !important;
    }
    
    /* Force Chat Input text to be dark */
    [data-testid="stChatInput"] textarea, [data-testid="stChatInput"] p {
        color: #202124 !important;
    }
    
    /* Suggestion Buttons */
    .stButton>button {
        border-radius: 9999px !important;
        border: 1px solid #DADCE0 !important;
        background-color: #FFFFFF !important;
        color: #1A73E8 !important;
        padding: 6px 16px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #F8F9FA !important;
        box-shadow: 0 1px 2px rgba(60,64,67,0.3) !important;
        border-color: #D2E3FC !important;
    }
    
    /* Change generic "RAG Agent" title */
    .st-emotion-cache-10trblm {
        color: #1A73E8 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def load_mock_data():
    """Load sample metadata for UI rendering."""
    data = {
        "Failure Stage": ["Discovery", "Execution", "Post-Execution", "Discovery", "Execution", "Execution", "Discovery"],
        "Theme": ["Search", "Face Tagging", "Backup", "UI Navigation", "Editing", "Face Tagging", "Search"]
    }
    return pd.DataFrame(data)

def render_dashboard():
    """Render the top half of the dashboard containing the analytics charts."""
    st.title("🔍 Google Photos Discovery Engine")
    st.markdown("*Analyze pain points and failure stages from user reviews across Play Store, App Store, Reddit, and Forums.*")
    
    df = load_mock_data()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Failure Stages")
        stage_counts = df['Failure Stage'].value_counts().reset_index()
        stage_counts.columns = ['Failure Stage', 'Count']
        chart1 = alt.Chart(stage_counts).mark_bar().encode(
            x='Failure Stage',
            y='Count',
            color=alt.Color('Failure Stage', scale=alt.Scale(scheme='set2'))
        ).properties(height=300)
        st.altair_chart(chart1, use_container_width=True)
        
    with col2:
        st.subheader("Top Pain Point Themes")
        theme_counts = df['Theme'].value_counts().reset_index()
        theme_counts.columns = ['Theme', 'Count']
        chart2 = alt.Chart(theme_counts).mark_bar().encode(
            x='Count',
            y=alt.Y('Theme', sort='-x'),
            color=alt.value('#a855f7')
        ).properties(height=300)
        st.altair_chart(chart2, use_container_width=True)

@st.cache_resource
def get_cached_collection():
    from src.process.vector_db import get_chroma_client, get_or_create_collection
    client = get_chroma_client()
    return get_or_create_collection(client)

def query_rag(prompt: str):
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from src.process.extract import get_llm
        
        col = get_cached_collection()
        
        results = col.query(query_texts=[prompt], n_results=5)
        
        context_docs = results["documents"][0] if results and "documents" in results and results["documents"] else []
        
        if not context_docs:
            return "No relevant user reviews found in the database. Have you run the scraping pipeline yet?"
            
        llm = get_llm()
        system_prompt = f"""
        You are a Product Management AI analyzing user feedback for Google Photos.
        Use ONLY the following user review excerpts to answer the question.
        If the answer is not in the context, say "I don't have enough data to answer that."
        
        Context:
        {"\n---\n".join(context_docs)}
        
        Question: {prompt}
        """
        
        try:
            response = llm.invoke(system_prompt)
            return response.content
        except Exception as api_err:
            return f"**API Error:** `{api_err}`"
            
    except Exception as e:
        return f"Error connecting to the intelligence engine: {e}"

def render_chat():
    """Render the AI Discovery Engine chat interface."""
    st.subheader("✨ AI Discovery Engine")
    st.markdown("*Ask questions across qualitative transcripts, telemetry logs, and UX interview clusters.*")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if len(st.session_state.messages) == 0:
        st.markdown("**Suggested Questions (from Assignment Brief):**")
        questions = [
            "What kinds of old photos do users struggle to retrieve?",
            "What information do people actually remember about a photo?",
            "What information have they forgotten?",
            "How do users formulate searches when their memory is incomplete?",
            "Is the user unable to express what they remember?",
            "Does Google Photos fail to understand the clues they provide?",
            "Are potentially relevant results difficult to evaluate?",
            "Does the user struggle to refine an unsuccessful search?"
        ]
        
        selected_question = None
        for q in questions:
            if st.button(q, key=q):
                selected_question = q
                
        if selected_question:
            st.session_state.messages.append({"role": "user", "content": selected_question})
            with st.spinner("Searching millions of vectors..."):
                response = query_rag(selected_question)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question (e.g. 'What are users saying about face tagging?')"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.spinner("Searching millions of vectors..."):
            response = query_rag(prompt)
        
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    load_css()
    render_dashboard()
    st.divider()
    render_chat()
