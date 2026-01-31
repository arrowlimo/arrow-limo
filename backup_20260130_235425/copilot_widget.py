"""
AI Copilot Chat Widget

Provides PyQt6 chat interface for AI Copilot with:
- Chat history display
- User input with Enter submission
- Quick action buttons
- Status indicators (Thinking, Executing, Ready)
- Function execution and result display

Usage:
    from copilot_widget import CopilotWidget
    
    widget = CopilotWidget()
    # Add to QMainWindow
    main_window.addWidget(widget)
"""

import sys
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QSplitter, QFrame, QScrollArea, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QSize
from PyQt6.QtGui import QFont, QIcon, QColor, QTextCursor, QTextFormat


class CopilotWorker(QThread):
    """Background worker for AI processing"""
    
    # Signals
    progress = pyqtSignal(str)  # Status updates
    response_ready = pyqtSignal(dict)  # {"text": str, "functions": list}
    error = pyqtSignal(str)  # Error messages
    
    def __init__(self, query: str, rag_engine, llm_engine, executor):
        super().__init__()
        self.query = query
        self.rag = rag_engine
        self.llm = llm_engine
        self.executor = executor
    
    def run(self):
        """Run AI processing in background"""
        try:
            # Step 1: Retrieve knowledge
            self.progress.emit("Searching knowledge base...")
            if self.rag:
                context_data = self.rag.search(self.query, top_k=3)
                # Format context for LLM
                context = self.rag.format_context(self.query, top_k=3)
            else:
                context = ""
            
            # Step 2: Generate response
            self.progress.emit("Generating response...")
            if self.llm:
                llm_response = self.llm.generate(self.query, context=context)
                if llm_response.error:
                    self.error.emit(f"LLM Error: {llm_response.error}")
                    return
                response_text = llm_response.text
                functions_called = llm_response.functions_called or []
            else:
                response_text = "AI not available"
                functions_called = []
            
            # Step 3: Execute functions if suggested
            function_results = []
            if functions_called and self.executor:
                for func_call in functions_called:
                    self.progress.emit(f"Executing {func_call}...")
                    calls = self.executor.parse_function_call(f"CALL_FUNCTION: {func_call}")
                    if calls:
                        result = self.executor.execute_function_call(calls[0])
                        function_results.append({
                            "function": calls[0]['function'],
                            "success": result.success,
                            "result": result.result
                        })
            
            # Emit response
            self.response_ready.emit({
                "text": response_text,
                "functions": function_results,
                "timestamp": datetime.now().isoformat()
            })
            
            self.progress.emit("Ready")
        
        except Exception as e:
            self.error.emit(f"Processing error: {str(e)}")


class CopilotWidget(QWidget):
    """AI Copilot chat widget"""
    
    def __init__(self, parent=None, rag_engine=None, llm_engine=None, executor=None):
        """
        Initialize copilot widget
        
        Args:
            parent: Parent widget
            rag_engine: Knowledge retriever (optional)
            llm_engine: LLM engine (optional)
            executor: Function executor (optional)
        """
        super().__init__(parent)
        self.rag = rag_engine
        self.llm = llm_engine
        self.executor = executor
        self.worker = None
        
        self._setup_ui()
        self._setup_quick_actions()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Title
        title = QLabel("AI Copilot")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Chat history
        chat_layout = QVBoxLayout()
        
        self.chat_display = QTextBrowser()
        self.chat_display.setMarkdown = False
        self.chat_display.setFont(QFont("Courier", 9))
        chat_layout.addWidget(self.chat_display)
        
        chat_frame = QFrame()
        chat_frame.setLayout(chat_layout)
        splitter.addWidget(chat_frame)
        
        # Right: Quick actions
        actions_layout = QVBoxLayout()
        actions_label = QLabel("Quick Actions")
        actions_font = QFont()
        actions_font.setPointSize(10)
        actions_label.setFont(actions_font)
        actions_layout.addWidget(actions_label)
        
        self.quick_list = QListWidget()
        self.quick_list.itemClicked.connect(self._on_quick_action)
        actions_layout.addWidget(self.quick_list)
        
        actions_frame = QFrame()
        actions_frame.setLayout(actions_layout)
        actions_frame.setMaximumWidth(150)
        splitter.addWidget(actions_frame)
        
        splitter.setSizes([400, 150])
        layout.addWidget(splitter)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask me anything about your business...")
        self.input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._on_send)
        self.send_button.setMaximumWidth(80)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        self.setLayout(layout)
    
    def _setup_quick_actions(self):
        """Setup quick action buttons"""
        actions = [
            ("Trial Balance (Dec)", "What is our trial balance for December 2024?"),
            ("WCB Liability", "Calculate our WCB liability for 2024"),
            ("Unpaid Charters", "Show unpaid charters"),
            ("Monthly Summary", "Get December 2024 financial summary"),
            ("Missing Deductions", "Check for missing tax deductions"),
            ("T4 Payroll Summary", "Summarize our T4 payroll and tax compliance"),
            ("GST Rules", "Explain GST calculation for Alberta"),
            ("Tax Liability", "Estimate quarterly tax liability"),
        ]
        
        for label, query in actions:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, query)
            self.quick_list.addItem(item)
    
    def _on_quick_action(self, item: QListWidgetItem):
        """Handle quick action click"""
        query = item.data(Qt.ItemDataRole.UserRole)
        self.input_field.setText(query)
        self._on_send()
    
    def _on_send(self):
        """Handle send button"""
        query = self.input_field.text().strip()
        if not query:
            return
        
        # Add user message to chat
        self._add_chat_message("YOU", query, is_user=True)
        self.input_field.clear()
        
        # Update status
        self.status_label.setText("Processing...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.send_button.setEnabled(False)
        
        # Start worker thread
        self.worker = CopilotWorker(query, self.rag, self.llm, self.executor)
        self.worker.progress.connect(self._on_progress)
        self.worker.response_ready.connect(self._on_response)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    @pyqtSlot(str)
    def _on_progress(self, status: str):
        """Update progress"""
        self.status_label.setText(status)
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
    
    @pyqtSlot(dict)
    def _on_response(self, response: Dict[str, Any]):
        """Handle AI response"""
        # Add response to chat
        text = response.get('text', '')
        self._add_chat_message("AI", text, is_user=False)
        
        # Add function results if any
        functions = response.get('functions', [])
        for func_result in functions:
            func_name = func_result.get('function', 'Unknown')
            success = func_result.get('success', False)
            result = func_result.get('result', {})
            
            if success and isinstance(result, dict):
                # Format result
                result_text = f"\n[{func_name} Result]\n"
                for key, val in list(result.items())[:5]:  # Show first 5 keys
                    result_text += f"  {key}: {val}\n"
                self._add_chat_message("FUNCTION", result_text, is_user=False)
        
        # Update status
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.send_button.setEnabled(True)
    
    @pyqtSlot(str)
    def _on_error(self, error: str):
        """Handle error"""
        self._add_chat_message("ERROR", error, is_user=False)
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.send_button.setEnabled(True)
    
    def _add_chat_message(self, role: str, text: str, is_user: bool = False):
        """Add message to chat display"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Format message
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if is_user:
            formatted = f"\n[{timestamp}] {role}:\n{text}\n"
            cursor.insertText(formatted)
            # User messages in blue
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        else:
            formatted = f"\n[{timestamp}] {role}:\n{text}\n"
            cursor.insertText(formatted)
        
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_display.clear()
        self._add_chat_message("SYSTEM", "Chat cleared. Ready to help!")


def test_widget():
    """Test copilot widget standalone"""
    from rag_engine import KnowledgeRetriever
    from llm_engine import LLMEngine
    from function_executor import FunctionExecutor
    
    app = __import__('PyQt6.QtWidgets', fromlist=['QApplication']).QApplication([])
    
    # Initialize AI components
    rag = KnowledgeRetriever()
    llm = LLMEngine()
    executor = FunctionExecutor()
    
    # Create main window
    window = __import__('PyQt6.QtWidgets', fromlist=['QMainWindow']).QMainWindow()
    window.setWindowTitle("AI Copilot - Test")
    window.setGeometry(100, 100, 1000, 600)
    
    # Add widget
    widget = CopilotWidget(rag_engine=rag, llm_engine=llm, executor=executor)
    window.setCentralWidget(widget)
    
    # Show
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    test_widget()
