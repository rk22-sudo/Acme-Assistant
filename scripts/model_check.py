import sys

from dotenv import load_dotenv
from google.genai.errors import APIError

from app.llm import _get_client

load_dotenv()
model = sys.argv[1]
try:
    r = _get_client().models.generate_content(model=model, contents="Say OK")
    print("OK:", r.text)
except APIError as e:
    print("code:", e.code)
    print(str(e)[:500])