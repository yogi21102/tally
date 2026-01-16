#tools/table_generator.py
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Force headless mode
import matplotlib.pyplot as plt
import os
import json
import uuid

# --- CONFIGURATION ---
PLOT_DIR = "generated_plots"
os.makedirs(PLOT_DIR, exist_ok=True)

class TableGenerator:
    """
    Generates professional tables. 
    Hybrid Logic:
    1. Tries to parse as specific Tally Vouchers (Day Book).
    2. Falls back to generic XML flattening (Stock Summary, Balance Sheet).
    """

    # Mapping Tally's internal XML tags to Human Readable Headers
    TALLY_MAP = {
        "DSPDISPNAME": "Item Name",
        "NAME": "Name",
        "DSPCLQTY": "Quantity",
        "DSPCLRATE": "Rate",
        "DSPCLAMTA": "Amount",
        "DSPSTKCL": "Closing Balance",
        "BSMAINAMT": "Amount",
        "PLAMT": "Amount",
        "CAMT": "Credit",
        "DAMT": "Debit",
    }

    def _parse_tally_vouchers(self, data):
        """Specialized Parser for Day Book / Vouchers."""
        rows = []
        messages = []
        try:
            if isinstance(data, list): messages = data
            elif "TALLYMESSAGE" in data: messages = data["TALLYMESSAGE"]
            elif "REQUESTDATA" in data and "TALLYMESSAGE" in data["REQUESTDATA"]:
                messages = data["REQUESTDATA"]["TALLYMESSAGE"]
        except: pass

        if isinstance(messages, dict): messages = [messages]
        if not messages: return None

        for msg in messages:
            v = msg.get("VOUCHER", {})
            if not v: continue
            
            # Extract Date
            raw_date = v.get("DATE", "")
            fmt_date = f"{raw_date[6:8]}-{raw_date[4:6]}-{raw_date[0:4]}" if len(raw_date) == 8 else raw_date

            # Extract Particulars
            particulars = v.get("PARTYNAME") or v.get("PARTYLEDGERNAME") or "Unknown"
            if isinstance(particulars, dict): particulars = particulars.get("_value", "")

            # Calculate Amount
            amount = 0.0
            inv_list = v.get("ALLINVENTORYENTRIES.LIST", [])
            if isinstance(inv_list, dict): inv_list = [inv_list]
            
            led_list = v.get("ALLLEDGERENTRIES.LIST", [])
            if isinstance(led_list, dict): led_list = [led_list]
            
            if inv_list:
                for item in inv_list:
                    try: amount += abs(float(str(item.get("AMOUNT", 0)).replace(",", "")))
                    except: pass
            elif led_list:
                for item in led_list:
                    try: 
                        val = abs(float(str(item.get("AMOUNT", 0)).replace(",", "")))
                        if val > 0: 
                            amount += val
                            break 
                    except: pass

            rows.append({
                "Date": fmt_date,
                "Particulars": particulars,
                "Vch Type": v.get("VOUCHERTYPENAME", ""),
                "Vch No": v.get("VOUCHERNUMBER", ""),
                "Amount": f"{amount:,.2f}"
            })
        
        return rows if rows else None

    # --- GENERIC PARSING (Restored) ---
    def _merge_parallel_lists(self, data):
        if not isinstance(data, dict): return []
        list_keys = [k for k, v in data.items() if isinstance(v, list) and len(v) > 0]
        if not list_keys: return []

        by_length = {}
        for k in list_keys:
            l = len(data[k])
            if l not in by_length: by_length[l] = []
            by_length[l].append(k)
        
        if not by_length: return []
        max_len = max(by_length.keys())
        target_keys = by_length[max_len] 

        if len(target_keys) == 1: return data[target_keys[0]]

        merged_list = []
        for i in range(max_len):
            merged_row = {}
            for k in target_keys:
                item = data[k][i]
                if isinstance(item, dict): merged_row.update(item)
                else: merged_row[k] = item
            merged_list.append(merged_row)
        return merged_list

    def _find_longest_list(self, data):
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict): return data
            candidates = []
            for item in data:
                res = self._find_longest_list(item)
                if res: candidates.append(res)
            return max(candidates, key=len) if candidates else []
            
        elif isinstance(data, dict):
            merged = self._merge_parallel_lists(data)
            if merged and len(merged) > 1: return merged
            candidates = []
            for key, value in data.items():
                res = self._find_longest_list(value)
                if res: candidates.append(res)
            return max(candidates, key=len) if candidates else []
        return []

    def _flatten_row(self, nested_dict):
        out = {}
        def flatten(x, name=''):
            if type(x) is dict:
                for a in x: flatten(x[a], name + a + '_')
            else:
                clean_key = name[:-1]
                final_key = clean_key
                for tag, readable in self.TALLY_MAP.items():
                    if tag in clean_key: 
                        final_key = readable
                        break
                if final_key in out: final_key = f"{final_key} ({clean_key[-4:]})" 
                out[final_key] = x
        flatten(nested_dict)
        return out

    def generate_table(self, json_path, query="Show data"):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # STRATEGY 1: Try Tally Voucher Parsing (Day Book)
            main_list = self._parse_tally_vouchers(data)
            
            # STRATEGY 2: Fallback to Generic Parsing (Stock Summary, P&L)
            if not main_list:
                main_list = self._merge_parallel_lists(data)
            
            # STRATEGY 3: Deep Search
            if not main_list or len(main_list) < 1:
                main_list = self._find_longest_list(data)

            if not main_list:
                 # Last Resort: Treat root as single row
                if isinstance(data, dict): main_list = [data]
                else: return json.dumps({"status": "error", "message": "No tabular data found."})

            # Flatten rows if they came from generic parser
            if main_list and isinstance(main_list[0], dict) and "Date" not in main_list[0]:
                rows = [self._flatten_row(item) for item in main_list]
            else:
                rows = main_list

            df = pd.DataFrame(rows)
            if df.empty: return json.dumps({"status": "error", "message": "Dataframe is empty."})

            # Filter Cols for Generic Data
            if "Vch No" not in df.columns:
                desired_cols = []
                for col in df.columns:
                    if col in self.TALLY_MAP.values(): desired_cols.append(col)
                    elif any(x in col for x in ["Name", "Amount", "Qty", "Rate", "Total", "Particulars"]):
                        desired_cols.append(col)
                if desired_cols:
                    # Sort so Name is first
                    final_cols = sorted(list(set(desired_cols)), key=lambda x: 0 if "Name" in x or "Particular" in x else 1)
                    df_display = df[final_cols].head(25)
                else:
                    df_display = df.head(25)
            else:
                df_display = df.head(25)

            # Plotting
            row_height = 0.5
            header_height = 0.8
            fig_height = (len(df_display) * row_height) + header_height + 1
            
            fig, ax = plt.subplots(figsize=(12, max(fig_height, 3))) 
            ax.axis('tight')
            ax.axis('off')
            
            table = ax.table(
                cellText=df_display.values,
                colLabels=df_display.columns,
                cellLoc='left',
                loc='center',
                colColours=['#f8f9fa']*len(df_display.columns)
            )

            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 1.5)

            # Styling
            for (row, col), cell in table.get_celld().items():
                cell.set_edgecolor("#dddddd")
                cell.set_linewidth(0.5)
                if row == 0:
                    cell.get_text().set_color('#333333')
                    cell.get_text().set_weight('bold')
                    cell.set_facecolor('#e9ecef')
                elif row > 0:
                     if row % 2 == 0: cell.set_facecolor('#ffffff')
                     else: cell.set_facecolor('#fdfdfd')

            # Save
            filename = f"table_{uuid.uuid4().hex[:8]}.png"
            save_path = os.path.join(PLOT_DIR, filename)
            abs_path = os.path.abspath(save_path).replace("\\", "/") 
            
            plt.title(f"{query}", fontsize=12, color="#444444", pad=20)
            plt.savefig(abs_path, bbox_inches='tight', dpi=150, pad_inches=0.2)
            plt.close()

            return json.dumps({
                "status": "success",
                "images": [save_path], 
                "rationale": f"Generated table with {len(df_display)} rows."
            })

        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})