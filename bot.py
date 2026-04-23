"""
MB Luxury Events — Bot Telegram
Genera preventivi su Canva direttamente da Telegram.
"""

import os
import json
import logging
import anthropic
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Env vars ─────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CANVA_TOKEN      = os.environ["CANVA_TOKEN"]
CANVA_DESIGN_ITA = os.environ.get("CANVA_DESIGN_ITA", "DAHHaCBY8Ks")
CANVA_DESIGN_ENG = os.environ.get("CANVA_DESIGN_ENG", "DAHGeHDN8_U")

# ── Libreria formazioni ───────────────────────────────────────────────
with open("formazioni.json", "r", encoding="utf-8") as f:
    FORMAZIONI = json.load(f)["mb_luxury_events"]["formazioni"]

FORMAZIONI_MAP = {f["id"]: f for f in FORMAZIONI}

# ── Stati conversazione ───────────────────────────────────────────────
RACCOLTA = 1

# ── System prompt per Claude ──────────────────────────────────────────
SYSTEM_PROMPT = """Sei l'assistente di MB Luxury Events, un'agenzia di musica per eventi di lusso.
Il tuo compito è raccogliere i dati per generare un preventivo e restituirli in formato JSON strutturato.

Quando l'utente ti fornisce i dati del preventivo, estrai le informazioni e rispondi SOLO con un JSON nel formato:

{
  "lingua": "ITA" oppure "ENG",
  "sposi": "Nome & Cognome",
  "data_evento": "gg mese aaaa",
  "location": "Nome Location, Città (Provincia)",
  "formazioni": [
    {"momento": "Aperitivo", "id_formazione": "id_dalla_libreria"},
    {"momento": "Dinner", "id_formazione": "id_dalla_libreria"},
    ...
  ],
  "totale": "X.XXX €",
  "note": "eventuali note aggiuntive o stringa vuota",
  "include_voices": true oppure false,
  "voice_ids": ["gabriella", "nancy"] oppure lista vuota
}

Per "id_formazione" usa uno di questi ID dalla libreria formazioni:
violino_solo, sax_dj_set, dj_set, filodiffusione, sax_bar, quartetto_acustico,
velvet_aura_live_show, live_band, caponi_brothers, voce_pianoforte_arpa_violino,
trio_unplugged, velvet_aura_5et, cool_vibes_band, fab_five, posteggia_napoletana,
quartetto_archi, dixieland_band

Se l'utente non specifica la lingua, usa ITA per nomi italiani, ENG per nomi stranieri.
Se mancano dati, chiedi solo quelli mancanti in modo breve e amichevole.
Rispondi sempre in italiano."""

# ── Client Anthropic ──────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Funzione: chiama Claude per estrarre dati ─────────────────────────
def estrai_dati_preventivo(testo_utente: str) -> dict | None:
    """Usa Claude per estrarre i dati dal messaggio dell'utente."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": testo_utente}]
        )
        testo = response.content[0].text.strip()

        # Prova a parsare JSON
        if testo.startswith("{"):
            return json.loads(testo)
        return None  # Claude sta chiedendo altri dati
    except Exception as e:
        logger.error(f"Errore Claude: {e}")
        return None

# ── Funzione: modifica Canva ──────────────────────────────────────────
import httpx

def modifica_canva(dati: dict) -> str | None:
    """Modifica il template Canva con i dati del preventivo. Ritorna l'URL del design."""
    design_id = CANVA_DESIGN_ITA if dati.get("lingua", "ITA") == "ITA" else CANVA_DESIGN_ENG
    headers = {
        "Authorization": f"Bearer {CANVA_TOKEN}",
        "Content-Type": "application/json"
    }

    # 1. Apri transazione
    r = httpx.post(
        f"https://api.canva.com/rest/v1/designs/{design_id}/editing_sessions",
        headers=headers
    )
    if r.status_code != 200:
        logger.error(f"Canva open session error: {r.text}")
        return None

    session = r.json()
    session_id = session["editing_session"]["id"]

    # 2. Prepara le operazioni
    operazioni = _prepara_operazioni(dati, design_id)

    # 3. Applica modifiche
    r2 = httpx.post(
        f"https://api.canva.com/rest/v1/designs/{design_id}/editing_sessions/{session_id}/commands",
        headers=headers,
        json={"commands": operazioni}
    )
    if r2.status_code != 200:
        logger.error(f"Canva edit error: {r2.text}")
        _chiudi_sessione(design_id, session_id, headers, commit=False)
        return None

    # 4. Commit
    _chiudi_sessione(design_id, session_id, headers, commit=True)

    return f"https://www.canva.com/design/{design_id}/edit"

def _chiudi_sessione(design_id, session_id, headers, commit=True):
    action = "commit" if commit else "cancel"
    httpx.post(
        f"https://api.canva.com/rest/v1/designs/{design_id}/editing_sessions/{session_id}/{action}",
        headers=headers
    )

def _prepara_operazioni(dati: dict, design_id: str) -> list:
    """Prepara la lista di operazioni di testo per Canva."""
    # Mappa element_id per ITA e ENG
    elementi_ita = {
        "titolo":    "PBWyxWrvztPjyDtn-LB2BsQQS2MGmnD7M",
        "data_loc":  "PBWyxWrvztPjyDtn-LB0Sr05DnKGDwx4n",
        "footer_p2": "PB2MlGvVXNdZXJrv-LBLHQRf5hDdfSFGg",
        "footer_p3": "PBrk8D8hH58TKzVX-LBSZ4QJ8QCKMJWfx",
        "footer_p4": "PB3Py5lt3H1dkJjn-LBTpZrvncDtzLfDw",
        "totale":    "PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-tdzihiU1N3bwUJEsA:mmaxlxx8:1",
        "nota_fee":  "PB3Py5lt3H1dkJjn-LB8SklK8B2jVVTVx",
    }

    ops = []
    sposi = dati["sposi"]
    lingua = dati.get("lingua", "ITA")

    # Cover
    ops.append({"type": "replace_text", "element_id": elementi_ita["titolo"],
                 "text": f"{sposi.upper()} wedding"})
    ops.append({"type": "replace_text", "element_id": elementi_ita["data_loc"],
                 "text": f"{dati['data_evento']}\n{dati['location']}"})

    # Footer su tutte le pagine
    for key in ["footer_p2", "footer_p3", "footer_p4"]:
        ops.append({"type": "replace_text", "element_id": elementi_ita[key],
                     "text": f"{sposi} Wedding "})

    # Totale
    ops.append({"type": "replace_text", "element_id": elementi_ita["totale"],
                 "text": dati["totale"]})

    return ops

# ── Handler Telegram ──────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono il bot di *MB Luxury Events*.\n\n"
        "Mandami i dati del preventivo in un messaggio, ad esempio:\n\n"
        "_Marco & Sofia, 15 agosto 2026, Villa Rufolo Ravello (SA), "
        "aperitivo quartetto acustico, dinner cool vibes band, "
        "party velvet aura, totale 3.500€_\n\n"
        "Posso anche chiederti i dati mancanti se non li fornisci tutti insieme.",
        parse_mode="Markdown"
    )
    return RACCOLTA

async def raccolta_dati(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = update.message.text

    await update.message.reply_text("⏳ Elaboro i dati...")

    # Storico conversazione per gestire domande di follow-up
    if "history" not in context.user_data:
        context.user_data["history"] = []

    context.user_data["history"].append({"role": "user", "content": testo})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=context.user_data["history"]
        )
        risposta = response.content[0].text.strip()
        context.user_data["history"].append({"role": "assistant", "content": risposta})

        # Se è JSON → genera il preventivo
        if risposta.startswith("{"):
            dati = json.loads(risposta)
            await update.message.reply_text("✅ Dati ricevuti! Modifico il template su Canva...")

            url = modifica_canva(dati)
            if url:
                await update.message.reply_text(
                    f"🎉 *Preventivo pronto!*\n\n"
                    f"👉 [Apri su Canva]({url})\n\n"
                    f"Da lì puoi aggiungere la foto della location, "
                    f"aggiustare i colori ed esportare il PDF.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "⚠️ Errore nella modifica Canva. Riprova o contatta il supporto."
                )

            # Reset conversazione
            context.user_data["history"] = []
            return RACCOLTA

        else:
            # Claude sta chiedendo altri dati
            await update.message.reply_text(risposta)
            return RACCOLTA

    except json.JSONDecodeError:
        await update.message.reply_text(risposta)
        return RACCOLTA
    except Exception as e:
        logger.error(f"Errore: {e}")
        await update.message.reply_text("⚠️ Si è verificato un errore. Riprova.")
        return RACCOLTA

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("❌ Operazione annullata. Mandami i dati quando vuoi!")
    return RACCOLTA

# ── Main ──────────────────────────────────────────────────────────────

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

    logger.info("Bot MB Luxury Events avviato!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
