import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from core.config.settings import settings
from core.observability.failure_registry import FailureRegistry


class EmailService:
    @staticmethod
    async def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
        correlation_id: str | None = None
    ) -> bool:
        """
        Sends an email using aiosmtplib with production hardening.
        Includes retries, timeouts, and proper MIME structure.
        """
        
        if not settings.SMTP_HOST:
            FailureRegistry.record("EMAIL_SMTP_UNCONFIGURED", "SMTP_HOST not configured. Skipping email send", "WARNING", extra={"correlation_id": correlation_id})
            return False
        else:
            FailureRegistry.recover("EMAIL_SMTP_UNCONFIGURED")

        message = MIMEMultipart("alternative")
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject

        if text_content:
            message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))

        max_retries = 3
        retry_delay = 2
        # Determine TLS / STARTTLS mode based on port to avoid connection hangs
        use_tls = False
        start_tls = False
        
        if settings.SMTP_PORT == 465:
            use_tls = True
        elif settings.SMTP_PORT == 587:
            start_tls = True
        else:
            use_tls = settings.SMTP_USE_TLS
            start_tls = not use_tls

        for attempt in range(max_retries):
            try:
                smtp_client = aiosmtplib.SMTP(
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    use_tls=use_tls,
                    start_tls=start_tls,
                    timeout=10,
                )
                
                async with smtp_client:
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        await smtp_client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    
                    await smtp_client.send_message(message)
                
                FailureRegistry.recover("EMAIL_SEND_FAILED")
                FailureRegistry.recover("EMAIL_SEND_EXHAUSTED")
                return True

            except (TimeoutError, aiosmtplib.SMTPException, OSError) as e:
                FailureRegistry.record("EMAIL_SEND_FAILED", f"Failed to send email on attempt {attempt + 1}: {e}", "WARNING", extra={"correlation_id": correlation_id, "attempt": attempt + 1, "error": str(e)})
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    FailureRegistry.record("EMAIL_SEND_EXHAUSTED", f"Exhausted retries for email: {e}", "ERROR", extra={"correlation_id": correlation_id})
        
        return False

    @classmethod
    async def send_otp_email(cls, to_email: str, otp: str, purpose: str = "LOGIN", correlation_id: str | None = None) -> bool:
        """Structured OTP email with HTML and text fallbacks."""
        subject = f"Your Veena Garments {purpose} Verification Code"
        
        # Premium HTML template branded for Veena Garments
        html_content = f"""
        <html>
            <body style="margin: 0; padding: 0; background-color: #f4f7f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f4f7f5; padding: 40px 20px;">
                    <tr>
                        <td align="center">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(18, 130, 64, 0.05); border: 1px solid #e2ece6;">
                                <!-- Header -->
                                <tr>
                                    <td style="background: linear-gradient(135deg, #128240 0%, #16a34a 100%); padding: 30px; text-align: center;">
                                        <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; font-family: 'Segoe UI', Arial, sans-serif;">Veena Garments</h1>
                                    </td>
                                </tr>
                                <!-- Body -->
                                <tr>
                                    <td style="padding: 40px 30px; text-align: center;">
                                        <h2 style="color: #1f2937; margin-top: 0; margin-bottom: 12px; font-size: 20px; font-weight: 600;">Verification Code</h2>
                                        <p style="color: #4b5563; font-size: 14px; line-height: 1.5; margin-bottom: 24px;">Please use the following verification code to complete your login. Click or double-click to select it:</p>
                                        
                                        <!-- OTP Block -->
                                        <div style="background-color: #f0fdf4; border: 1px dashed #16a34a; border-radius: 8px; padding: 18px 24px; display: inline-block; margin-bottom: 24px;">
                                            <span style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: 32px; font-weight: 700; color: #14532d; letter-spacing: 6px; user-select: all; -webkit-user-select: all; -moz-user-select: all; -ms-user-select: all;">{otp}</span>
                                        </div>
                                        
                                        <p style="color: #dc2626; font-size: 13px; font-weight: 500; margin-top: 0; margin-bottom: 24px;">This code is valid for exactly 2 minutes.</p>
                                        <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 24px 0;">
                                        <p style="color: #9ca3af; font-size: 11px; line-height: 1.4; margin: 0;">Veena Garments Pvt Ltd &copy; Since 1965. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
        text_content = f"Your Veena Garments {purpose} verification code is: {otp}. It is valid for exactly 2 minutes."
        
        return await cls.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            correlation_id=correlation_id
        )
