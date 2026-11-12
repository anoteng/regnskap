"""Moves a release that is already on Play's internal track to production.

Nothing is built or uploaded: Play refuses a version code it has seen before,
so the bundle that was tested internally is the one that goes out.

Environment:
  SERVICE_ACCOUNT_JSON  the service account key, as JSON text
  PACKAGE_NAME          e.g. eu.privatregnskap.app
  VERSION_CODE          optional; defaults to the newest on the internal track
  DRY_RUN               "true" validates the edit and throws it away
  WHATS_NEW_DIR         one file per language, named after it (nb-NO.txt);
                        what Play shows as "What's new". Required.
"""
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"


def call(session, method, url, **kwargs):
    response = session.request(method, url, **kwargs)
    if not response.ok:
        sys.exit(f"{method} {url} -> {response.status_code}\n{response.text}")
    return response.json() if response.content else {}


def release_notes(directory):
    notes = []
    for path in sorted(Path(directory).glob("*.txt")):
        text = path.read_text(encoding="utf-8").strip()
        if len(text) > 500:
            sys.exit(f"{path}: {len(text)} characters, Play allows 500")
        if text:
            notes.append({"language": path.stem, "text": text})
    if not notes:
        sys.exit(f"No release notes in {directory}: production does not go out without them")
    return notes


def main():
    notes = release_notes(os.environ["WHATS_NEW_DIR"])

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["SERVICE_ACCOUNT_JSON"]), scopes=[SCOPE]
    )
    session = AuthorizedSession(credentials)
    base = f"{API}/{os.environ['PACKAGE_NAME']}"
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    edit_id = call(session, "POST", f"{base}/edits")["id"]
    edit = f"{base}/edits/{edit_id}"

    current = call(session, "GET", f"{edit}/tracks/production").get("releases", [])
    for live in current:
        print(f"Now in production: {live.get('name', '?')} ({', '.join(live.get('versionCodes', []))}), {live.get('status')}")

    internal = call(session, "GET", f"{edit}/tracks/internal")
    candidates = [
        release
        for release in internal.get("releases", [])
        if release.get("status") == "completed" and release.get("versionCodes")
    ]
    wanted = os.environ.get("VERSION_CODE", "").strip()
    if wanted:
        candidates = [r for r in candidates if wanted in r["versionCodes"]]
    if not candidates:
        sys.exit(f"No completed release on the internal track{' with version code ' + wanted if wanted else ''}")
    release = max(candidates, key=lambda r: max(int(code) for code in r["versionCodes"]))

    production = {
        "track": "production",
        "releases": [{
            key: release[key]
            for key in ("name", "versionCodes")
            if key in release
        } | {"status": "completed", "releaseNotes": notes}],
    }
    call(session, "PUT", f"{edit}/tracks/production", json=production)
    print(f"Release {release.get('name', '?')} (version codes {', '.join(release['versionCodes'])}) -> production")
    for note in notes:
        print(f"--- What's new ({note['language']}) ---\n{note['text']}")

    if dry_run:
        call(session, "POST", f"{edit}:validate")
        call(session, "DELETE", edit)
        print("Dry run: the edit validated and was discarded. Nothing was published.")
    else:
        call(session, "POST", f"{edit}:commit")
        print("Committed. Play may still hold it for review before it reaches users.")


if __name__ == "__main__":
    main()
