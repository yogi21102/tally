# tools/tally_company_tool.py
import pyodbc
from langchain.tools import tool
from dotenv import load_dotenv
import os

# Load the .env variables
load_dotenv()

CONNECTION_STRING = os.getenv("ODBC_CONNECTION_STRING")

def _detect_tally_driver():
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        for d in drivers:
            if "tally" in d.lower():
                return d
        return None
    except Exception:
        return None


@tool("get_company_list")
def get_company_list() -> list:
    """
    Fetch list of companies from Tally using ODBC (DSN-less).
    Uses connection string from .env.
    """

    # Use a local connection string variable so we don't shadow the module constant
    conn_str = CONNECTION_STRING
    if not conn_str:
        # Try to auto-detect a Tally ODBC driver and build a default connection string
        detected = _detect_tally_driver()
        if not detected:
            return {"error": "ODBC_CONNECTION_STRING not found in .env and no Tally ODBC driver detected."}
        conn_str = f"Driver={{{detected}}};Server=localhost;Port=9000"

    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
    except Exception as e:
        # If connection failed, attempt to detect a Tally driver and retry with that name
        err = str(e)
        detected = _detect_tally_driver()
        if detected and ("tally" in detected.lower()):
            try:
                fallback = f"Driver={{{detected}}};Server=localhost;Port=9000"
                conn = pyodbc.connect(fallback, autocommit=True)
                cursor = conn.cursor()
            except Exception as e2:
                return {"error": f"ODBC connection failed: {err} -- fallback attempt also failed: {e2}"}
        else:
            return {"error": f"ODBC connection failed: {err}. Installed drivers: {pyodbc.drivers()}"}

    try:
        cursor.execute("SELECT $Name FROM Company")
        companies = [row[0] for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        return companies

    except Exception as e:
        return {"error": f"ODBC query failed: {str(e)}"}
