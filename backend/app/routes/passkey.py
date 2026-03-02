import base64
import json
import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from backend.database import get_db
from backend.config import get_settings
from ..models import User, WebAuthnCredential
from ..schemas import (
    WebAuthnRegistrationStart,
    WebAuthnRegistrationComplete,
    WebAuthnLoginStart,
    WebAuthnLoginComplete,
    WebAuthnCredential as WebAuthnCredentialSchema,
    Token,
)
from ..auth import get_current_user, create_access_token

router = APIRouter(prefix="/auth/passkey", tags=["passkey"])
settings = get_settings()

# Temporary in-memory storage for challenges
# In production, use Redis or similar
challenges_store = {}


def base64_to_base64url(b64_string: str) -> str:
    """Convert standard base64 to base64url"""
    return b64_string.replace('+', '-').replace('/', '_').replace('=', '')


def base64url_to_base64(b64url_string: str) -> str:
    """Convert base64url to standard base64"""
    # Add padding if needed
    padding = 4 - (len(b64url_string) % 4)
    if padding and padding != 4:
        b64url_string += '=' * padding
    return b64url_string.replace('-', '+').replace('_', '/')


def get_rp_id() -> str:
    """Get Relying Party ID from settings or default"""
    # For development: localhost, for production: your domain
    return getattr(settings, 'rp_id', 'localhost')


def get_rp_name() -> str:
    """Get Relying Party name"""
    return getattr(settings, 'rp_name', 'Regnskap')


def get_origin() -> str:
    """Get expected origin for WebAuthn"""
    # For development
    rp_id = get_rp_id()
    if rp_id == 'localhost':
        return 'http://localhost:8002'
    return f'https://{rp_id}'


@router.post("/register/begin")
async def begin_registration(
    request: WebAuthnRegistrationStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start passkey registration for authenticated user.
    Returns registration options for navigator.credentials.create()
    """
    # Get user's existing credentials to exclude
    existing_credentials = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == current_user.id
    ).all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=base64.b64decode(cred.credential_id))
        for cred in existing_credentials
    ]

    # Generate registration options
    registration_options = generate_registration_options(
        rp_id=get_rp_id(),
        rp_name=get_rp_name(),
        user_id=str(current_user.id).encode('utf-8'),
        user_name=current_user.email,
        user_display_name=current_user.full_name,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    # Store challenge for verification
    challenge_key = f"reg_{current_user.id}_{secrets.token_urlsafe(16)}"
    challenges_store[challenge_key] = {
        'challenge': registration_options.challenge,
        'user_id': current_user.id,
        'credential_name': request.credential_name,
    }

    # Convert to JSON-serializable format
    options_json_str = options_to_json(registration_options)
    options_dict = json.loads(options_json_str)

    # Add challenge key to response so client can send it back
    options_dict['challenge_key'] = challenge_key

    return options_dict


@router.post("/register/complete")
async def complete_registration(
    request: WebAuthnRegistrationComplete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete passkey registration.
    Verifies attestation and stores the credential.
    """
    attestation = request.attestation
    challenge_key = attestation.get('challenge_key')

    if not challenge_key or challenge_key not in challenges_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired challenge"
        )

    challenge_data = challenges_store.pop(challenge_key)
    expected_challenge = challenge_data['challenge']

    try:
        # Verify the attestation response
        verification = verify_registration_response(
            credential=attestation,
            expected_challenge=expected_challenge,
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
        )

        # Store the credential (use base64url format to match frontend)
        credential_id_b64 = base64.b64encode(verification.credential_id).decode('utf-8')
        credential_id_b64url = base64_to_base64url(credential_id_b64)
        public_key_b64 = base64.b64encode(verification.credential_public_key).decode('utf-8')

        new_credential = WebAuthnCredential(
            user_id=current_user.id,
            credential_id=credential_id_b64url,
            public_key=public_key_b64,
            sign_count=verification.sign_count,
            credential_name=request.credential_name or challenge_data.get('credential_name'),
            aaguid=str(verification.aaguid) if verification.aaguid else None,
        )

        db.add(new_credential)
        db.commit()
        db.refresh(new_credential)

        return {
            'success': True,
            'credential': WebAuthnCredentialSchema.model_validate(new_credential)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration verification failed: {str(e)}"
        )


@router.post("/login/begin")
async def begin_login(
    request: WebAuthnLoginStart,
    db: Session = Depends(get_db)
):
    """
    Start passkey authentication.
    Returns authentication options for navigator.credentials.get()
    """
    # If email provided, get credentials for that user
    # Otherwise, allow any registered credential (discoverable credentials)
    allow_credentials = []
    user_id = None

    if request.email:
        user = db.query(User).filter(User.email == request.email).first()
        if user:
            user_id = user.id
            credentials = db.query(WebAuthnCredential).filter(
                WebAuthnCredential.user_id == user.id
            ).all()

            allow_credentials = [
                PublicKeyCredentialDescriptor(id=base64.b64decode(cred.credential_id))
                for cred in credentials
            ]

    # Generate authentication options
    authentication_options = generate_authentication_options(
        rp_id=get_rp_id(),
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Store challenge
    challenge_key = f"auth_{secrets.token_urlsafe(16)}"
    challenges_store[challenge_key] = {
        'challenge': authentication_options.challenge,
        'user_id': user_id,
    }

    options_json_str = options_to_json(authentication_options)
    options_dict = json.loads(options_json_str)

    options_dict['challenge_key'] = challenge_key

    return options_dict


@router.post("/login/complete", response_model=Token)
async def complete_login(
    request: WebAuthnLoginComplete,
    db: Session = Depends(get_db)
):
    """
    Complete passkey authentication.
    Verifies assertion and returns JWT token.
    """
    assertion = request.assertion
    challenge_key = assertion.get('challenge_key')

    if not challenge_key or challenge_key not in challenges_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired challenge"
        )

    challenge_data = challenges_store.pop(challenge_key)
    expected_challenge = challenge_data['challenge']

    # Look up credential
    # assertion['rawId'] is already a base64url string from frontend
    credential_id_b64url = assertion['rawId']

    credential = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.credential_id == credential_id_b64url
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credential not found"
        )

    try:
        # Verify the assertion
        public_key_bytes = base64.b64decode(credential.public_key)

        verification = verify_authentication_response(
            credential=assertion,
            expected_challenge=expected_challenge,
            expected_origin=get_origin(),
            expected_rp_id=get_rp_id(),
            credential_public_key=public_key_bytes,
            credential_current_sign_count=credential.sign_count,
        )

        # Update sign count and last used
        credential.sign_count = verification.new_sign_count
        credential.last_used_at = datetime.utcnow()
        db.commit()

        # Get user
        user = db.query(User).filter(User.id == credential.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Create access token with configured expiration
        from datetime import timedelta
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )

        return {
            'access_token': access_token,
            'token_type': 'bearer'
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/credentials", response_model=list[WebAuthnCredentialSchema])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all passkeys for the current user"""
    credentials = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == current_user.id
    ).all()

    return credentials


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a passkey"""
    credential = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.id == credential_id,
        WebAuthnCredential.user_id == current_user.id
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    db.delete(credential)
    db.commit()

    return {'success': True}


@router.patch("/credentials/{credential_id}/rename")
async def rename_credential(
    credential_id: int,
    new_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rename a passkey"""
    credential = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.id == credential_id,
        WebAuthnCredential.user_id == current_user.id
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    credential.credential_name = new_name
    db.commit()

    return WebAuthnCredentialSchema.model_validate(credential)
