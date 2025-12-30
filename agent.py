"""
AI Agent with Human-in-the-Loop Validation
============================================
A unified agent combining:
- Q&A with satisfaction feedback
- Code generation with approval workflow
- LangChain + Gemini (no rate limiting issues)

Author: AI Agent Builder
"""

import os
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()


# =============================================================================
# ENUMS & DATA CLASSES
# =============================================================================

class AgentStage(Enum):
    """Current stage of the agent workflow."""
    CHAT = "chat"
    APPROVAL = "approval"
    FEEDBACK = "feedback"


@dataclass
class AgentResponse:
    """Structured response from the agent."""
    content: str
    has_code: bool = False
    code_block: Optional[str] = None
    requires_approval: bool = False


# =============================================================================
# CORE AGENT CLASS
# =============================================================================

class HumanInLoopAgent:
    """
    AI Agent with human-in-the-loop validation.
    
    Features:
        - Answer questions with satisfaction feedback
        - Generate code with approval workflow
        - Revise responses based on user feedback
    
    Usage:
        agent = HumanInLoopAgent()
        response = agent.ask("Write a Python function")
        # User reviews response
        agent.approve()  # or agent.reject("Make it shorter")
    """
    
    SYSTEM_PROMPT = """You are an expert AI assistant specialized in coding and answering questions.

RULES:
1. Give clear, accurate, and helpful responses
2. When writing code, include comments and docstrings
3. If user provides feedback, improve your response accordingly
4. Be concise but thorough
5. For code requests, always wrap code in ```python blocks"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the agent.
        
        Args:
            api_key: Google API key. If None, reads from GOOGLE_API_KEY env var.
        
        Raises:
            ValueError: If no API key is provided or found.
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set GOOGLE_API_KEY in .env or pass to constructor."
            )
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=self.api_key,
            temperature=0.3
        )
        
        self.chat_history: list = []
        self.stage = AgentStage.CHAT
        self.last_question: Optional[str] = None
        self.last_response: Optional[str] = None
        self.pending_code: Optional[str] = None
    
    def ask(self, question: str) -> AgentResponse:
        """
        Ask the agent a question.
        
        Args:
            question: The user's question or request.
        
        Returns:
            AgentResponse with content and code detection.
        """
        messages = [SystemMessage(content=self.SYSTEM_PROMPT)]
        
        # Add recent chat history for context
        for msg in self.chat_history[-10:]:
            messages.append(msg)
        
        messages.append(HumanMessage(content=question))
        
        response = self.llm.invoke(messages)
        content = response.content
        
        # Store for potential revision
        self.last_question = question
        self.last_response = content
        
        # Detect if response contains code
        has_code = "```" in content
        code_block = self._extract_code(content) if has_code else None
        
        if code_block:
            self.pending_code = code_block
            self.stage = AgentStage.APPROVAL
        else:
            self.stage = AgentStage.APPROVAL  # Always ask for satisfaction
        
        return AgentResponse(
            content=content,
            has_code=has_code,
            code_block=code_block,
            requires_approval=True
        )
    
    def approve(self) -> str:
        """
        User approves the response.
        
        Returns:
            Confirmation message.
        """
        if self.last_question and self.last_response:
            self.chat_history.append(HumanMessage(content=self.last_question))
            self.chat_history.append(AIMessage(content=self.last_response))
        
        self.stage = AgentStage.CHAT
        approved_code = self.pending_code
        
        # Reset pending state
        self.pending_code = None
        self.last_question = None
        self.last_response = None
        
        if approved_code:
            return f"✅ Code approved!\n```python\n{approved_code}\n```"
        return "✅ Response approved!"
    
    def reject(self, feedback: str) -> AgentResponse:
        """
        User rejects and provides feedback for improvement.
        
        Args:
            feedback: What was wrong and what to improve.
        
        Returns:
            Improved AgentResponse.
        """
        if not self.last_question or not self.last_response:
            return AgentResponse(content="No previous response to revise.", requires_approval=False)
        
        revision_prompt = f"""
The user was NOT satisfied with your previous response.

ORIGINAL QUESTION: {self.last_question}

YOUR PREVIOUS RESPONSE: {self.last_response}

USER FEEDBACK: {feedback}

Please provide an IMPROVED response based on their feedback.
"""
        
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=revision_prompt)
        ]
        
        response = self.llm.invoke(messages)
        content = response.content
        
        # Update for next potential revision
        self.last_response = content
        
        has_code = "```" in content
        code_block = self._extract_code(content) if has_code else None
        
        if code_block:
            self.pending_code = code_block
        
        self.stage = AgentStage.APPROVAL
        
        return AgentResponse(
            content=content,
            has_code=has_code,
            code_block=code_block,
            requires_approval=True
        )
    
    def reset(self) -> None:
        """Reset conversation history and state."""
        self.chat_history = []
        self.stage = AgentStage.CHAT
        self.last_question = None
        self.last_response = None
        self.pending_code = None
    
    @staticmethod
    def _extract_code(text: str) -> Optional[str]:
        """Extract first code block from markdown text."""
        import re
        match = re.search(r'```(?:python)?\n(.*?)```', text, re.DOTALL)
        return match.group(1).strip() if match else None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def save_code(code: str, filepath: str) -> str:
    """
    Save code to a file.
    
    Args:
        code: The code content to save.
        filepath: Where to save the file.
    
    Returns:
        Success or error message.
    """
    try:
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        return f"✅ Saved to {filepath}"
    except Exception as e:
        return f"❌ Error: {e}"


def execute_code(code: str) -> str:
    """
    Execute Python code safely.
    
    Args:
        code: Python code to execute.
    
    Returns:
        Execution output or error.
    """
    import subprocess
    import sys
    
    temp_file = "_temp_exec.py"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = ""
        if result.stdout:
            output += f"📤 Output:\n{result.stdout}"
        if result.stderr:
            output += f"\n⚠️ Errors:\n{result.stderr}"
        
        return output or "✅ Executed (no output)"
        
    except subprocess.TimeoutExpired:
        return "❌ Timeout: Code took too long (30s limit)"
    except Exception as e:
        return f"❌ Error: {e}"
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Run the agent in CLI mode."""
    print("=" * 60)
    print("🤖 AI AGENT WITH HUMAN VALIDATION")
    print("=" * 60)
    print("Commands: quit, approve, reject <feedback>, save <path>, run")
    print("=" * 60)
    
    try:
        agent = HumanInLoopAgent()
        print("✅ Agent initialized!\n")
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    while True:
        try:
            user_input = input("👤 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("👋 Goodbye!")
                break
            
            elif user_input.lower() == 'approve':
                print(f"\n{agent.approve()}\n")
            
            elif user_input.lower().startswith('reject '):
                feedback = user_input[7:].strip()
                response = agent.reject(feedback)
                print(f"\n🤖 Improved Response:\n{response.content}")
                print("\n⚠️ Satisfied? ('approve' or 'reject <feedback>')\n")
            
            elif user_input.lower().startswith('save '):
                path = user_input[5:].strip()
                if agent.pending_code:
                    print(save_code(agent.pending_code, path))
                else:
                    print("❌ No code to save")
            
            elif user_input.lower() == 'run':
                if agent.pending_code:
                    print(execute_code(agent.pending_code))
                else:
                    print("❌ No code to run")
            
            else:
                # Regular question
                response = agent.ask(user_input)
                print(f"\n🤖 Agent:\n{response.content}")
                print("\n⚠️ Satisfied? ('approve' or 'reject <feedback>')")
                
                if response.has_code:
                    print("   Code detected! Use 'save <path>' or 'run' after approval.\n")
        
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break


if __name__ == "__main__":
    main()
