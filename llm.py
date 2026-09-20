import os

BACKEND = os.getenv("LLM_BACKEND", "ollama")            # "ollama" ou "gemini"
MODELE_OLLAMA = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
MODELE_GEMINI = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # à vérifier dans AI Studio


def demander_llm(prompt, json_mode=False):
    """Envoie un prompt au modèle et retourne le texte de la réponse."""
    if BACKEND == "gemini":
        from google import genai
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        config = {"temperature": 0}
        if json_mode:
            config["response_mime_type"] = "application/json"
        rep = client.models.generate_content(model=MODELE_GEMINI, contents=prompt, config=config)
        return rep.text or ""
    import ollama
    rep = ollama.chat(
        model=MODELE_OLLAMA,
        messages=[{"role": "user", "content": prompt}],
        format="json" if json_mode else None,
        options={"temperature": 0},
    )
    return rep["message"]["content"]