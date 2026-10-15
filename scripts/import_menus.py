"""Preview/import a reviewed menu JSON through the scoped bearer-key API.

python scripts/import_menus.py data/menus/kfc_sg_reference_20261004.json
Add --apply to import after the server validates and previews the same payload.
The key is read from the private --env file, never from a CLI argument or browser.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from run_demo import load_env, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--env", type=Path, default=ROOT / ".env.demo")
    parser.add_argument("--url", default="http://127.0.0.1:5055")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    load_env(args.env)
    key = os.environ.get("MENU_IMPORT_API_KEY", "")
    if len(key) < 32:
        raise SystemExit("Configure MENU_IMPORT_API_KEY in the private environment and restart the web app first.")
    parsed = urlsplit(args.url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
            or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})):
        raise SystemExit("Use your application origin: HTTPS, or HTTP on loopback only.")

    def api(path, data=None):
        encoded = json.dumps(data).encode() if data is not None else None
        req = Request(args.url.rstrip("/") + "/api/integrations/" + path, data=encoded,
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        # Do not forward the credential to a redirect destination.
        from urllib.request import build_opener, HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with build_opener(NoRedirect).open(req, timeout=45) as response:
                return json.load(response)
        except HTTPError as error:
            try:
                message = json.load(error).get("error", "Import request failed.")
            except (ValueError, AttributeError):
                message = "Import request failed. Check the application URL and status."
            raise SystemExit(f"HTTP {error.code}: {message}") from None

    menu = json.loads(args.file.read_text(encoding="utf-8"))
    names = menu.pop("matchNames", None)
    if names:
        if not menu.get("isReference") or menu.get("places"):
            raise SystemExit("matchNames is only for explicitly labelled shared reference menus without a places list.")
        menu["places"] = []
        for name in names:
            matches = api("menu-targets?" + urlencode({"name": name}))["places"]
            menu["places"].extend({k: p[k] for k in ("id", "name", "sourceId")} for p in matches)
    if not menu.get("places"):
        raise SystemExit("No matching establishments; no data imported.")
    preview = api("menu-imports", {"menu": menu})
    print(json.dumps({k: preview[k] for k in ("added", "skipped", "conflicts", "places")}, indent=2))
    if args.apply:
        result = api("menu-imports", {"menu": preview["menu"], "apply": True, "previewToken": preview["previewToken"]})
        print(json.dumps({k: result[k] for k in ("added", "skipped", "applied")}))
    else:
        print("Preview only. Add --apply after reviewing the source and target establishments.")


if __name__ == "__main__":
    main()
