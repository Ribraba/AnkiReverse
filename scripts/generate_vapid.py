"""
Génère les clés VAPID nécessaires pour les Web Push notifications.
Usage : python scripts/generate_vapid.py
"""
from pywebpush import Vapid

vapid = Vapid()
vapid.generate_keys()

public_key = vapid.public_key.public_bytes(
    encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.X962,
    format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.UncompressedPoint,
)

import base64

public_b64 = base64.urlsafe_b64encode(public_key).decode().rstrip("=")
private_pem = vapid.private_key.private_bytes(
    encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.PEM,
    format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PrivateFormat"]).PrivateFormat.PKCS8,
    encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["NoEncryption"]).NoEncryption(),
).decode()

print("Ajoutez ces valeurs dans votre fichier .env :\n")
print(f"VAPID_PUBLIC_KEY={public_b64}")
print(f"VAPID_PRIVATE_KEY={private_pem.strip()}")
print(f"VAPID_EMAIL=mailto:votre@email.com")
print("\nCopiez VAPID_PUBLIC_KEY dans pwa/.env.local :")
print(f"NEXT_PUBLIC_VAPID_KEY={public_b64}")
