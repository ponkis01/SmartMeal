import os
from dotenv import load_dotenv

# .env laden
load_dotenv()

# Zugriff auf den Key
API_KEY = os.getenv("SPOONACULAR_API_KEY")

# Test (nur zur Sicherheit)
if not API_KEY:
    print("❌ API key not found. Make sure it's set in the .env file.")
