"""
MB Luxury Events — Bot Telegram v3
- Claude API estrae i dati dal messaggio
- Canva REST API modifica il template direttamente
"""

import os
import json
import logging
import httpx
import anthropic
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CANVA_TOKEN       = os.environ.get("CANVA_TOKEN", "")
CANVA_DESIGN_ITA  = os.environ.get("CANVA_DESIGN_ITA", "DAHHaCBY8Ks")
CANVA_DESIGN_ENG  = os.environ.get("CANVA_DESIGN_ENG", "DAHGeHDN8_U")

with open("formazioni.json", "r", encoding="utf-8") as f:
    _lib = json.load(f)["mb_luxury_events"]["formazioni"]
FORMAZIONI_MAP = {f["id"]: f for f in _lib}
FORMAZIONI_LIST = "\n".join(
    f'- {f["nome_display"]} → id: "{f["id"]}"' for f in _lib
)

SYSTEM_PROMPT = f"""Sei l'assistente di MB Luxury Events.
Estrai i dati dal messaggio dell'utente e rispondi SOLO con un JSON valido, nessun altro testo.

Formato JSON richiesto:
{{
  "lingua": "ITA" o "ENG",
  "sposi": "Nome & Cognome",
  "data_evento": "gg Mese aaaa",
  "location": "Nome Location, Città (Provincia)",
  "formazioni": [
    {{"momento": "Aperitivo", "id": "id_formazione"}},
    {{"momento": "Dinner", "id": "id_formazione"}},
    {{"momento": "After Dinner", "id": "id_formazione"}},
    {{"momento": "Taglio Torta", "id": "id_formazione"}}
  ],
  "totale": "X.XXX €",
  "include_voices": false,
  "completo": true
}}

Se mancano dati obbligatori (sposi, data, location, almeno una formazione, totale),
metti "completo": false e rispondi con una domanda gentile in italiano per i dati mancanti
— in quel caso NON restituire JSON, scrivi solo la domanda.

Formazioni disponibili:
{FORMAZIONI_LIST}

Usa "ITA" per nomi italiani, "ENG" per nomi stranieri o se il testo è in inglese.
"""

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

RACCOLTA = 1

# ── Elementi Canva ITA ────────────────────────────────────────────────
ELEMENTI_ITA = {
    "titolo":         "PBWyxWrvztPjyDtn-LB2BsQQS2MGmnD7M",
    "data_loc":       "PBWyxWrvztPjyDtn-LB0Sr05DnKGDwx4n",
    "footer_p2":      "PB2MlGvVXNdZXJrv-LBLHQRf5hDdfSFGg",
    "footer_p3":      "PBrk8D8hH58TKzVX-LBSZ4QJ8QCKMJWfx",
    "footer_p4":      "PB3Py5lt3H1dkJjn-LBTpZrvncDtzLfDw",
    "aperitivo_mom":  "PB2MlGvVXNdZXJrv-LBp0xfHyJcmDMMCn",
    "aperitivo_copy": "PB2MlGvVXNdZXJrv-LBfjX1Rdp8pq2xBP",
    "dinner_mom":     "PB2MlGvVXNdZXJrv-LBgM1NhgvzxGHgfQ",
    "dinner_copy":    "PB2MlGvVXNdZXJrv-LB3fSS0Hq73tfyTZ",
    "after_mom":      "PB2MlGvVXNdZXJrv-LBsHc9qWpFrdCm2X",
    "after_copy":     "PB2MlGvVXNdZXJrv-LBnbkKBzp2XTmJs4",
    "torta_mom":      "PB2MlGvVXNdZXJrv-LBGDNC6K4BjKZ6N6",
    "torta_copy":     "PB2MlGvVXNdZXJrv-LBHCGRswjR3ccPpr",
    "fee_r1":         "PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-A1",
    "fee_r2":         "PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-A3",
    "fee_r3":         "PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-WBt--_gfGpm7Qxh3A:mj7900ec:0",
    "totale":         "PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-tdzihiU1N3bwUJEsA:mmaxlxx8:1",
}

MOMENTO_MAP = {
    "aperitivo":    ("aperitivo_mom", "aperitivo_copy"),
    "dinner":       ("dinner_mom",    "dinner_copy"),
    "after dinner": ("after_mom",     "after_copy"),
    "taglio torta": ("torta_mom",     "torta_copy"),
}

def get_copy(form_id: str, lingua: str) -> str:
    f = FORMAZIONI_MAP.get(form_id)
    if not f:
        return form_id
    if lingua == "ITA" and f.get("lingua") == "ENG":
        return f.get("traduzione_ITA", f["copy"])
    if lingua == "ENG" and f.get("lingua") == "ITA":
        return f.get("traduzione_ENG", f["copy"])
    return f["copy"]

def get_nome(form_id: str) -> str:
    f = FORMAZIONI_MAP.get(form_id)
    return f["nome_display"].upper() if f else form_id.upper()

def modifica_canva(dati: dict) -> str:
    if not CANVA_TOKEN:
        return None

    design_id = CANVA_DESIGN_ITA if dati.get("lingua", "ITA") == "ITA" else CANVA_DESIGN_ENG
    lingua = dati.get("lingua", "ITA")
    sposi = dati["sposi"]
    headers = {
        "Authorization": f"Bearer {CANVA_TOKEN}",
        "Content-Type": "application/json"
    }

    # Apri sessione
    r = httpx.post(
        f"https://api.canva.com/rest/v1/designs/{design_id}/editing_sessions",
        headers=headers, timeout=30
    )
    if r.status_code != 200:
        logger.error(f"Canva session error: {r.status_code} {r.text}")
        return None

    session_id = r.json()["editing_session"]["id"]

    # Prepara operazioni
    ops = [
        {"type": "replace_text", "element_id": ELEMENTI_ITA["titolo"],
         "text": f"{sposi.upper()} WEDDING"},
        {"type": "replace_text", "element_id": ELEMENTI_ITA["data_loc"],
         "text": f"{dati['data_evento']}\n{dati['location']}"},
        {"type": "replace_text", "element_id": ELEMENTI_ITA["footer_p2"],
         "text": f"{sposi} Wedding "},
        {"type": "replace_text", "element_id": ELEMENTI_ITA["footer_p3"],
         "text": f"{sposi} Wedding "},
        {"type": "replace_text", "element_id": ELEMENTI_ITA["footer_p4"],
         "text": f"{sposi} Wedding "},
        {"type": "replace_text", "element_id": ELEMENTI_ITA["totale"],
         "text": dati.get("totale", "")},
    ]

    # Formazioni
    fee_voci = []
    for form in dati.get("formazioni", []):
        momento = form["momento"].lower()
        form_id = form["id"]
        nome = get_nome(form_id)
        copy = get_copy(form_id, lingua)
        fee_voci.append(f"{form['momento']}: {get_nome(form_id)}")

        keys = MOMENTO_MAP.get(momento)
        if keys:
            ops.append({"type": "replace_text",
                        "element_id": ELEMENTI_ITA[keys[0]],
                        "text": form["momento"]})
            ops.append({"type": "replace_text",
                        "element_id": ELEMENTI_ITA[keys[1]],
                        "text": f"{nome}\n{copy}"})

    # Fee rows
    for i, key in enumerate(["fee_r1", "fee_r2", "fee_r3"]):
        ops.append({"type": "replace_text",
                    "element_id": ELEMENTI_ITA[key],
                    "text": fee_voci[i] if i < len(fee_voci) else ""})

    # Esegui operazioni
    r2 = httpx.post(
        f"https://api.canva.com/rest/v1/designs/{design_id}/editing_sessions/{session_id}/commands",
        headers=headers,
        json={"commands": ops},
        timeout=30
    )

    # Commit
    action = "commit" if r2.status_code == 200 else "cancel"
    httpx.post(
        f"https://api.canva.com/rest/v1/designs/{design_id}/editing_sessions/{session_id}/{action}",
        headers=headers, timeout=30
    )

    if r2.status_code == 200:
        return f"https://www.canva.com/design/{design_id}/edit"
    else:
        logger.error(f"Canva edit error: {r2.status_code} {r2.text}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "👋 Ciao! Sono il bot di MB Luxury Events.\n\n"
        "Mandami i dati del preventivo, ad esempio:\n\n"
        "Marco e Sofia, 15 agosto 2026, Villa Rufolo Ravello SA, "
        "aperitivo quartetto acustico, dinner cool vibes band, "
        "party velvet aura, taglio torta sax bar, totale 3500 euro"
    )
    return RACCOLTA

async def raccolta_dati(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = update.message.text

    if "history" not in context.user_data:
        context.user_data["history"] = []

    context.user_data["history"].append({"role": "user", "content": testo})

    await update.message.reply_text("Elaboro i dati...")

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=context.user_data["history"]
        )
        risposta = response.content[0].text.strip()
        context.user_data["history"].append({"role": "assistant", "content": risposta})

        # Prova a parsare JSON
        try:
            risposta_pulita = risposta.strip()
            if risposta_pulita.startswith("```"):
                risposta_pulita = risposta_pulita.split("```")[1]
                if risposta_pulita.startswith("json"):
                    risposta_pulita = risposta_pulita[4:]
            risposta_pulita = risposta_pulita.strip()
            dati = json.loads(risposta_pulita)

            if not dati.get("completo", False):
                await update.message.reply_text(risposta)
                return RACCOLTA

            # Dati completi — prepara riepilogo e link Canva
            lingua = dati.get("lingua", "ITA")
            canva_url = (
                "https://www.canva.com/design/DAHHaCBY8Ks/edit"
                if lingua == "ITA"
                else "https://www.canva.com/design/DAHGeHDN8_U/edit"
            )

            formazioni_testo = "\n".join(
                f"  - {f['momento']}: {FORMAZIONI_MAP.get(f['id'], {}).get('nome_display', f['id'])}"
                for f in dati.get("formazioni", [])
            )

            msg = (
                f"Preventivo pronto!\n\n"
                f"Sposi: {dati['sposi']}\n"
                f"Data: {dati['data_evento']}\n"
                f"Location: {dati['location']}\n"
                f"Formazioni:\n{formazioni_testo}\n"
                f"Totale: {dati['totale']}\n\n"
                f"Apri il template Canva:\n{canva_url}"
            )

            await update.message.reply_text(msg)
            context.user_data["history"] = []

        except json.JSONDecodeError:
            # Claude sta chiedendo dati mancanti
            await update.message.reply_text(risposta)

    except Exception as e:
        logger.error(f"Errore: {e}")
        await update.message.reply_text("Si e verificato un errore. Riprova.")

    return RACCOLTA

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("Annullato. Mandami i dati quando vuoi!")
    return RACCOLTA

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, raccolta_dati)
        ],
        states={
            RACCOLTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, raccolta_dati)]
        },
        fallbacks=[CommandHandler("annulla", annulla)],
        allow_reentry=True
    )
    app.add_handler(conv)
    logger.info("Bot MB Luxury Events v3 avviato!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
