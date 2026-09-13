"""Shared fixtures and environment setup for the test suite."""
import os

# Set required env vars before any module is imported during collection.
os.environ.setdefault("GMAIL_APP_PASSWORD", "test_placeholder")
os.environ.setdefault("ALERT_EMAIL", "test@example.com")
