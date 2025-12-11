# debug_odbc.py
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

print("--- Tally ODBC Debugger ---")

# 1. Print what we are trying to use
conn_str = os.getenv("ODBC_CONNECTION_STRING")
print(f"Testing Connection String: {conn_str}")

# 2. Check installed drivers
print("\nInstalled Drivers on your PC:")
found_tally = False
drivers = pyodbc.drivers()
for d in drivers:
    print(f" - {d}")
    if "Tally" in d:
        found_tally = True

if not found_tally:
    print("\n⚠️ WARNING: No Tally ODBC Driver found! Reinstall Tally Prime.")
else:
    print("\n✅ Tally Driver found.")

# 3. Attempt Connection
print("\nAttempting connection...")
try:
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    
    # Try to fetch companies
    cursor.execute("SELECT $Name FROM Company")
    rows = cursor.fetchall()
    
    if rows:
        print(f"\n✅ SUCCESS! Found {len(rows)} companies:")
        for row in rows:
            print(f"   * {row[0]}")
    else:
        print("\n⚠️ Connection Successful, but NO COMPANIES found.")
        print("   -> Make sure a company is fully loaded in Tally (Gateway of Tally).")
        
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ CONNECTION FAILED:\n{e}")
    print("\nSUGGESTION: Copy the exact driver name from the 'Installed Drivers' list above")
    print("and paste it into your .env file inside the { } brackets.")