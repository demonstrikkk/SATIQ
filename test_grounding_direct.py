import sys
from pathlib import Path
REPO_ROOT = Path(r"C:\Users\aarav\Downloads\SATIQ")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
for p in [r"C:\coding\sih\model2_grounding", r"C:\coding\sih\model2_grounding\gdino_src", r"C:\coding\sih\model3_change_vqa"]:
    if p not in sys.path:
        sys.path.insert(0, p)

from capabilities.single_image.grounding import grounding_tool

patch = r"C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_43_57"
print(f"Testing grounding_tool with patch {patch}")
print(f"Patch exists: {Path(patch).exists()}")
print(f"Files: {list(Path(patch).glob('*B04*'))[:1]}")

# Test with query that will be real
for query in ["Provide the bounding box for the forest patch", "Ground the forest area", "Provide bbox for water body"]:
    print(f"\n--- Query: {query} ---")
    out = grounding_tool(patch, query, conf_threshold=0.35)
    print(f"Status: {out['status']}")
    if out['status'] == 'success':
        print(f"Text: {out['text'][:300]}")
        print(f"Confidence: {out['confidence']}")
        print(f"Artifacts: {out['artifacts']}")
        print(f"Metadata boxes: {len(out['metadata'].get('boxes', [])) if out.get('metadata') else 0}")
        if out.get('metadata', {}).get('scores'):
            print(f"Top score: {max(out['metadata']['scores']):.3f}")
    else:
        print(f"Error: {out['error_code']} - {out['message'][:500]}")
