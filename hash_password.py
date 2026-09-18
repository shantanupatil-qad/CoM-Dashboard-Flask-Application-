"""Print one user entry for APP_USERS_FILE without echoing a password."""
import getpass
import json
from werkzeug.security import generate_password_hash
if __name__ == '__main__':
    username=input('Approved username: ').strip()
    password=getpass.getpass('Password (minimum 16 characters): ')
    confirmation=getpass.getpass('Confirm password: ')
    if not username or len(password)<16 or password!=confirmation:
        raise SystemExit('Username is required; passwords must match and contain at least 16 characters.')
    print(json.dumps({username:generate_password_hash(password, method='pbkdf2:sha256')},indent=2))
