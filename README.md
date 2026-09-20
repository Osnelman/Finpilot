# FinPilot

Personal finance decision-support agent (Agentic AI Hackathon 2026, Problem Statement 2).

Imports a CSV statement (date, libelle, montant), categorizes spending, detects recurring
payments and unusual expenses, compares with budgets, projects a savings goal, answers
questions in plain language and writes a monthly report.

The code computes every figure; the AI only explains. It is designed to explain data,
not to give financial advice. The demo data is fictional.

Run: pip install -r requirements.txt, set GEMINI_API_KEY and LLM_BACKEND=gemini, then
streamlit run app.py
