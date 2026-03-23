import requests
from backend.config import get_settings

settings = get_settings()


def send_password_reset_email(to_email: str, reset_token: str, user_name: str):
    """Send password reset email with token link"""

    reset_link = f"https://{settings.rp_id}/reset-password?token={reset_token}"

    text = f"""
Hei {user_name},

Du har bedt om å tilbakestille passordet ditt for Privatregnskap.eu.

Klikk på lenken nedenfor for å tilbakestille passordet:
{reset_link}

Lenken er gyldig i 1 time.

Hvis du ikke ba om dette, kan du ignorere denne e-posten.

Hilsen
Privatregnskap.eu
"""

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2>Tilbakestill passord</h2>
    <p>Hei {user_name},</p>
    <p>Du har bedt om å tilbakestille passordet ditt for Privatregnskap.eu.</p>
    <p>Klikk på knappen nedenfor for å tilbakestille passordet:</p>
    <p style="margin: 30px 0;">
      <a href="{reset_link}"
         style="background-color: #4CAF50; color: white; padding: 12px 24px;
                text-decoration: none; border-radius: 4px; display: inline-block;">
        Tilbakestill passord
      </a>
    </p>
    <p>Eller kopier og lim inn denne lenken i nettleseren:</p>
    <p style="color: #666; font-size: 0.9em;">{reset_link}</p>
    <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
      Lenken er gyldig i 1 time.<br>
      Hvis du ikke ba om dette, kan du ignorere denne e-posten.
    </p>
    <hr style="margin-top: 30px; border: none; border-top: 1px solid #ddd;">
    <p style="color: #999; font-size: 0.8em;">Hilsen Privatregnskap.eu</p>
  </body>
</html>
"""

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": settings.brevo_api_key,
            "Content-Type": "application/json",
        },
        json={
            "sender": {"name": settings.email_from_name, "email": settings.email_from},
            "to": [{"email": to_email}],
            "subject": "Tilbakestill passord - Privatregnskap.eu",
            "htmlContent": html,
            "textContent": text,
        },
    )
    response.raise_for_status()
