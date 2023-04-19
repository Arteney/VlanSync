# Authentication token (replace with your own authentication logic)
AUTH_TOKEN = 'your_auth_token'

def authenticate(token):
    """Authenticate the request using token"""
    if token == AUTH_TOKEN:
        return True
    else:
        return False