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

from magi.core.arxiv_id import abs_url, normalize_arxiv_id
from magi.core.config_loader import load_config, get as cfg_get
from magi.core.wiki_common import atomic_write
from urllib.parse import urlparse

from magi.ingest.convert_result import ConversionResult


#: The result is fetched after the work is done and billed, so a transient
#: network failure costs the whole job. Three tries, backing off.
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_BACKOFF_S = 5


def convert(input_path, output_dir) -> ConversionResult:
    """Convert a PDF to Markdown via the MinerU cloud API.

    Returns a result instead of calling sys.exit — there were twelve exit
    points in here, which meant a caller running this in-process could not
    learn whether it failed on a missing token, a timeout, or a bad zip.
    `main` keeps the old stdout and exit code exactly.
    """
    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' not found.")
        return ConversionResult.failed(f"File '{input_path}' not found.")

    _cfg = load_config()
    api_token = cfg_get(_cfg, "ocr.mineru_api_token", "")
    if not api_token:
        print("Error: mineru_api_token not configured in config.yaml")
        return ConversionResult.failed("mineru_api_token not configured in config.yaml")

    # There used to be two lines here popping `http_proxy` and `https_proxy`,
    # commented "unset proxy to avoid SSLEOFError". They never did anything:
    # the variables are conventionally spelled in UPPER CASE, which is what
    # this machine sets and what `requests` reads, and only the lower-case
    # names were removed. A workaround that has never once executed.
    #
    # It would also have been the wrong fix. The SSLEOFError is real, but it
    # comes from the *result host* being unreachable while the API host is
    # fine — measured: uploads and polling both succeed through the proxy and
    # only the CDN fails. Dropping the proxy would break the half that works,
    # and on a machine using fake-IP DNS there is no direct route to fall back
    # to. Mutating os.environ from inside a conversion would also silently
    # change how every other request in the process is routed.
    #
    # What helps is retrying the download and saying what actually happened;
    # see the end of this function.

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
    res = requests.post(url, headers=headers, json=data, timeout=(10, 60))
    try:
        body = res.json()
    except ValueError:
        print(f"Error: upload-URL response was not JSON (status {res.status_code}): {res.text}")
        return ConversionResult.failed(f"upload-URL response was not JSON (status {res.status_code})")
    if res.status_code != 200 or body.get("code") != 0:
        print("Error getting upload URL:", res.text)
        return ConversionResult.failed(f"getting upload URL failed: {res.text}")

    result_data = body.get("data") or {}
    batch_id = result_data.get("batch_id")
    file_urls = result_data.get("file_urls") or []
    if not batch_id or not file_urls:
        print(f"Error: unexpected upload-URL response shape: {body}")
        return ConversionResult.failed(f"unexpected upload-URL response shape: {body}")
    upload_url = file_urls[0]

    print(f"Uploading {base_name}...")
    with open(input_path, "rb") as f:
        res_upload = requests.put(upload_url, data=f, timeout=(10, 300))
        if res_upload.status_code != 200:
            print("Upload failed:", res_upload.status_code)
            return ConversionResult.failed(f"upload failed with status {res_upload.status_code}")

    print("Upload complete. Waiting for extraction task to process (this may take a few minutes)...")
    
    # 2. Poll for result
    poll_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    poll_headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "*/*"
    }

    zip_url = None
    POLL_DEADLINE_S = 30 * 60
    start = time.monotonic()
    while True:
        if time.monotonic() - start > POLL_DEADLINE_S:
            print("Error: MinerU extraction timed out after 30 minutes.", file=sys.stderr)
            return ConversionResult.failed("MinerU extraction timed out after 30 minutes.")
        time.sleep(10)
        res_poll = requests.get(poll_url, headers=poll_headers, timeout=(10, 60))
        if res_poll.status_code != 200:
            print("Poll error:", res_poll.status_code)
            continue
        try:
            poll_data = res_poll.json()
        except ValueError:
            print(f"Error: poll response was not JSON (status {res_poll.status_code}): {res_poll.text}")
            return ConversionResult.failed(f"poll response was not JSON (status {res_poll.status_code})")
        if poll_data.get("code") != 0:
            print("Poll error code:", poll_data)
            continue

        data = poll_data.get("data") or {}
        results = data.get("extract_result") or []
        if not results:
            continue
        extract_result = results[0]
        state = extract_result.get("state")
        if not state:
            continue
        print(f"Status: {state}...")
        if state == "done":
            zip_url = extract_result.get("full_zip_url")
            break
        elif state == "failed":
            print("MinerU Processing failed:", extract_result.get("err_msg"))
            return ConversionResult.failed(f"MinerU processing failed: {extract_result.get('err_msg')}")

    if not zip_url:
        print("Error: Could not retrieve zip URL.")
        return ConversionResult.failed("Could not retrieve zip URL.")

    # The conversion is finished and paid for by the time we get here — the
    # service has already done the work and charged the quota for it. Fetching
    # the result once and giving up cost a measured seven jobs in one round,
    # every one of them converted server-side and then lost to a host that
    # could not be reached. Retry, and if it still fails say plainly that the
    # extraction succeeded, so the reader looks at their network rather than at
    # the document.
    print("Downloading extraction results...")
    zip_res, last_error = None, ""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            zip_res = requests.get(zip_url, timeout=(10, 300))
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            zip_res = None
        else:
            if zip_res.status_code == 200:
                break
            last_error = f"HTTP {zip_res.status_code}"
            zip_res = None
        if attempt < DOWNLOAD_ATTEMPTS:
            wait = DOWNLOAD_BACKOFF_S * attempt
            print(f"  download attempt {attempt}/{DOWNLOAD_ATTEMPTS} failed "
                  f"({last_error}); retrying in {wait}s")
            time.sleep(wait)

    if zip_res is None:
        host = urlparse(zip_url).hostname or "the result host"
        detail = (f"the extraction SUCCEEDED and the quota for it is already spent, "
                  f"but the result could not be downloaded from {host} after "
                  f"{DOWNLOAD_ATTEMPTS} attempts ({last_error}). This is a network "
                  f"problem between this machine and {host}, not a problem with the "
                  f"document — check a proxy or firewall rule for that host.")
        print("Failed to download zip:", detail, file=sys.stderr)
        return ConversionResult.failed(detail)

    md_content = ""
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    print("Extracting files...")
    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as z:
        # Find markdown file — prefer full.md, then largest .md by size
        md_names = [n for n in z.namelist() if n.endswith('.md')]
        md_filename = (
            next((n for n in md_names if os.path.basename(n) == 'full.md'), None)
            or next((n for n in md_names if n.endswith('full.md')), None)
            or (max(md_names, key=lambda n: z.getinfo(n).file_size) if md_names else None)
        )

        if not md_filename:
            print("Error: No markdown file found in result zip.")
            return ConversionResult.failed("No markdown file found in result zip.")
            
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

    fm_dict = {
        "title": title,
        "source": input_path,
        "type": doc_type,
        "ingested": today,
        "tags": [],
        "summary": "Converted from PDF via MinerU Cloud API.",
    }
    # The tex and OCR routes both recover the arXiv id from the filename; this
    # one did not, so a paper ingested through MinerU stayed invisible to the
    # radar's library fingerprint and kept being re-surfaced as a candidate.
    found_id = normalize_arxiv_id(base_name)
    if found_id:
        fm_dict["arxiv_id"] = found_id
        fm_dict["arxiv_url"] = abs_url(found_id)
    frontmatter = "---\n" + yaml.safe_dump(fm_dict, allow_unicode=True, sort_keys=False, default_flow_style=False) + "---\n"

    atomic_write(output_path, frontmatter + "\n" + md_content, encoding='utf-8')

    print(f"Successfully converted and saved to {output_path}")
    return ConversionResult(
        success=True,
        markdown_path=str(output_path),
        images_dir=os.path.join(output_dir, "images"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi ingest mineru", description="Convert PDF to Markdown using MinerU Cloud API.")
    parser.add_argument("input_path", help="Path to the .pdf file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for the raw Markdown file.")
    args = parser.parse_args(argv)

    result = convert(args.input_path, args.output_dir)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
