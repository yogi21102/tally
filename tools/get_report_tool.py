# tools/get_report_tool.py
import requests
import xml.etree.ElementTree as ET
from langchain.tools import tool
from dotenv import load_dotenv
import os
import json
import re

load_dotenv()
TALLY_URL = os.getenv("TALLY_HTTP_HOST", "http://localhost:9000")

def escape_xml(value: str) -> str:
    """Escapes special characters for XML requests."""
    if not value: return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

def clean_tally_xml(xml_string: str) -> str:
    """
    The 'Nuclear' Cleaner.
    Uses logic to validate every single XML entity and destroy illegal ones.
    """
    if not xml_string: return ""

    # 1. Remove XML Declaration
    xml_string = re.sub(r'<\?xml.*?\?>', '', xml_string)

    # 2. Fix Raw Ampersands (e.g. "AT&T")
    xml_string = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', xml_string)

    # 3. LOGIC-BASED ENTITY CLEANER
    # Finds any entity like &#123; or &#x1F;
    def validate_entity(match):
        entity_body = match.group(1)
        try:
            # Convert to integer (handle Hex 'x' or Decimal)
            if entity_body.lower().startswith("x"):
                codepoint = int(entity_body[1:], 16)
            else:
                codepoint = int(entity_body)

            # XML 1.0 Allowlist: 
            # Tab (9), Newline (10), Carriage Return (13), and anything above 31
            if codepoint in (9, 10, 13) or codepoint >= 32:
                return match.group(0) # Keep it, it's valid
            else:
                return "" # DELETE IT (It's an illegal control char like &#4;)
        except:
            return "" # Malformed entity? Delete it.

    # Apply the validator to all numeric entities
    xml_string = re.sub(r'&#(x[0-9a-fA-F]+|[0-9]+);', validate_entity, xml_string)

    # 4. Remove Raw Control Characters (The actual bytes)
    xml_string = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', xml_string)

    return xml_string.strip()

@tool("get_report")
def get_report(company_name: str, report_name: str) -> str:
    """Fetch data from Tally via XML over HTTP."""
    try:
        safe_report = escape_xml(report_name)
        safe_company = escape_xml(company_name)

        xml_req = f"""<ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>{safe_report}</REPORTNAME>
                        <STATICVARIABLES>
                            <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                            <SVCurrentCompany>{safe_company}</SVCurrentCompany>
                        </STATICVARIABLES>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>"""

        response = requests.post(TALLY_URL, data=xml_req, timeout=45)

        # Decoding
        content = response.content
        decoded_xml = ""
        try:
            if content.startswith(b'\xff\xfe'): decoded_xml = content.decode('utf-16')
            elif content.startswith(b'\xef\xbb\xbf'): decoded_xml = content.decode('utf-8-sig')
            else: decoded_xml = content.decode('utf-8')
        except:
            decoded_xml = content.decode('latin-1')

        # --- RUN THE NUCLEAR CLEANER ---
        decoded_xml = clean_tally_xml(decoded_xml)

        if "Unknown Request" in decoded_xml or "LINEERROR" in decoded_xml:
             return f"Error: Tally refused the request for '{report_name}'."

        # Parse XML
        try:
            root = ET.fromstring(decoded_xml)
        except ET.ParseError as e:
            # If it fails, let's wrap it in ROOT just in case
            try:
                decoded_xml = f"<ROOT>{decoded_xml}</ROOT>"
                root = ET.fromstring(decoded_xml)
            except:
                # Debugging: Return the specific error location
                return f"Error parsing Tally XML: {str(e)}"

        # Convert to Dict
        def xml_to_dict(elem):
            d = {}
            d.update(elem.attrib)
            children = list(elem)
            if children:
                child_counts = {}
                for child in children:
                    child_counts[child.tag] = child_counts.get(child.tag, 0) + 1
                for child in children:
                    child_dict = xml_to_dict(child)
                    if child_counts[child.tag] > 1:
                        if child.tag not in d: d[child.tag] = []
                        d[child.tag].append(child_dict)
                    else:
                        d[child.tag] = child_dict
            text = elem.text.strip() if elem.text else ""
            if text:
                if children or d: d["_value"] = text
                else: return text
            return d

        data_dict = xml_to_dict(root)
        
        if "BODY" in data_dict and "IMPORTDATA" in data_dict["BODY"]:
            clean_data = data_dict["BODY"]["IMPORTDATA"]
        else:
            clean_data = data_dict

        return json.dumps(clean_data, ensure_ascii=False)

    except Exception as e:
        return f"Error connecting to Tally: {str(e)}"