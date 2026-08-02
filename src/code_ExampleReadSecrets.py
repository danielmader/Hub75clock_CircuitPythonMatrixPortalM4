# Write your code here :-)

import json
import os

## Auf dem Gerät liegt eine lokale secrets.py (gitignored), die für die Checker
## das gleichnamige CPython-stdlib-Modul verschattet - daher die ignore-Marker.
import secrets

print("Hello World!")

print(secrets.creds_dict)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]

## settings.toml
print(os.getenv("test_variable"))

## JSON
secrets_dict = {
    'key1': 'asdf',
    'key2': 'qwer',
    'key3': 'foobar',
}
## Speichern in einer JSON-Datei
# with open('secrets.json', 'w') as f:
#     json.dump(secrets_dict, f, indent=4)  # indent sorgt für bessere Lesbarkeit
## Laden der JSON-Datei
with open('secrets.json', 'r') as f:
    secrets_dict = json.load(f)
print(secrets_dict)

print(secrets.creds_dict)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
