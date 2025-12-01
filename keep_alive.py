"""
Backend Keep-Alive System for Render
A robust Python-based keep-alive mechanism that prevents your Flask backend
from sleeping on Render's free tier by making periodic internal pings.

This runs as a background thread and doesn't rely on external services.
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class BackendKeepAlive:
    """
    Manages the keep-alive system for Render backends.
    Prevents automatic sleep by pinging the service at strategic intervals.
    """

    def __init__(
        self,
        app=None,
        backend_url: Optional[str] = None,
        primary_interval: int = 25 * 60,  # 25 minutes in seconds
        secondary_interval: int = 15 * 60,  # 15 minutes in seconds
        health_check_interval: int = 2 * 60,  # 2 minutes in seconds
        request_timeout: int = 10,  # 10 seconds
        max_retries: int = 3,
        failure_threshold: int = 5,
        verbose: bool = True,
        webhook_url: Optional[str] = None,
    ):
        """
        Initialize the keep-alive system.

        Args:
            app: Flask application instance (optional, can call init_app later)
            backend_url: The base URL of the backend (e.g., http://localhost:5000)
            primary_interval: Primary ping interval in seconds (default 25 min)
            secondary_interval: Secondary ping interval in seconds (default 15 min)
            health_check_interval: Health check interval in seconds (default 2 min)
            request_timeout: Request timeout in seconds (default 10)
            max_retries: Maximum retry attempts for failed requests (default 3)
            failure_threshold: Consecutive failures before alert (default 5)
            verbose: Enable detailed logging (default True)
            webhook_url: Optional webhook URL for critical alerts
        """
        self.app = app
        self.backend_url = backend_url
        self.primary_interval = primary_interval
        self.secondary_interval = secondary_interval
        self.health_check_interval = health_check_interval
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.verbose = verbose
        self.webhook_url = webhook_url

        # Internal state
        self.threads = []
        self.is_active = False
        self.lock = threading.Lock()
        self.start_time = None
        self.success_count = 0
        self.failure_count = 0
        self.request_count = 0
        self.last_ping_time = None
        self.last_health_status = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        Initialize the keep-alive system with a Flask app.
        This allows for factory pattern initialization.
        """
        self.app = app
        
        # Get backend URL from config or environment
        if not self.backend_url:
            self.backend_url = app.config.get(
                'BACKEND_URL',
                os.getenv('BACKEND_URL', 'http://localhost:5000')
            )

    def start(self, delay_startup_ping: int = 10):
        """
        Start the keep-alive system with all background threads.
        
        Args:
            delay_startup_ping: Seconds to wait before first ping (allows server to initialize)
        """
        if self.is_active:
            self.log('⚠️  Keep-alive system already running', 'warning')
            return

        with self.lock:
            self.is_active = True
            self.start_time = datetime.now()
            self.success_count = 0
            self.failure_count = 0
            self.request_count = 0

        self.log('🚀 Starting Backend Keep-Alive System', 'info')
        self.log(f'📍 Backend URL: {self.backend_url}', 'info')
        self.log(f'⏱️  Primary interval: {self.primary_interval // 60} minutes', 'info')
        self.log(f'⏱️  Secondary interval: {self.secondary_interval // 60} minutes', 'info')
        self.log(f'⏱️  Health check interval: {self.health_check_interval // 60} minutes', 'info')

        # Start background threads
        self._start_primary_keep_alive()
        self._start_secondary_keep_alive()
        self._start_health_monitoring()

        # Perform initial ping after server is ready
        self.log(f'⏳ Waiting {delay_startup_ping}s for server to fully initialize before first ping...', 'debug')
        threading.Timer(
            delay_startup_ping,
            self._ping,
            args=('startup', 0)
        ).start()

    def _start_primary_keep_alive(self):
        """Start the primary keep-alive thread (25-minute interval)."""
        thread = threading.Thread(
            target=self._keep_alive_loop,
            args=(self.primary_interval, 'primary'),
            daemon=True,
            name='KeepAlive-Primary'
        )
        thread.start()
        self.threads.append(thread)
        self.log('✅ Primary keep-alive thread started', 'debug')

    def _start_secondary_keep_alive(self):
        """Start the secondary keep-alive thread (15-minute interval)."""
        thread = threading.Thread(
            target=self._keep_alive_loop,
            args=(self.secondary_interval, 'secondary'),
            daemon=True,
            name='KeepAlive-Secondary'
        )
        thread.start()
        self.threads.append(thread)
        self.log('✅ Secondary keep-alive thread started', 'debug')

    def _start_health_monitoring(self):
        """Start the health monitoring thread (2-minute interval)."""
        thread = threading.Thread(
            target=self._keep_alive_loop,
            args=(self.health_check_interval, 'health'),
            daemon=True,
            name='KeepAlive-Health'
        )
        thread.start()
        self.threads.append(thread)
        self.log('✅ Health monitoring thread started', 'debug')

    def _keep_alive_loop(self, interval: int, ping_type: str):
        """
        Continuous loop for keep-alive pings.

        Args:
            interval: Time in seconds between pings
            ping_type: Type of ping (primary, secondary, health)
        """
        while self.is_active:
            try:
                time.sleep(interval)
                if self.is_active:  # Check again after sleep
                    if ping_type == 'health':
                        self._check_health()
                    else:
                        self._ping(ping_type, 0)
            except Exception as e:
                self.log(f'❌ Error in {ping_type} keep-alive loop: {str(e)}', 'error')
                time.sleep(5)  # Brief pause before retry

    def _ping(self, ping_type: str, retry_count: int):
        """
        Send a ping request to the backend health endpoint.

        Args:
            ping_type: Type of ping (primary, secondary, startup)
            retry_count: Current retry attempt number
        """
        try:
            self.log(
                f'📤 Sending {ping_type} ping (attempt {retry_count + 1}/{self.max_retries + 1})...',
                'debug'
            )

            response = self._make_request('/api/health', method='GET')

            with self.lock:
                self.last_ping_time = datetime.now()
                self.request_count += 1
                self.failure_count = 0  # Reset on success
                self.success_count += 1

            self.log(
                f'✅ {ping_type} ping successful! '
                f'Status: {response.status_code} | Total pings: {self.success_count}',
                'info'
            )

            # Log detailed response if verbose
            if self.verbose and response.status_code == 200:
                try:
                    data = response.json()
                    if 'database' in data:
                        self.log(f'   Database: {data["database"].get("status", "N/A")}', 'debug')
                    if 'storage' in data:
                        self.log(f'   Cloudinary: {data["storage"].get("cloudinary", {}).get("status", "N/A")}', 'debug')
                except:
                    pass

            return True

        except Exception as error:
            # During startup, don't increment failure count as aggressively
            if ping_type != 'startup':
                with self.lock:
                    self.failure_count += 1
                
                self.log(
                    f'❌ {ping_type} ping failed ({self.failure_count}/{self.failure_threshold}): {str(error)}',
                    'error'
                )
            else:
                # Startup failures are logged at debug level
                self.log(
                    f'⚠️  startup ping not ready yet (attempt {retry_count + 1}/{self.max_retries + 1}): {str(error)}',
                    'debug'
                )

            # Retry logic with exponential backoff
            if retry_count < self.max_retries:
                backoff_delay = min(
                    5 * (2 ** retry_count),  # 5s, 10s, 20s, etc.
                    60  # Max 60 seconds
                )
                
                if ping_type == 'startup':
                    self.log(
                        f'🔄 Retrying startup ping in {backoff_delay} seconds... '
                        f'(retry {retry_count + 1}/{self.max_retries})',
                        'debug'
                    )
                else:
                    self.log(
                        f'🔄 Retrying in {backoff_delay} seconds... '
                        f'(retry {retry_count + 1}/{self.max_retries})',
                        'warning'
                    )
                
                threading.Timer(
                    backoff_delay,
                    self._ping,
                    args=(ping_type, retry_count + 1)
                ).start()
            else:
                if ping_type != 'startup':
                    self.log(f'💥 All retry attempts exhausted for {ping_type} ping', 'error')
                else:
                    self.log(f'ℹ️  Startup ping initialization failed, will retry during regular intervals', 'info')

            # Alert if failure threshold exceeded (only for non-startup pings)
            if ping_type != 'startup' and self.failure_count >= self.failure_threshold:
                self._handle_critical_failure()

            return False

    def _check_health(self):
        """Check the health of the backend service."""
        try:
            response = self._make_request('/api/health', method='GET')

            if response.status_code == 200:
                data = response.json()
                with self.lock:
                    self.last_health_status = {
                        'timestamp': datetime.now().isoformat(),
                        'status': 'healthy',
                        'database': data.get('database', {}).get('status'),
                        'cloudinary': data.get('storage', {}).get('cloudinary', {}).get('status'),
                        'google_drive': data.get('storage', {}).get('google_drive', {}).get('status'),
                    }

                self.log(
                    f'💚 Health check passed | '
                    f'Database: {self.last_health_status["database"]} | '
                    f'Drive: {self.last_health_status["google_drive"]}',
                    'debug'
                )
            else:
                self.log(f'💛 Health check returned status {response.status_code}', 'warning')

        except Exception as error:
            with self.lock:
                self.last_health_status = {
                    'timestamp': datetime.now().isoformat(),
                    'status': 'unhealthy',
                    'error': str(error)
                }

            self.log(f'💔 Health check failed: {str(error)}', 'warning')

    def _make_request(self, endpoint: str, method: str = 'GET', **kwargs):
        """
        Make an HTTP request to the backend.

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            **kwargs: Additional request parameters

        Returns:
            requests.Response object

        Raises:
            Exception: If request fails
        """
        url = f'{self.backend_url}{endpoint}'

        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'BackendKeepAlive/1.0',
            }

            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=self.request_timeout,
                **kwargs
            )

            if response.status_code >= 500:
                raise Exception(f'Server error: {response.status_code}')

            return response

        except requests.exceptions.Timeout:
            raise Exception(f'Request timeout after {self.request_timeout}s')
        except requests.exceptions.ConnectionError:
            raise Exception('Failed to connect to backend')
        except Exception as e:
            raise Exception(f'Request failed: {str(e)}')

    def _handle_critical_failure(self):
        """Handle critical failures when threshold is exceeded."""
        message = (
            f'🚨 CRITICAL: Backend has failed '
            f'{self.failure_count} consecutive ping attempts'
        )

        self.log(message, 'critical')

        # Send webhook alert if configured
        if self.webhook_url:
            try:
                requests.post(
                    self.webhook_url,
                    json={
                        'level': 'critical',
                        'message': message,
                        'timestamp': datetime.now().isoformat(),
                        'backend_url': self.backend_url,
                        'failure_count': self.failure_count,
                        'last_health': self.last_health_status,
                    },
                    timeout=5
                )
                self.log('📨 Sent critical alert to webhook', 'info')
            except Exception as error:
                self.log(f'Failed to send webhook alert: {str(error)}', 'error')

    def stop(self):
        """Stop the keep-alive system gracefully."""
        if not self.is_active:
            self.log('⚠️  Keep-alive system is not running', 'warning')
            return

        with self.lock:
            self.is_active = False

        self.log('🛑 Stopping Backend Keep-Alive System', 'info')

        # Wait for threads to finish (with timeout)
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2)

        # Print final statistics
        if self.start_time:
            uptime = datetime.now() - self.start_time
            uptime_minutes = uptime.total_seconds() // 60
            uptime_seconds = int(uptime.total_seconds() % 60)

            self.log(
                f'📊 Session Stats: {int(uptime_minutes)}m {uptime_seconds}s uptime | '
                f'{self.success_count} successful pings | '
                f'{self.failure_count} consecutive failures',
                'info'
            )

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the keep-alive system.

        Returns:
            Dictionary containing status information
        """
        uptime = None
        if self.is_active and self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()

        with self.lock:
            return {
                'active': self.is_active,
                'backend_url': self.backend_url,
                'uptime_seconds': uptime,
                'total_requests': self.request_count,
                'success_count': self.success_count,
                'failure_count': self.failure_count,
                'last_ping_time': self.last_ping_time.isoformat() if self.last_ping_time else None,
                'last_health_status': self.last_health_status,
                'config': {
                    'primary_interval_seconds': self.primary_interval,
                    'secondary_interval_seconds': self.secondary_interval,
                    'health_check_interval_seconds': self.health_check_interval,
                    'failure_threshold': self.failure_threshold,
                }
            }

    def log(self, message: str, level: str = 'info'):
        """
        Log messages with appropriate level.

        Args:
            message: Log message
            level: Log level (debug, info, warning, error, critical)
        """
        if level == 'debug' and not self.verbose:
            return

        log_func = {
            'debug': logger.debug,
            'info': logger.info,
            'warning': logger.warning,
            'error': logger.error,
            'critical': logger.critical,
        }.get(level, logger.info)

        log_func(message)


def require_keep_alive_active(func):
    """
    Decorator to require that the keep-alive system is active.
    Returns 503 Service Unavailable if not active.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # This assumes 'keep_alive' is available in the Flask app context
        from flask import current_app
        
        if hasattr(current_app, 'keep_alive') and not current_app.keep_alive.is_active:
            return jsonify({'error': 'Keep-alive system not active'}), 503
        
        return func(*args, **kwargs)
    
    return wrapper
