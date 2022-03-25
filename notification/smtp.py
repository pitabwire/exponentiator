import logging
import os
import smtplib
import ssl

from notification import NotifierInterface

log = logging.getLogger(__name__)

ENVIRONMENT_EMAIL_USERNAME_KEY = 'EMAIL_USERNAME'
ENVIRONMENT_EMAIL_PASSWORD_KEY = 'EMAIL_PASSWORD'
ENVIRONMENT_EMAIL_RECEIVER_ADDRESS_KEY = 'EMAIL_RECEIVER_ADDRESS'
ENVIRONMENT_EMAIL_SMTP_SERVER_HOST_KEY = 'EMAIL_SMTP_SERVER_HOST'
ENVIRONMENT_EMAIL_SMTP_SERVER_PORT_KEY = 'EMAIL_SMTP_SERVER_PORT'


class EmailHandler(NotifierInterface):

    def __init__(self):
        self.smtp_server_host = None
        self.smtp_server_port = None
        self.user_name = None
        self.password = None
        self.receiver_email = None

    def setup(self):
        self.user_name = os.getenv(ENVIRONMENT_EMAIL_USERNAME_KEY)
        self.password = os.getenv(ENVIRONMENT_EMAIL_PASSWORD_KEY)
        self.receiver_email = os.getenv(ENVIRONMENT_EMAIL_RECEIVER_ADDRESS_KEY)

        self.smtp_server_host = os.getenv(ENVIRONMENT_EMAIL_SMTP_SERVER_HOST_KEY, 'in-v3.mailjet.com')
        self.smtp_server_port = os.getenv(ENVIRONMENT_EMAIL_SMTP_SERVER_PORT_KEY, 587)

        if not all([self.user_name, self.password, self.receiver_email, self.smtp_server_host, self.smtp_server_port]):
            log.warning("No email credentials exist set the environment variables %s, %s, %s",
                        ENVIRONMENT_EMAIL_USERNAME_KEY, ENVIRONMENT_EMAIL_PASSWORD_KEY,
                        ENVIRONMENT_EMAIL_RECEIVER_ADDRESS_KEY)
            return

    def send(self, subject, content):
        message = f"""\
        Subject: {subject}

        {content}"""

        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_server_host, self.smtp_server_port) as server:
            server.starttls(context=context)
            server.login(self.user_name, self.password)
            server.sendmail(self.user_name, self.receiver_email, message)
