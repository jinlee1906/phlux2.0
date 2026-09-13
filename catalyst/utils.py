"""Shared utilities: WebDriver factory for the Selenium fallback and detection rendering."""
from __future__ import annotations

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

_CHROME_DRIVER_PATH: str | None = None


def _get_chrome_driver_path() -> str:
    global _CHROME_DRIVER_PATH
    if _CHROME_DRIVER_PATH is None:
        _CHROME_DRIVER_PATH = ChromeDriverManager().install()
    return _CHROME_DRIVER_PATH


def get_driver(headless: bool = True, use_undetected: bool = False):
    """Create and return a Selenium WebDriver instance.

    Args:
        headless: Run the browser without a visible window.
        use_undetected: Use ``undetected_chromedriver`` to bypass bot detection.

    Returns:
        A configured Chrome WebDriver.
    """
    chrome_args = [
        "--disable-gpu",
        "--window-size=1920x1080",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    ]

    if use_undetected:
        options = uc.ChromeOptions()
        options.headless = headless
        for arg in chrome_args:
            options.add_argument(arg)
        return uc.Chrome(options=options)

    options = Options()
    if headless:
        options.add_argument("--headless")
    for arg in chrome_args:
        options.add_argument(arg)
    return webdriver.Chrome(service=Service(_get_chrome_driver_path()), options=options)
