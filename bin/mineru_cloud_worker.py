import argparse
import os
import sys
import time
import zipfile
import io
import re
from datetime import datetime
import requests
import yaml

# Add bin/ directory to path for config_loader
_bin_dir = os.path.dirname(os.path.abspath(__file__))
if _bin_dir not in sys.path:
    sys.path.insert(0, _bin_dir)
from config_loader import load_config, get as cfg_get

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown using MinerU Cloud API.")
    parser.add_argument("input_path", help="Path to the .pdf file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for the raw Markdown file.")
    args = parser.parse_args()

    input_path = args.input_path
    output_dir = args.output_dir

    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' not found.")
        sys.exit(1)

    _cfg = load_config()
    api_token = cfg_get(_cfg, "ocr.mineru_api_token", "")
    if not api_token:
        print("Error: mineru_api_token not configured in config.yaml")
        sys.exit(1)

    # Unset proxy to avoid SSLEOFError
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

    base_name = os.path.basename(input_path)
    if base_name.lower().endswith('.pdf'):
        slug = base_name[:-4]
    else:
        slug = os.path.splitext(base_name)[0]

    # 1. Get upload URL
    url = "https://mineru.net/api/v4/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    data = {
        "files": [
            {"name": base_name, "data_id": slug}
        ],
        "model_version": "vlm"
    }

    print("Requesting MinerU upload URL...")
    res = requests.post(url, headers=headers, json=data)
    if res.status_code != 200 or res.json().get("code") != 0:
        print("Error getting upload URL:", res.text)
        sys.exit(1)

    result_data = res.json()["data"]
    batch_id = result_data["batch_id"]
    upload_url = result_data["file_urls"][0]

    print(f"Uploading {base_name}...")
    with open(input_path, "rb") as f:
        res_upload = requests.put(upload_url, data=f)
        if res_upload.status_code != 200:
            print("Upload failed:", res_upload.status_code)
            sys.exit(1)

    print("Upload complete. Waiting for extraction task to process (this may take a few minutes)...")
    
    # 2. Poll for result
    poll_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    poll_headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "*/*"
    }

    zip_url = None
    while True:
        time.sleep(10)
        res_poll = requests.get(poll_url, headers=poll_headers)
        if res_poll.status_code != 200:
            print("Poll error:", res_poll.status_code)
            continue
        poll_data = res_poll.json()
        if poll_data.get("code") != 0:
            print("Poll error code:", poll_data)
            continue
        
        extract_result = poll_data["data"]["extract_result"][0]
        state = extract_result["state"]
        print(f"Status: {state}...")
        if state == "done":
            zip_url = extract_result.get("full_zip_url")
            break
        elif state == "failed":
            print("MinerU Processing failed:", extract_result.get("err_msg"))
            sys.exit(1)

    if not zip_url:
        print("Error: Could not retrieve zip URL.")
        sys.exit(1)

    print("Downloading extraction results...")
    zip_res = requests.get(zip_url)
    if zip_res.status_code != 200:
        print("Failed to download zip:", zip_res.status_code)
        sys.exit(1)

    md_content = ""
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    print("Extracting files...")
    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as z:
        # Find markdown file
        md_filename = None
        for name in z.namelist():
            if name.endswith(".md"):
                md_filename = name
                break
        
        if not md_filename:
            print("Error: No markdown file found in result zip.")
            sys.exit(1)
            
        md_content = z.read(md_filename).decode('utf-8', errors='ignore')
        
        # First, find all referenced images in the markdown
        img_re = re.compile(r'!\[([^\]]*)\]\(([^)]+?)\)(\{[^}]*\})?')
        referenced_images = set()
        for m in img_re.finditer(md_content):
            target = m.group(2)
            basename = os.path.basename(target)
            if basename:
                referenced_images.add(basename)
                
        # Extract images and rewrite paths
        n_fig_ok = 0
        
        # We need a mapping from the original image path in markdown to the new filename
        image_mapping = {}
        for name in z.namelist():
            if "/images/" in name or name.startswith("images/"):
                basename = os.path.basename(name)
                if not basename:
                    continue
                if basename in referenced_images:
                    new_filename = f"{slug}-{basename}"
                    # Save to output_dir/images
                    out_path = os.path.join(images_dir, new_filename)
                    with open(out_path, "wb") as img_f:
                        img_f.write(z.read(name))
                    # Let's map basename to new_filename
                    image_mapping[basename] = new_filename
                    n_fig_ok += 1

        def repl(m):
            cap, target = m.group(1), m.group(2)
            tail = m.group(3) or ""
            basename = os.path.basename(target)
            if basename in image_mapping:
                return f'![{cap}](images/{image_mapping[basename]}){tail}'
            return m.group(0)

        md_content = img_re.sub(repl, md_content)
        print(f"Figures: {n_fig_ok} extracted and re-linked.")

    title = slug.replace('_', ' ').replace('-', ' ').title()
    doc_type = os.path.basename(os.path.normpath(output_dir))
    if doc_type not in ['papers', 'articles', 'notes', 'repos']:
        doc_type = 'papers'

    today = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"{today}-{slug}.md"
    output_path = os.path.join(output_dir, output_filename)

    frontmatter = f"""---
title: "{title}"
source: "{input_path}"
type: {doc_type}
ingested: {today}
tags: []
summary: "Converted from PDF via MinerU Cloud API."
---
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + "\n" + md_content)

    print(f"Successfully converted and saved to {output_path}")

if __name__ == "__main__":
    main()
