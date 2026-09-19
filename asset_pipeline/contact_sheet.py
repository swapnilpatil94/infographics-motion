"""Generates an asset contact sheet FROM THE REGISTRY — every row is read
from assets/licenses/registry.json, never hand-typed, so the sheet can't
drift from what's actually registered.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(ROOT, "assets/licenses/registry.json")
OUT_PATH = os.path.join(ROOT, "output/previews/asset_contact_sheet.html")


def generate():
    with open(REGISTRY_PATH) as f:
        data = json.load(f)
    assets = sorted(data["assets"], key=lambda a: (a["asset_type"], a["id"]))

    rows = []
    for a in assets:
        status_color = "#2e7d32" if a["status"] == "REGISTERED" else "#c62828"
        rows.append(f"""
        <tr>
          <td>{a['id']}</td>
          <td>{a['asset_type']}</td>
          <td>{a['source']}</td>
          <td>{a['license']}</td>
          <td>{'yes' if a.get('riggable') else 'no'}</td>
          <td style="color:{status_color};font-weight:bold">{a['status']}</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Asset Contact Sheet</title>
<style>
body {{ font-family: -apple-system, sans-serif; background: #f4f2ee; padding: 24px; }}
h1 {{ font-size: 20px; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 13px; }}
th {{ background: #222; color: white; }}
tr:nth-child(even) {{ background: #fafafa; }}
.summary {{ margin-bottom: 12px; color: #555; }}
</style></head>
<body>
<h1>Asset Contact Sheet</h1>
<div class="summary">{len(assets)} assets registered — {sum(1 for a in assets if a['status']=='REGISTERED')} REGISTERED, {sum(1 for a in assets if a['status']=='QUARANTINED')} QUARANTINED. Generated from assets/licenses/registry.json.</div>
<table>
<tr><th>Asset ID</th><th>Type</th><th>Source</th><th>License</th><th>Riggable</th><th>Status</th></tr>
{"".join(rows)}
</table>
</body></html>"""

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    generate()
