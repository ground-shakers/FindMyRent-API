import os

import firebase_admin
from firebase_admin import credentials, messaging

from dotenv import load_dotenv

load_dotenv()

# 1. Initialize Firebase Admin
# Download your service account key from: 
# Firebase Console -> Project Settings -> Service Accounts -> Generate New Private Key
cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
firebase_admin.initialize_app(cred)

# 2. The Device Token (Copy this from your Flutter App screen)
# It will look like a long string of random characters
registration_token = 'YOUR_DEVICE_TOKEN_COPIED_FROM_APP'

# 3. Construct the message
message = messaging.Message(
    notification=messaging.Notification(
        title='Connection Test',
        body='Hello from Python! If you see this, the pipeline works.',
    ),
    token=registration_token,
)

# 4. Send the message
try:
    response = messaging.send(message)
    print('Successfully sent message:', response)
except Exception as e:
    print('Error sending message:', e)