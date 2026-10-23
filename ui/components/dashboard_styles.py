"""CSS styles cho Dashboard layout theo spec 2.2.2 - 2.5."""

DASHBOARD_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Source Sans Pro', sans-serif;
}

/* Ẩn sidebar mặc định của Streamlit */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

.stApp {
    background: #fafafa;
}

/* ─── Navbar ─────────────────────────────────────────────────────────── */
.navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #fff;
    border-bottom: 1px solid #e0e0e0;
    padding: 8px 16px;
    height: 55px;
    box-sizing: border-box;
}

.navbar-logo img {
    height: 35px;
    width: auto;
}

.navbar-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

/* ─── Dashboard layout ───────────────────────────────────────────────── */
.dashboard-body {
    display: flex;
    width: 100%;
    min-height: calc(100vh - 55px - 60px);
    overflow: hidden;
}

.dashboard-toolbar {
    width: 185px;
    min-width: 185px;
    max-width: 185px;
    background: #fff;
    border-right: 1px solid #e0e0e0;
    overflow-y: auto;
    height: calc(100vh - 55px - 60px);
}

.dashboard-mashup {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    padding: 16px;
    background: #fafafa;
    height: calc(100vh - 55px - 60px);
}

.dashboard-info {
    width: 320px;
    min-width: 320px;
    max-width: 320px;
    background: #fff;
    border-left: 1px solid #e0e0e0;
    overflow-y: auto;
    padding: 12px;
    height: calc(100vh - 55px - 60px);
}

/* ─── Footer ─────────────────────────────────────────────────────────── */
.footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #fff;
    border-top: 1px solid #e0e0e0;
    padding: 10px 16px;
    height: 60px;
    box-sizing: border-box;
}

.footer-logo img {
    height: 30px;
    width: auto;
}

.footer-credits {
    font-size: 19px;
    font-family: 'Source Sans Pro', sans-serif;
    color: #333;
    margin: 0;
}

.footer-github {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    color: #333;
    text-decoration: none;
    transition: background 0.2s, color 0.2s;
}

.footer-github:hover {
    background: #f2f2f2;
    color: #3f51b5;
}

.footer-github svg {
    width: 24px;
    height: 24px;
    fill: currentColor;
}

/* ─── Toolbar widgets ────────────────────────────────────────────────── */
.toolbar-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #555;
    padding: 12px 10px 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.toolbar-category {
    border-bottom: 1px solid #eee;
}

.toolbar-category-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    color: #333;
    background: #fff;
    user-select: none;
}

.toolbar-category-header:hover {
    background: #f5f5f5;
}

.toolbar-category-header .arrow {
    font-size: 0.7rem;
    color: #888;
}

.toolbar-list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.toolbar-list-item {
    padding: 8px 10px 8px 18px;
    font-size: 0.85rem;
    color: #444;
    cursor: pointer;
    background: rgb(242, 242, 242);
    border-top: 1px solid #e8e8e8;
    transition: background 0.15s, color 0.15s;
}

.toolbar-list-item:hover {
    background: #3f51b5;
    color: #fff;
}

.toolbar-list-item.active {
    background: #3f51b5;
    color: #fff;
}

.toolbar-dimensions {
    font-size: 0.75rem;
    color: #888;
    padding: 6px 10px 10px;
    font-style: italic;
}

/* ─── Navbar buttons (100x35px) ─────────────────────────────────────── */
div[data-testid="column"] .nav-btn > button {
    width: 100px !important;
    min-width: 100px !important;
    height: 35px !important;
    min-height: 35px !important;
    padding: 0 !important;
    font-size: 0.85rem !important;
    font-family: 'Source Sans Pro', sans-serif !important;
    background: #fff !important;
    color: #333 !important;
    border: 1px solid #ccc !important;
    border-radius: 4px !important;
}

div[data-testid="column"] .nav-btn > button:hover {
    background: #3f51b5 !important;
    color: #fff !important;
    border-color: #3f51b5 !important;
}

/* ─── Responsive footer @ 960px ──────────────────────────────────────── */
@media (max-width: 960px) {
    .footer {
        flex-direction: column;
        height: auto;
        gap: 8px;
        padding: 12px;
        text-align: center;
    }

    .footer-credits {
        font-size: 16px;
    }

    .dashboard-body {
        flex-direction: column;
    }

    .dashboard-toolbar,
    .dashboard-info {
        width: 100%;
        min-width: 100%;
        max-width: 100%;
        height: auto;
        max-height: 300px;
    }

    .dashboard-mashup {
        height: auto;
        min-height: 400px;
    }
}

/* Streamlit overrides trong dashboard */
.dashboard-mashup .stChatMessage { border-radius: 8px; }
.dashboard-info .stButton > button { border-radius: 6px; }
"""
