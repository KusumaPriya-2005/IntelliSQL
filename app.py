import streamlit as st
import os
from dotenv import load_dotenv  
from google import genai


# ✅ Load environment variables
load_dotenv()

import db_manager
from db_manager import DB_PATH
from prompt_builder import build_contents, build_system_prompt
from query_executor import run_query
from sql_safety import MAX_ROWS, strip_markdown_fences, validate_and_sanitize

MODEL_NAME = "gemini-2.5-flash"


def get_client():
    """Create the Gemini client lazily so a missing key does not break import."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def get_response(que, system_prompt, client):
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_contents(system_prompt, que)
    )
    return strip_markdown_fences((response.text or "").strip())


def page_home():
    st.markdown("""
        <style>
            body {
                background-color: #2E2E2E;
            }
            .main-title {
                text-align: center;
                color: #4CAF50;  /* Green color for headings */
                font-size: 1.5em;
            }
            .sub-title {
                text-align: center;
                color: #4CAF50; /* Green color for headings */
                font-size: 1.5em;
            }
            .offerings {
                padding: 20px;
                color: white; /* White color for body text */
            }
            .offerings h2{
                color: #4CAF50; /* Green color for headings */
            }
            .offerings ul{
                list-style-type: none;
                padding: 0;
            }
            offerings li { 
                margin: 10px 0;
                font-size: 18px;
            }
            .custom-sidebar { 
                background-color: #2E2E2E;
                color: white;
            }   
        </style>
    """, unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>Welcome to IntelliSQL!</h1>", unsafe_allow_html=True)
    st.markdown("<h2 class='sub-title'>Revolutionizing Database Querying with Advanced LLM Capabilities</h2>", unsafe_allow_html=True)


    col1, col2 = st.columns([1, 1])

    with col1:
        st.image("https://cdn1.iconfinder.com/data/icons/business-dual-color-glyph-set-3/128/Data_warehouse-1024.png", width=500)

    with col2:
        st.markdown("""
        <div class='offerings'>
            <h2>Wide Range of offerings</h2>
            <ul>
                <li>💡 Intelligent Query Assistance</li>
                <li>🔍 Data Exploration and Insights</li>
                <li>📊 Efficient Data Retrieval</li>
                <li>🚀 Performance Optimization</li>
                <li>🔧 Syntax Suggestions</li>
                <li>📉 Trend Analysis</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)    
    
def page_about():
    st.markdown("""
        <style>
            .content {
                color: white; /* white color for body text */
            }
        </style>
    """, unsafe_allow_html=True)
    st.markdown("<h1 style='color: #4CAF50;'>About IntelliSQL</h1>", unsafe_allow_html=True)
    st.markdown("<div class='content'>", unsafe_allow_html=True)
    st.markdown("""
    <h2>IntelliSQL is an innovative project aimed at revolutionizing database querying using advanced Language Model capabilities.Powered by cutting-edge LLM (Large Language Model) architecture, this system offers users an intelligent platform for interacting with SQL databases effortlessly and intuitively.</h2>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.image("https://download.logo.wine/logo/Oracle_SQL_Developer/Oracle_SQL_Developer-Logo.wine.png", width="stretch")

def render_db_status():
    """DB status banner; Initialize button only when the DB/schema is missing."""
    result = st.session_state.pop("init_result", None)
    if result is not None:
        ok, text = result
        (st.success if ok else st.error)(text)
    schema_ready = db_manager.db_exists(DB_PATH) and bool(db_manager.get_schema(DB_PATH).tables)
    if schema_ready:
        st.success(f"Database ready: {DB_PATH}")
        return
    st.warning(
        f"Database not found ({DB_PATH}). This app needs a local SQLite database "
        "to answer queries."
    )
    if st.button("Initialize database", key="init_db_button"):
        try:
            with st.spinner("Initializing database..."):
                init = db_manager.initialize_if_needed(DB_PATH)
            st.session_state["init_result"] = (True, f"Database initialized. {init.message}")
            st.session_state["expand_schema"] = True
        except Exception as e:
            st.session_state["init_result"] = (False, (
                f"Database initialization failed. Details: {e}\n\n"
                "Next steps: check file permissions, ensure the directory is writable, "
                "and retry initialization."
            ))
        st.rerun()


def handle_submit(que, schema):
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("Missing GOOGLE_API_KEY. Set it in your environment or .env file.")
        return
    if not db_manager.db_exists(DB_PATH) or not schema.tables:
        st.warning("Database not initialized. Initialize the database before running queries.")
        return
    if not que.strip():
        st.warning("Please enter a question.")
        return

    try:
        sql = get_response(que, build_system_prompt(schema), get_client())
    except Exception as e:
        st.error(f"Could not get a response from the model: {e}")
        return

    with st.expander("Generated SQL", expanded=False):
        st.code(sql or "(empty)", language="sql")

    gate = validate_and_sanitize(sql)
    if not gate.allowed:
        st.warning("Query blocked")
        st.write(f"Reason: {gate.reason}")
        st.write("What you can try:")
        st.write("- Rephrase as a read-only question, e.g., \"Show all students\"")
        st.write("- Ask for filters/aggregations instead of changes")
        return
    if gate.limit_applied:
        st.info(f"A row limit was applied (max {MAX_ROWS}): `{gate.sanitized_sql}`")

    try:
        result = run_query(DB_PATH, gate.sanitized_sql)
    except Exception as e:
        st.error(f"The query could not be executed: {e}. See the database schema above to rephrase.")
        return

    st.markdown("<div class='response'>", unsafe_allow_html=True)
    st.subheader("The Response is:")
    st.caption(f"Showing up to {MAX_ROWS} rows.")
    if result.rows:
        st.table([dict(zip(result.columns, row)) for row in result.rows])
    else:
        st.write("No rows returned.")
    st.markdown("</div>", unsafe_allow_html=True)


def page_intelligent_query_assistance():
    st.markdown("""
        <style>
            .tool-input {
                margin-bottom: 20px;
                color: white; /* white color for body text */
            }
            .response {
                margin-top: 20px;
                color: white; /* white color for body text */
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='color: #4CAF50;'>Intelligent Query Assistance</h1>", unsafe_allow_html=True)
    st.write("""
    IntelliSQL enhances the querying process by providing intelligent assistance to users. Whether they are novice or experienced SQL users, IntelliSQL guides them through crafting complex queries with ease. By understanding natural language queries, IntelliSQL suggests relevant SQL statements, offers syntax suggestions, and assists in optimizing query performance, thereby streamlining the database interaction experience.
    """)

    col1, col2 = st.columns([2, 1])

    with col1:
        render_db_status()
        schema = db_manager.get_schema(DB_PATH)
        with st.expander("Database schema", expanded=st.session_state.pop("expand_schema", False)):
            if not schema.tables:
                st.write("No tables found.")
            for table in schema.tables:
                st.markdown(f"**Table: {table.name}**")
                for col in table.columns:
                    st.write(f"- {col.name} ({col.type})")

        st.markdown("<div class='tool-input'>", unsafe_allow_html=True)
        que = st.text_input("Enter Your Query:", key="sql_query")
        submit = st.button("Get Answer", key="submit_button", help="Click to retrieve the SQL data")
        st.markdown("</div>", unsafe_allow_html=True)

        # Execute only on explicit submit (never on mere typing / reruns).
        if submit:
            handle_submit(que, schema)

    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/9850/9850877.png", width="stretch")

def main():
    st.set_page_config(
        page_title="IntelliSQL",
        page_icon="",
        layout="wide"
    )
    st.sidebar.title("Navigation")
    st.sidebar.markdown("<style>.sidebar.sidebar-content {background-color: #2E2E2E; color: white;}</style>", unsafe_allow_html=True)
    pages = {
        "Home": page_home,
        "About": page_about,
        "Intelligent Query Assistance": page_intelligent_query_assistance,
    }
    selection = st.sidebar.radio("Go to", list(pages.keys()))
    page = pages[selection]
    page()

if __name__ == "__main__":
    main()



