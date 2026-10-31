"""Remote, metadata-only inventory of book repositories (no file content downloaded): resolve each default branch's
current COMMIT, fetch its recursive tree, count formats, deduplicate exact Git blobs across repositories and list
candidate titles. Writes data/books/remote/<owner>__<repo>.tree.json (private cache) and
config/book_candidates/remote_inventory_20261031.json (public bibliographic metadata).
usage: .venv/bin/python validation/remote_inventory.py"""
import collections, json, os, posixpath, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REPOS = ["chenggaw/mingchaonaxieshier", "HarborLibrary/Chinese-History", "HarborLibrary/Europe-History", "HarborLibrary/History-General",
         "HarborLibrary/Social-Sciences", "HarborLibrary/Military-Science", "HarborLibrary/America-History", "HarborLibrary/Asia-History",
         "HarborLibrary/Commerce", "HarborLibrary/Political-Science", "gh73962/shiji_md", "sdlyyxy/Chinese-Modern-Contemporary-History-Anthology"]
BOOK = {"pdf", "epub", "txt", "md", "mobi", "azw3", "chm", "djvu", "zip", "rar", "doc", "docx", "html"}
SUPPORTED = {"epub": "epub", "txt": "txt", "md": "markdown", "pdf": "text-pdf (scans -> needs_ocr)"}


def gh(path):
    return json.loads(subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout)


out, blobs = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "note": "metadata only; files are leads until acquired, verified and parsed", "repos": []}, collections.defaultdict(list)
for r in REPOS:
    meta = gh(f"repos/{r}"); br = meta["default_branch"]; commit = gh(f"repos/{r}/commits/{br}")["sha"]
    tree = gh(f"repos/{r}/git/trees/{commit}?recursive=1")
    (ROOT / "data/books/remote" / f"{r.replace('/', '__')}.tree.json").write_text(json.dumps(tree, ensure_ascii=False))
    files = [x for x in tree["tree"] if x["type"] == "blob"]
    ext = collections.Counter(posixpath.splitext(x["path"])[1].lower().lstrip(".") for x in files)
    books = [x for x in files if posixpath.splitext(x["path"])[1].lower().lstrip(".") in BOOK]
    for x in books:
        blobs[x["sha"]].append(f"{r}:{x['path']}")
    out["repos"].append({"repo": r, "url": f"https://github.com/{r}", "default_branch": br, "commit": commit, "tree_truncated": tree["truncated"],
                         "licence": (meta.get("license") or {}).get("spdx_id"), "blobs": len(files), "book_like_files": len(books),
                         "bytes_book_like": sum(x["size"] for x in books), "extensions": dict(ext.most_common())})
    print(f"{r:62} {br:7} {commit[:10]} files={len(files):4} book={len(books):4} {sum(x['size'] for x in books)/1e9:5.2f} GB trunc={tree['truncated']}")
dups = {k: v for k, v in blobs.items() if len(v) > 1}
out["exact_duplicate_blobs"] = {"count": len(dups), "examples": list(dups.values())[:15]}
out["unique_book_like_blobs"] = len(blobs)
(ROOT / "config/book_candidates/remote_inventory_20261031.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("unique book-like blobs", len(blobs), "exact duplicate groups", len(dups))
