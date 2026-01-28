"""
Configuration management module for Arrow Limousine Management System

Centralized configuration loading and environment variable management
to eliminate duplicate configuration code across the codebase.

Usage:
    from shared.config import get_config, get_db_config, setup_logging
    
    config = get_config()
    logger = setup_logging()
"""

import os
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    load_dotenv(env_file)

class Config:
    """Centralized configuration class with environment variable management."""
    
    def __init__(self):
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables with defaults."""
        
        # Database configuration
        self._config['database'] = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'name': os.getenv('DB_NAME', 'almsdata'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
        }
        
        # Application configuration
        self._config['app'] = {
            'name': os.getenv('APP_NAME', 'Arrow Limousine Management System'),
            'version': os.getenv('APP_VERSION', '2025.1'),
            'environment': os.getenv('APP_ENV', 'development'),
            'debug': os.getenv('APP_DEBUG', 'false').lower() == 'true',
            'secret_key': os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        }
        
        # API configuration
        self._config['api'] = {
            'host': os.getenv('API_HOST', '127.0.0.1'),
            'port': int(os.getenv('API_PORT', '5000')),
            'cors_origins': os.getenv('CORS_ORIGINS', '*').split(','),
            'api_keys': [k.strip() for k in os.getenv('API_KEYS', '').split(',') if k.strip()],
            'rate_limit_enabled': os.getenv('RATE_LIMIT_ENABLED', '1') not in ('0', 'false'),
            'rate_limit_count': int(os.getenv('RATE_LIMIT_COUNT', '60')),
            'rate_limit_window': int(os.getenv('RATE_LIMIT_WINDOW', '60')),
        }
        
        # Logging configuration
        self._config['logging'] = {
            'level': os.getenv('LOG_LEVEL', 'INFO').upper(),
            'format': os.getenv('LOG_FORMAT', 'text').lower(),  # 'text' or 'json'
            'file': os.getenv('LOG_FILE', 'app.log'),
            'max_bytes': int(os.getenv('LOG_MAX_BYTES', '5242880')),  # 5MB
            'backup_count': int(os.getenv('LOG_BACKUP_COUNT', '5')),
            'request_logging': os.getenv('REQUEST_LOGGING', '1') not in ('0', 'false'),
        }
        
        # Business configuration
        self._config['business'] = {
            'company_name': os.getenv('COMPANY_NAME', 'Arrow Limousine Ltd.'),
            'company_address': os.getenv('COMPANY_ADDRESS', 'Calgary, Alberta, Canada'),
            'gst_number': os.getenv('GST_NUMBER', ''),
            'business_number': os.getenv('BUSINESS_NUMBER', ''),
        }
        
        # File storage configuration
        self._config['storage'] = {
            'upload_folder': os.getenv('UPLOAD_FOLDER', 'uploads'),
            'static_folder': os.getenv('STATIC_FOLDER', 'frontend/dist'),
            'max_file_size': int(os.getenv('MAX_FILE_SIZE', '16777216')),  # 16MB
            'allowed_extensions': os.getenv('ALLOWED_EXTENSIONS', 'pdf,jpg,jpeg,png').split(','),
        }
        
        # Email configuration
        self._config['email'] = {
            'smtp_host': os.getenv('SMTP_HOST', ''),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_user': os.getenv('SMTP_USER', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('FROM_EMAIL', 'noreply@arrowlimo.ca'),
        }
        
        # Sentry configuration (optional)
        self._config['sentry'] = {
            'dsn': os.getenv('SENTRY_DSN', ''),
            'traces_sample_rate': float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.0')),
            'environment': os.getenv('SENTRY_ENVIRONMENT', self._config['app']['environment']),
        }
        
        # LMS integration
        self._config['lms'] = {
            'path': os.getenv('LMS_PATH', r'L:\limo\backups\lms.mdb'),
            'backup_path': os.getenv('LMS_BACKUP_PATH', r'L:\limo\backups'),
        }
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value by section and key."""
        if key is None:
            return self._config.get(section, default)
        return self._config.get(section, {}).get(key, default)
    
    def get_database_url(self) -> str:
        """Get PostgreSQL database URL."""
        db = self._config['database']
        return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self._config['app']['environment'] == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self._config['app']['environment'] == 'development'

# Global configuration instance
_config = Config()

def get_config() -> Config:
    """Get the global configuration instance."""
    return _config

def get_db_config() -> Dict[str, Any]:
    """Get database configuration dictionary."""
    return _config.get('database')

def get_api_config() -> Dict[str, Any]:
    """Get API configuration dictionary."""
    return _config.get('api')

def get_business_config() -> Dict[str, Any]:
    """Get business configuration dictionary."""
    return _config.get('business')

def setup_logging(logger_name: str = 'arrow', **kwargs) -> logging.Logger:
    """
    Setup standardized logging configuration.
    
    Args:
        logger_name: Name of the logger
        **kwargs: Override default logging configuration
        
    Returns:
        Configured logger instance
    """
    log_config = _config.get('logging')
    log_config.update(kwargs)  # Allow overrides
    
    logger = logging.getLogger(logger_name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
        
    logger.setLevel(getattr(logging, log_config['level']))
    
    # Create formatter
    if log_config['format'] == 'json':
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                data = {
                    'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'funcName': record.funcName,
                    'lineno': record.lineno,
                }
                if record.exc_info:
                    data['exception'] = self.formatException(record.exc_info)
                return json.dumps(data, separators=(',', ':'))
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s [%(module)s:%(funcName)s:%(lineno)d] %(message)s'
        )
    
    # File handler with rotation
    if log_config['file']:
        file_handler = RotatingFileHandler(
            log_config['file'],
            maxBytes=log_config['max_bytes'],
            backupCount=log_config['backup_count'],
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    return logger

def get_upload_path(filename: str = '') -> Path:
    """Get the upload directory path, optionally joined with filename."""
    upload_dir = Path(_config.get('storage', 'upload_folder'))
    upload_dir.mkdir(exist_ok=True)
    return upload_dir / filename if filename else upload_dir

def get_static_path(filename: str = '') -> Path:
    """Get the static files directory path, optionally joined with filename."""
    static_dir = Path(_config.get('storage', 'static_folder'))
    return static_dir / filename if filename else static_dir

def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed for upload."""
    if not filename or '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    allowed = _config.get('storage', 'allowed_extensions')
    return ext in allowed

def validate_environment() -> Dict[str, Any]:
    """
    Validate the current environment configuration.
    
    Returns:
        Dictionary with validation results and any issues found
    """
    issues = []
    warnings = []
    
    # Check required environment variables
    required_vars = [
        'DB_PASSWORD',  # Database should have proper password
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            issues.append(f"Missing required environment variable: {var}")
    
    # Check database connection
    try:
        from .db_utils import test_connection
        if not test_connection():
            issues.append("Cannot connect to database")
    except Exception as e:
        issues.append(f"Database connection test failed: {e}")
    
    # Check file permissions
    try:
        upload_path = get_upload_path()
        upload_path.mkdir(exist_ok=True)
        test_file = upload_path / '.test'
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        issues.append(f"Upload directory not writable: {e}")
    
    # Check log file permissions
    log_file = _config.get('logging', 'file')
    if log_file:
        try:
            Path(log_file).touch()
        except Exception as e:
            warnings.append(f"Log file may not be writable: {e}")
    
    # Production environment checks
    if _config.is_production():
        if _config.get('app', 'secret_key') == 'dev-secret-key-change-in-production':
            issues.append("Production environment using default secret key")
        
        if _config.get('app', 'debug'):
            warnings.append("Debug mode enabled in production")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'environment': _config.get('app', 'environment'),
        'config_summary': {
            'database': f"{_config.get('database', 'host')}:{_config.get('database', 'port')}/{_config.get('database', 'name')}",
            'api_port': _config.get('api', 'port'),
            'logging_level': _config.get('logging', 'level'),
        }
    }