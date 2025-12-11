# tools/get_report_tool.py
import requests
import xml.etree.ElementTree as ET
from langchain.tools import tool
from dotenv import load_dotenv
import os

load_dotenv()
TALLY_URL = os.getenv("TALLY_HTTP_HOST")

def build_report_envelope(report_name: str, company_name: str) -> str:
    """
    Constructs a robust Tally XML Request.
    Includes Date Ranges and Export Format to prevent empty data.
    """
    def esc(s):
        if s is None: return ''
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    rid = esc(report_name)
    cname = esc(company_name)

    # We set a wide date range to ensure we capture data even if Tally's current period is different.
    # You can adjust these years if needed.
    return f"""
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Export Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>{rid}</REPORTNAME>
        <STATICVARIABLES>
            <SVCurrentCompany>{cname}</SVCurrentCompany>
            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            <SVFROMDATE>20200401</SVFROMDATE>
            <SVTODATE>20300331</SVTODATE>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>
""".strip()

def xml_to_dict(elem):
    """
    A robust XML-to-Dict converter that handles Tally's quirks:
    1. Captures Attributes (Tally often puts values in attributes).
    2. Handles Lists (Repeating tags like <LEDGER>).
    3. Cleans whitespace.
    """
    # 1. Capture Attributes (Crucial for some Tally reports)
    d = {k: v for k, v in elem.attrib.items()}
    
    # 2. Capture Children
    children = list(elem)
    if children:
        child_counts = {}
        for child in children:
            child_counts[child.tag] = child_counts.get(child.tag, 0) + 1
            
        for child in children:
            # Recursive call
            child_dict = xml_to_dict(child)
            
            # If multiple children have same tag, make it a list
            if child_counts[child.tag] > 1:
                if child.tag not in d:
                    d[child.tag] = []
                d[child.tag].append(child_dict)
            else:
                d[child.tag] = child_dict
    
    # 3. Capture Text
    text = elem.text.strip() if elem.text else ""
    if text:
        if children or d:
            # If we have both children/attributes AND text, store text in 'content'
            d["content"] = text
        else:
            # If it's a leaf node with only text, return the string directly
            return text
            
    return d

@tool("get_report")
def get_report(company_name: str, report_name: str):
    """
    Fetch report from Tally using HTTP XML.
    """
    if not TALLY_URL:
        return {"error": "Missing TALLY_HTTP_HOST in .env"}

    xml_payload = build_report_envelope(report_name, company_name)

    try:
        response = requests.post(TALLY_URL, data=xml_payload)
        # Tally sometimes sends weird encodings, force UTF-8
        response.encoding = 'utf-8' 
    except Exception as e:
        return {"error": f"HTTP connection failed: {str(e)}"}

    raw_xml = response.text.strip()

    if not raw_xml:
        return {"error": "Tally returned an empty response"}

    try:
        root = ET.fromstring(raw_xml)
        
        # Check for Tally Errors inside the XML
        if "LINEERROR" in raw_xml:
             return {"error": "Tally Report Error", "raw": raw_xml}
             
        parsed = xml_to_dict(root)
        return parsed
    except Exception as e:
        return {"error": f"XML Parsing Failed: {str(e)}", "raw_snippet": raw_xml[:500]}