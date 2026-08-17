import argparse
import os
import re
import sys

def verify_claims(filepath, topic_dir):
    if not os.path.isfile(filepath):
        print(f"Error: claims file not found: {filepath}", file=sys.stderr)
        sys.exit(2)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().replace('\r\n', '\n')

    # Parse blocks of claims
    blocks = re.split(r'\n(?=CLAIM:)', content.strip())
    
    verified_count = 0
    unverified_count = 0

    print("=== Verification Report ===")
    for block in blocks:
        if not block.strip(): continue
        
        claim_match = re.search(r'CLAIM:\s*(.*)', block, re.IGNORECASE)
        evidence_match = re.search(r'^EVIDENCE:\s*(.*?)(?=\n^(?:CLAIM|SOURCE_TYPE|SOURCE|CONTRADICTS_SOURCE|SEVERITY|FINDING):|\Z)', block, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        source_type_match = re.search(r'SOURCE_TYPE:\s*(.*)', block, re.IGNORECASE)
        source_match = re.search(r'SOURCE:\s*(.*)', block, re.IGNORECASE)
        
        if not (claim_match and evidence_match and source_type_match and source_match):
            print(f"[UNVERIFIED - Malformed Block]\n{block}\n")
            unverified_count += 1
            continue
            
        claim = claim_match.group(1).strip()
        evidence = evidence_match.group(1).strip()
        if evidence.startswith('"') and evidence.endswith('"'):
            evidence = evidence[1:-1]
        source_type = source_type_match.group(1).strip().lower()
        source = source_match.group(1).strip()
        
        is_valid = False
        reason = ""
        
        if source_type == "local_wiki":
            abs_path = source
            if not os.path.isabs(abs_path):
                abs_path = os.path.join(topic_dir, source)

            # Path traversal protection: verify the resolved path is within topic_dir
            real_path = os.path.normcase(os.path.realpath(abs_path))
            real_topic_dir = os.path.normcase(os.path.realpath(topic_dir))
            if not real_path.startswith(real_topic_dir + os.sep) and real_path != real_topic_dir:
                reason = f"Path traversal detected: {abs_path} resolves outside {topic_dir}"
                print(f"Warning: {reason}", file=sys.stderr)
                is_valid = False
                # Skip the rest of processing for this entry
            elif not os.path.exists(real_path):
                reason = f"File not found: {abs_path}"
            else:
                with open(abs_path, "r", encoding="utf-8") as sf:
                    file_content = sf.read().replace('\r\n', '\n')
                    if evidence in file_content:
                        is_valid = True
                    else:
                        reason = f"Evidence string not exactly found in file."
        elif source_type == "web":
            if source.startswith("http://") or source.startswith("https://"):
                # Only validates URL format, not content — honest label
                print(f"[URL-FORMAT-OK] {claim}")
                print(f"  Source: {source}")
                verified_count += 1
                continue
            else:
                reason = f"Invalid URL format: {source}"
        else:
            reason = f"Unknown SOURCE_TYPE: {source_type}"
            
        if is_valid:
            print(f"[VERIFIED] {claim}")
            print(f"  Source: {source}")
            verified_count += 1
        else:
            print(f"[UNVERIFIED - {reason}] {claim}")
            print(f"  Evidence: {evidence}")
            unverified_count += 1
            
    print(f"\nTotal Verified: {verified_count}")
    print(f"Total Unverified: {unverified_count}")
    return unverified_count

def main():
    parser = argparse.ArgumentParser(description="Verify claims extracted by Subagents")
    parser.add_argument("claims_file", help="Path to text file containing claims")
    parser.add_argument("--topic-dir", required=True, help="Topic workspace directory")
    args = parser.parse_args()
    
    failures = verify_claims(args.claims_file, args.topic_dir)
    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
