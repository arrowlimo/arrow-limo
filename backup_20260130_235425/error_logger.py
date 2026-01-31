"""
Centralized Error Logging System
Captures all errors, stores them, and provides UI for review/fixing
"""

import sys
import traceback
import json
from datetime import datetime
from pathlib import Path
import psycopg2
from typing import Optional


class ErrorLogger:
    """Centralized error logger - stores all errors for review"""
    
    def __init__(self, db=None):
        self.db = db
        self.error_log_file = Path("L:/limo/error_log.jsonl")
        self.ensure_error_table()
    
    def ensure_error_table(self):
        """Create errors table if it doesn't exist"""
        if not self.db:
            return
        
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_errors (
                    error_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_type VARCHAR(100),
                    error_message TEXT,
                    traceback TEXT,
                    widget_name VARCHAR(200),
                    action VARCHAR(200),
                    user_context TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolution_notes TEXT,
                    resolved_at TIMESTAMP
                )
            """)
            self.db.commit()
        except Exception as e:
            # Fallback to file-only logging if DB fails
            self.log_to_file({
                'timestamp': datetime.now().isoformat(),
                'error_type': 'ErrorLoggerInit',
                'error_message': f'Failed to create error table: {e}',
                'traceback': traceback.format_exc()
            })
    
    def log_error(self, error: Exception, widget_name: str = "Unknown", 
                  action: str = "Unknown", user_context: str = ""):
        """Log an error to both database and file"""
        
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'widget_name': widget_name,
            'action': action,
            'user_context': user_context
        }
        
        # Always log to file (backup)
        self.log_to_file(error_data)
        
        # Try to log to database
        if self.db:
            try:
                cur = self.db.get_cursor()
                cur.execute("""
                    INSERT INTO app_errors 
                    (error_type, error_message, traceback, widget_name, action, user_context)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    error_data['error_type'],
                    error_data['error_message'],
                    error_data['traceback'],
                    error_data['widget_name'],
                    error_data['action'],
                    error_data['user_context']
                ))
                self.db.commit()
            except Exception as db_err:
                # If database logging fails, at least we have the file
                pass
        
        # Print to console for immediate visibility
        print(f"\n❌ ERROR LOGGED: {error_data['error_type']} in {widget_name}")
        print(f"   Message: {error_data['error_message']}")
        print(f"   See error_log.jsonl for full details\n")
    
    def log_to_file(self, error_data: dict):
        """Append error to JSON lines file"""
        try:
            with open(self.error_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_data) + '\n')
        except Exception as e:
            # Last resort - print to stderr
            print(f"CRITICAL: Cannot write to error log: {e}", file=sys.stderr)
    
    def get_recent_errors(self, limit: int = 100, resolved: Optional[bool] = None):
        """Get recent errors from database"""
        if not self.db:
            return []
        
        try:
            cur = self.db.get_cursor()
            
            if resolved is None:
                query = """
                    SELECT error_id, timestamp, error_type, error_message, 
                           widget_name, action, resolved
                    FROM app_errors
                    ORDER BY timestamp DESC
                    LIMIT %s
                """
                cur.execute(query, (limit,))
            else:
                query = """
                    SELECT error_id, timestamp, error_type, error_message, 
                           widget_name, action, resolved
                    FROM app_errors
                    WHERE resolved = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """
                cur.execute(query, (resolved, limit))
            
            return cur.fetchall()
        except Exception as e:
            print(f"Failed to fetch errors: {e}")
            return []
    
    def get_error_details(self, error_id: int):
        """Get full error details including traceback"""
        if not self.db:
            return None
        
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT error_id, timestamp, error_type, error_message, 
                       traceback, widget_name, action, user_context, 
                       resolved, resolution_notes, resolved_at
                FROM app_errors
                WHERE error_id = %s
            """, (error_id,))
            return cur.fetchone()
        except Exception as e:
            print(f"Failed to fetch error details: {e}")
            return None
    
    def mark_resolved(self, error_id: int, resolution_notes: str = ""):
        """Mark an error as resolved"""
        if not self.db:
            return False
        
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                UPDATE app_errors
                SET resolved = TRUE,
                    resolution_notes = %s,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE error_id = %s
            """, (resolution_notes, error_id))
            self.db.commit()
            return True
        except Exception as e:
            print(f"Failed to mark error as resolved: {e}")
            return False
    
    def get_error_stats(self):
        """Get error statistics"""
        if not self.db:
            return {}
        
        try:
            cur = self.db.get_cursor()
            
            # Total errors
            cur.execute("SELECT COUNT(*) FROM app_errors")
            total = cur.fetchone()[0]
            
            # Unresolved errors
            cur.execute("SELECT COUNT(*) FROM app_errors WHERE resolved = FALSE")
            unresolved = cur.fetchone()[0]
            
            # Errors by type
            cur.execute("""
                SELECT error_type, COUNT(*) 
                FROM app_errors 
                WHERE resolved = FALSE
                GROUP BY error_type 
                ORDER BY COUNT(*) DESC 
                LIMIT 5
            """)
            by_type = cur.fetchall()
            
            # Errors by widget
            cur.execute("""
                SELECT widget_name, COUNT(*) 
                FROM app_errors 
                WHERE resolved = FALSE
                GROUP BY widget_name 
                ORDER BY COUNT(*) DESC 
                LIMIT 5
            """)
            by_widget = cur.fetchall()
            
            return {
                'total': total,
                'unresolved': unresolved,
                'resolved': total - unresolved,
                'by_type': by_type,
                'by_widget': by_widget
            }
        except Exception as e:
            print(f"Failed to get error stats: {e}")
            return {}


# Global error logger instance
_global_error_logger = None


def init_error_logger(db):
    """Initialize the global error logger"""
    global _global_error_logger
    _global_error_logger = ErrorLogger(db)
    return _global_error_logger


def get_error_logger():
    """Get the global error logger instance"""
    global _global_error_logger
    if _global_error_logger is None:
        _global_error_logger = ErrorLogger()
    return _global_error_logger


def log_error(error: Exception, widget_name: str = "Unknown", 
              action: str = "Unknown", user_context: str = ""):
    """Convenience function to log an error"""
    logger = get_error_logger()
    logger.log_error(error, widget_name, action, user_context)
