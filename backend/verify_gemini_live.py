"""
Safe minimal live verification script for Google Gemini LLM provider.
Never prints, logs, or exposes the API key.
Exits cleanly if GEMINI_API_KEY is unset or is a placeholder.
Warns and stops if billing is requested.
"""
import sys
import os
import asyncio
from dotenv import load_dotenv

# Load backend/.env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()


async def verify_live_gemini():
    from llm.gemini_provider import GeminiProvider, is_valid_gemini_key

    if not is_valid_gemini_key(os.getenv("GEMINI_API_KEY")):
        print("[STATUS] GEMINI_API_KEY is not configured (or is a placeholder) in backend/.env.")
        print("[INFO] To enable live Gemini calls:")
        print("       1. Get a free API key at https://aistudio.google.com/apikey (no billing required).")
        print("       2. Add GEMINI_API_KEY=your_key to backend/.env.")
        print("       3. Run this script again: python verify_gemini_live.py")
        return 0

    # Fetch raw key only for scrubbing in case it appears in exception messages
    raw_key = os.getenv("GEMINI_API_KEY", "")

    def sanitize(msg: str) -> str:
        if raw_key and len(raw_key) > 4:
            return msg.replace(raw_key, "[REDACTED]")
        return msg

    provider = GeminiProvider()
    print(f"[STATUS] Initialized Gemini provider (model: {provider.model_name}).")
    print("[STATUS] Sending minimal live test request (max_tokens=30)...")

    try:
        response = await provider.generate_response(
            prompt="Reply with the single phrase 'Gemini live test OK'.",
            history=[],
            context_text="",
            citations=[],
            has_sufficient_context=True,
            system_prompt="You are a helpful assistant.",
            max_tokens=30,
        )
        reply = sanitize(response.content.strip().replace("\n", " "))
        print(f"[SUCCESS] Received live response from Gemini: \"{reply[:80]}\"")
        input_tokens = response.metadata.get("input_tokens", "N/A")
        output_tokens = response.eval_count or response.metadata.get("output_tokens", "N/A")
        print(f"[SUCCESS] Tokens used: input={input_tokens}, output={output_tokens}")
        return 0
    except Exception as exc:
        err = sanitize(str(exc))
        if "billing" in err.lower() or "payment" in err.lower() or "402" in err:
            print("[ALERT] Google API indicated billing is required. Free tier exhausted or unavailable.")
            print("[ACTION] STOP: Do NOT add a payment method or upgrade to paid tier.")
            return 1
        elif "quota" in err.lower() or "429" in err or "resource_exhausted" in err.lower():
            print("[NOTICE] Gemini free tier rate limit or quota exceeded.")
            print(f"[DETAIL] {err[:150]}")
            return 1
        elif "400" in err or "401" in err or "403" in err or "api_key_invalid" in err.lower() or "key not valid" in err.lower():
            print("[ERROR] Gemini API authentication error: Key was rejected or invalid.")
            print(f"[DETAIL] {err[:150]}")
            return 1
        else:
            print(f"[ERROR] Live test encountered an error: {err[:200]}")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(verify_live_gemini())
    sys.exit(exit_code)
