"""
Streamlit UI - AI Agent with Human Validation
==============================================
Clean, unified interface for Q&A and code generation
with satisfaction feedback loop.
"""

import streamlit as st
from agent import HumanInLoopAgent, AgentStage, save_code, execute_code

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="AI Agent",
    page_icon="🤖",
    layout="wide"
)

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #888;
        margin-bottom: 2rem;
    }
    .stButton button {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE
# =============================================================================

def init_session_state():
    """Initialize session state variables."""
    defaults = {
        'agent': None,
        'messages': [],
        'stage': 'chat',
        'pending_response': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    api_key = st.text_input(
        "Google API Key",
        type="password",
        help="Get from https://aistudio.google.com/app/apikey"
    )
    
    if st.button("🚀 Initialize Agent", use_container_width=True):
        if api_key:
            try:
                st.session_state.agent = HumanInLoopAgent(api_key=api_key)
                st.success("✅ Agent ready!")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Enter API key first!")
    
    if st.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.stage = 'chat'
        st.session_state.pending_response = None
        if st.session_state.agent:
            st.session_state.agent.reset()
        st.rerun()
    
    st.divider()
    
    # Status
    status = "🟢 Ready" if st.session_state.agent else "🟡 Not initialized"
    st.markdown(f"**Status:** {status}")
    st.markdown(f"**Stage:** {st.session_state.stage.title()}")
    
    st.divider()
    
    # Help
    st.markdown("""
    ### 📖 How it Works
    1. Ask a question or request code
    2. Review the response
    3. **Satisfied?**
       - ✅ Yes → Continue
       - ❌ No → Give feedback
    4. Agent improves based on feedback
    """)

# =============================================================================
# MAIN CONTENT
# =============================================================================

st.markdown('<h1 class="main-header">🤖 AI Agent</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Ask questions • Generate code • Human validation</p>', unsafe_allow_html=True)

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =============================================================================
# SATISFACTION CHECK
# =============================================================================

if st.session_state.stage == 'approval' and st.session_state.pending_response:
    st.markdown("---")
    st.markdown("### 🤔 Are you satisfied with this response?")
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("✅ YES", type="primary", use_container_width=True):
            if st.session_state.agent:
                result = st.session_state.agent.approve()
                st.session_state.messages.append({
                    "role": "user",
                    "content": "✅ *Satisfied*"
                })
            st.session_state.stage = 'chat'
            st.session_state.pending_response = None
            st.rerun()
    
    with col2:
        if st.button("❌ NO", type="secondary", use_container_width=True):
            st.session_state.stage = 'feedback'
            st.rerun()
    
    # Code actions (if code was generated)
    if st.session_state.pending_response and st.session_state.pending_response.has_code:
        with col3:
            if st.button("▶️ Run Code", use_container_width=True):
                if st.session_state.agent and st.session_state.agent.pending_code:
                    output = execute_code(st.session_state.agent.pending_code)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"**Execution Result:**\n```\n{output}\n```"
                    })
                    st.rerun()
        
        with col4:
            save_path = st.text_input("Save path", placeholder="output.py", label_visibility="collapsed")
            if st.button("💾 Save", use_container_width=True) and save_path:
                if st.session_state.agent and st.session_state.agent.pending_code:
                    result = save_code(st.session_state.agent.pending_code, save_path)
                    st.success(result)

# =============================================================================
# FEEDBACK INPUT
# =============================================================================

if st.session_state.stage == 'feedback':
    st.markdown("---")
    st.markdown("### 💬 What should be improved?")
    
    feedback = st.text_area(
        "Your feedback",
        placeholder="Explain what was wrong or what you expected...",
        key="feedback_input"
    )
    
    if st.button("📤 Submit Feedback", type="primary"):
        if feedback and st.session_state.agent:
            st.session_state.messages.append({
                "role": "user",
                "content": f"❌ *Not satisfied:* {feedback}"
            })
            
            with st.spinner("🔄 Improving response..."):
                response = st.session_state.agent.reject(feedback)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**📝 Improved Response:**\n\n{response.content}"
            })
            st.session_state.pending_response = response
            st.session_state.stage = 'approval'
            st.rerun()
        else:
            st.warning("Please provide feedback!")

# =============================================================================
# CHAT INPUT
# =============================================================================

if st.session_state.stage == 'chat':
    if prompt := st.chat_input("Ask me anything..."):
        if not st.session_state.agent:
            st.error("Please initialize the agent first!")
        else:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = st.session_state.agent.ask(prompt)
                    st.markdown(response.content)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.content
            })
            st.session_state.pending_response = response
            st.session_state.stage = 'approval'
            st.rerun()

# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.markdown(
    '<p style="text-align:center;color:#666;font-size:0.8rem">'
    '🤖 AI Agent with Human-in-the-Loop Validation | LangChain + Gemini'
    '</p>',
    unsafe_allow_html=True
)
