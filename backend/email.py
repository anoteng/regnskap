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


def send_bank_connection_error_email(
    to_email: str,
    user_name: str,
    account_name: str,
    needs_reauth: bool,
    failures: int,
    error: str,
):
    """Tell the owner that a bank connection has stopped syncing on its own."""

    link = f"https://{settings.rp_id}/?view=bank-connections"

    if needs_reauth:
        heading = "Bankkoblingen må autoriseres på nytt"
        reason = (
            f"Banksesjonen for <strong>{account_name}</strong> har utløpt. "
            "Transaksjoner hentes ikke inn før du har logget inn i banken på nytt."
        )
        reason_text = (
            f"Banksesjonen for {account_name} har utløpt. Transaksjoner hentes ikke "
            "inn før du har logget inn i banken på nytt."
        )
    else:
        heading = "Bankkoblingen får ikke kontakt"
        reason = (
            f"Synkroniseringen av <strong>{account_name}</strong> har feilet "
            f"{failures} ganger på rad. Feilen kommer fra banken, ikke fra sesjonen, "
            "men den har vart lenge nok til at den bør ses på."
        )
        reason_text = (
            f"Synkroniseringen av {account_name} har feilet {failures} ganger på rad. "
            "Feilen kommer fra banken, ikke fra sesjonen, men den har vart lenge nok "
            "til at den bør ses på."
        )

    text = f"""
Hei {user_name},

{reason_text}

Siste feilmelding:
{error}

Åpne bankkoblinger: {link}

Hilsen
Privatregnskap.eu
"""

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2>{heading}</h2>
    <p>Hei {user_name},</p>
    <p>{reason}</p>
    <p style="margin: 30px 0;">
      <a href="{link}"
         style="background-color: #4CAF50; color: white; padding: 12px 24px;
                text-decoration: none; border-radius: 4px; display: inline-block;">
        Åpne bankkoblinger
      </a>
    </p>
    <p style="color: #666; font-size: 0.9em;">Siste feilmelding:</p>
    <pre style="color: #666; font-size: 0.8em; white-space: pre-wrap;">{error}</pre>
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
            "subject": f"{heading} - Privatregnskap.eu",
            "htmlContent": html,
            "textContent": text,
        },
    )
    response.raise_for_status()


def send_push_connection_stale_email(
    to_email: str,
    user_name: str,
    account_name: str,
    days: int,
):
    """Tell the owner that their own device has stopped uploading transactions."""

    link = f"https://{settings.rp_id}/?view=bank-connections"
    heading = "Ingen nye transaksjoner fra enheten din"

    text = f"""
Hei {user_name},

{account_name} har ikke fått transaksjoner fra enheten din på {days} dager.

Denne kontoen hentes ikke av Privatregnskap.eu. Det er din egen enhet som henter
fra banken og laster opp, så når den stopper, stopper alt. Åpne appen eller
klienten og kjør en synkronisering. Har innloggingen mot banken utløpt, må du
logge inn med BankID på nytt der.

Åpne bankkoblinger: {link}

Hilsen
Privatregnskap.eu
"""

    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2>{heading}</h2>
    <p>Hei {user_name},</p>
    <p><strong>{account_name}</strong> har ikke fått transaksjoner fra enheten din
       på {days} dager.</p>
    <p>Denne kontoen hentes ikke av Privatregnskap.eu. Det er din egen enhet som
       henter fra banken og laster opp, så når den stopper, stopper alt. Åpne appen
       eller klienten og kjør en synkronisering. Har innloggingen mot banken utløpt,
       må du logge inn med BankID på nytt der.</p>
    <p style="margin: 30px 0;">
      <a href="{link}"
         style="background-color: #4CAF50; color: white; padding: 12px 24px;
                text-decoration: none; border-radius: 4px; display: inline-block;">
        Åpne bankkoblinger
      </a>
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
            "subject": f"{heading} - Privatregnskap.eu",
            "htmlContent": html,
            "textContent": text,
        },
    )
    response.raise_for_status()
