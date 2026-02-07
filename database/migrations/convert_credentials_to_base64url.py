#!/usr/bin/env python3
"""
Convert existing credential_id from base64 to base64url format
"""
from backend.database import engine
from sqlalchemy import text

def base64_to_base64url(b64_string: str) -> str:
    """Convert standard base64 to base64url"""
    return b64_string.replace('+', '-').replace('/', '_').replace('=', '')

with engine.connect() as conn:
    # Get all credentials
    result = conn.execute(text("SELECT id, credential_id FROM webauthn_credentials"))
    credentials = result.fetchall()

    print(f"Found {len(credentials)} credentials to convert")

    for cred_id, credential_id in credentials:
        # Convert to base64url
        new_credential_id = base64_to_base64url(credential_id)

        if new_credential_id != credential_id:
            print(f"Converting credential {cred_id}: {credential_id[:20]}... -> {new_credential_id[:20]}...")
            conn.execute(
                text("UPDATE webauthn_credentials SET credential_id = :new_id WHERE id = :id"),
                {"new_id": new_credential_id, "id": cred_id}
            )

    conn.commit()
    print("Conversion complete!")
