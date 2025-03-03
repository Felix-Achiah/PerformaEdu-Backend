import secrets
import string

def generate_verification_token():
    # Generate a random token
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for i in range(32))
    return token

