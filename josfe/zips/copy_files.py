import os
import shutil
from pathlib import Path

# ==== CONFIGURATION ====
# Destination root where your new folder will be created
dest_root = "/home/erpnext_user/dev-bench/apps/josfe/josfe/zips"

# Name of the folder under zips/ where files will be copied
folder_name = "export3"   # 👈 change this as needed
dest_dir = os.path.join(dest_root, folder_name)

# ==== FILES AND FOLDERS TO COPY ====
files_to_copy = [
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing/xml/xades_template.py",
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing/doctype/sri_xml_queue/sri_xml_queue.py",
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing/core/numbering/state.py",
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing/core/numbering/serie_autoname.py",
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing/core/utils/common.py",
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing/core/validations/access_key.py",
    "/home/erpnext_user/dev-bench/apps/josfe/josfe/public/js/sri_invoicing/sales_invoice_series.js",

]

# folders_to_copy = [
#     "/home/erpnext_user/dev-bench/apps/josfe/josfe/sri_invoicing"
# ]

# ==== ENSURE DESTINATION EXISTS ====
os.makedirs(dest_dir, exist_ok=True)

# ==== COPY INDIVIDUAL FILES ====
for src in files_to_copy:
    if os.path.isfile(src):
        shutil.copy2(src, dest_dir)
        print(f"✅ Copied: {src} -> {dest_dir}")
    else:
        print(f"⚠️ Skipped (not found): {src}")

# ==== COPY FILES FROM FOLDERS (flattened, recursive) ====
for folder in folders_to_copy:
    folder_path = Path(folder)
    if folder_path.is_dir():
        for file in folder_path.rglob("*"):
            if file.is_file():
                try:
                    shutil.copy2(file, dest_dir)
                    print(f"📂 Copied: {file} -> {dest_dir}")
                except Exception as e:
                    print(f"❌ Failed: {file} ({e})")
    else:
        print(f"⚠️ Folder not found: {folder}")

print("\n🎉 Done! All files are in:", dest_dir)
