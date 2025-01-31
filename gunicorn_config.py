# gunicorn_config.py
workers = 2
worker_class = 'eventlet'  # For WebSocket support
worker_connections = 1000
timeout = 300  # Increased timeout
keepalive = 2
