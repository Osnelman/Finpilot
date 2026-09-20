#!/bin/bash
# lancer.sh : démarre FinPilot
# Usage : ./lancer.sh          (modèle Gemini)
#         ./lancer.sh local    (modèle local Qwen via Ollama)

cd "$HOME/Bureau/hacquaton" || { echo "Dossier du projet introuvable"; exit 1; }
source venv/bin/activate || { echo "Environnement virtuel introuvable"; exit 1; }

if [ "$1" = "local" ]; then
  export LLM_BACKEND=ollama
else
  export LLM_BACKEND=gemini
  if [ -z "$GEMINI_API_KEY" ]; then
    read -s -p "Cle Gemini (Ctrl+Maj+V pour coller, puis Entree) : " GEMINI_API_KEY
    echo
    export GEMINI_API_KEY
  fi
fi

streamlit run app.py