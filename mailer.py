import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes for Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(service, to, subject, body, cc=None, bcc=None):
    """
    Sends an email via the Gmail API.
    
    Parameters:
        service: Authenticated Gmail API service object
        to (str): Primary recipient email address
        subject (str): Email subject
        body (str): Email body (plain text)
        cc (str or list, optional): CC recipient(s)
        bcc (str or list, optional): BCC recipient(s)
    """
    message = MIMEMultipart()
    message['To'] = to
    message['Subject'] = subject

    # Handle CC and BCC (convert to comma-separated string if given as a list)
    if cc:
        if isinstance(cc, list):
            cc = ', '.join(cc)
        message['Cc'] = cc
    if bcc:
        if isinstance(bcc, list):
            bcc = ', '.join(bcc)

    message.attach(MIMEText(body, 'plain'))

    # Combine all recipients for the Gmail API call
    all_recipients = [to]
    if cc:
        all_recipients += cc.split(', ')
    if bcc:
        all_recipients += bcc.split(', ')

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    try:
        send_result = service.users().messages().send(
            userId="me", body={"raw": raw_message}
        ).execute()
        print(f"Email sent! Message ID: {send_result['id']}")
    except Exception as e:
        print("An error occurred while sending email:", e)


def authenticate_gmail():
    """
    Authenticates.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        print("Reading existing credentials from token.json")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired creds...")
            creds.refresh(Request())
        else:
            print("Creating new signin flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    if not creds:
        raise "Could not load credentials - check README.md for instructions"
    return build('gmail', 'v1', credentials=creds)

def main(args):
    if not len(args):
        print("Usage: python mailer.py <email>")
        return

    email = args[0]
    service = authenticate_gmail()
    send_email(service, email, "Test email from Python", "This is a test email sent from Python")

if __name__ == '__main__':
    main(sys.argv[1:])


