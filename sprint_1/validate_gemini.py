"""Smoke test Vertex AI Gemini — confirma que la SA + rol Vertex User funcionan.

Uso:
    py sprint_1/validate_gemini.py > diag_gemini.txt 2>&1

Llama a Gemini via Vertex AI con la misma config que vision_extractor.py.
Si pasa, el pipeline puede usar el Free Trial GCP de mejorahora-automations.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    try:
        from vision_extractor import _get_vertex_config, _vertex_client, DEFAULT_MODEL
    except ImportError as e:
        print(f"[ERR] No pude importar vision_extractor: {e}")
        return 2

    cfg = _get_vertex_config()
    print(f"[info] Project: {cfg['project']}")
    print(f"[info] Location: {cfg['location']}")
    print(f"[info] Credentials file: {cfg['credentials_file']}")

    creds_path = Path(cfg["credentials_file"]) if cfg["credentials_file"] else None
    if not creds_path or not creds_path.exists():
        print(f"[ERR] No existe el archivo de credenciales: {creds_path}")
        return 2

    try:
        client = _vertex_client()
        print("[info] Client Vertex AI instanciado OK")
    except Exception as e:
        print(f"[FAIL] No pude instanciar client: {type(e).__name__}: {e}")
        return 1

    # Smoke test: llamada minima (solo texto, ~20 tokens)
    try:
        from google.genai import types
    except ImportError as e:
        print(f"[ERR] google-genai types no disponible: {e}")
        return 2

    for model_name in (DEFAULT_MODEL, "gemini-2.5-flash", "gemini-2.0-flash-001"):
        print(f"\n--- Probando {model_name} ---")
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents="Di solo la palabra OK.",
                config=types.GenerateContentConfig(
                    max_output_tokens=10,
                    temperature=0.0,
                ),
            )
            text = (resp.text or "").strip()
            print(f"[OK] {model_name} respondio: {text!r}")
            um = getattr(resp, "usage_metadata", None)
            if um:
                p = getattr(um, "prompt_token_count", "?")
                c = getattr(um, "candidates_token_count", "?")
                t = getattr(um, "total_token_count", "?")
                print(f"    tokens: prompt={p} resp={c} total={t}")
        except Exception as e:
            msg = str(e)
            short = msg[:500]
            print(f"[FAIL] {model_name}: {type(e).__name__}: {short}")
            if "PERMISSION_DENIED" in msg or "403" in msg:
                print("       ^ SA sin rol 'Vertex AI User' o API Vertex AI no habilitada")
            elif "429" in msg or "quota" in msg.lower():
                print("       ^ Rate limit o quota agotada")
            elif "billing" in msg.lower() or "billed" in msg.lower():
                print("       ^ Billing no activo en el proyecto")

    print("\n== Fin smoke test ==")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
