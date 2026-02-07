import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.config import get_settings
import ssl

settings = get_settings()


def send_password_reset_email(to_email: str, reset_token: str, user_name: str):
    """Send password reset email with token link"""

    # Create reset link
    reset_link = f"https://{settings.rp_id}/reset-password?token={reset_token}"

    # Create email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Tilbakestill passord - Regnskap'
    msg['From'] = settings.smtp_from
    msg['To'] = to_email

    # Plain text version
    text = f"""
Hei {user_name},

Du har bedt om å tilbakestille passordet ditt for Regnskap.

Klikk på lenken nedenfor for å tilbakestille passordet:
{reset_link}

Lenken er gyldig i 1 time.

Hvis du ikke ba om dette, kan du ignorere denne e-posten.

Hilsen
Regnskap
"""

    # HTML version
    html = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2>Tilbakestill passord</h2>
    <p>Hei {user_name},</p>
    <p>Du har bedt om å tilbakestille passordet ditt for Regnskap.</p>
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
    <p style="color: #999; font-size: 0.8em;">Hilsen Regnskap</p>
  </body>
</html>
"""

    # Attach both versions
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    # Send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
