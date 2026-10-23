"""Footer component — spec 2.3."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
GITHUB_URL = "https://github.com/sdateamdtu2020"


def render_footer() -> None:
    """Render Footer với Logo, Credits và GitHub link."""
    logo_b64 = _logo_as_base64()

    st.markdown(
        f"""
        <div class="footer">
            <div class="footer-logo">
                <img src="data:image/png;base64,{logo_b64}" alt="Logo" />
            </div>
            <p class="footer-credits">SDA-Team © 2020</p>
            <a class="footer-github" href="{GITHUB_URL}" target="_blank" rel="noopener noreferrer"
               title="GitHub">
                <svg viewBox="0 0 496 512" xmlns="http://www.w3.org/2000/svg">
                    <path d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3 .3-5.6-1.3-5.6-3.6
                    0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3
                    4.9 2.6 1 5.6 0 6.1-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5 .3-6.1 2.3zm44.2-1.7c-2.9
                    .7-4.9 2.6-4.6 4.9 .3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244
                    8C106.9 8 0 113 0 252c0 110 63.2 205.8 154.8 250.2 11.3 2.1 15.5-5 15.5-11.1
                    0-5.5-.2-22.2-.3-40.3-61.3 13.3-74.1-29.5-74.1-29.5-10.1-25.7-24.8-32.5-24.8-32.5-20.3-13.9
                    .3-13.6 .3-13.6 22.5 1.6 34.3 23.2 34.3 23.2 20 34.3 52.5 24.4 65.3 18.7 2-14.5 7.8-24.4
                    14.2-30-49.7-5.6-102-24.9-102-114.9 0-25.4 9.1-46.1 24-62.3-2.4-5.9-10.4-29.6 2.3-61.7
                    0 0 19.6-6.2 64 23.8 18.6-5.2 38.5-7.8 58.3-7.9 19.8 .1 39.7 2.7 58.3 7.9 44.4-30 64-23.8
                    64-23.8 12.7 32.1 5.7 55.8 2.3 61.7 14.9 16.2 24 36.9 24 62.3 0 90.3-52.4 109.2-102.3
                    114.9 8 6.9 15.2 20.5 15.2 34.6 0 25- .2 45.1-.2 51.2 0 6.1 4.2 13.2 15.5 11.1C433.1 457.8
                    496 362 496 252 496 113 389 8 244 8z"/>
                </svg>
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _logo_as_base64() -> str:
    import base64
    if LOGO_PATH.exists():
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return ""
