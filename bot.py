"""
MB Luxury Events — Bot Telegram
Genera preventivi su Canva direttamente da Telegram
usando Claude API con connettore Canva.
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

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Env vars ─────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# ── Libreria formazioni ───────────────────────────────────────────────
with open("formazioni.json", "r", encoding="utf-8") as f:
    _lib = json.load(f)["mb_luxury_events"]["formazioni"]

FORMAZIONI_TESTO = "\n".join(
    f'- {f["nome_display"]} (id: {f["id"]}): {f["copy"][:80]}...'
    for f in _lib
)

# ── System prompt ─────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""Sei l'assistente di MB Luxury Events, agenzia di musica per eventi di lusso.

Il tuo compito è raccogliere i dati per un preventivo e poi modificare il template Canva corretto.

## Template Canva disponibili
- Italiano (nomi italiani): design ID = DAHHaCBY8Ks
- Inglese (nomi stranieri): design ID = DAHGeHDN8_U

## Formazioni disponibili
{FORMAZIONI_TESTO}

## Workflow
1. Quando l'utente ti fornisce i dati, estraili e confermagli la scaletta
2. Usa il tool Canva per aprire il template giusto (start-editing-transaction)
3. Modifica tutti i campi: nome sposi, data, location, formazioni, totale, footer
4. Fai il commit delle modifiche
5. Rispondi con il link al design Canva

## Campi da modificare nel template ITA (element_id)
- Nome sposi (cover): PBWyxWrvztPjyDtn-LB2BsQQS2MGmnD7M → "NOME & COGNOME wedding"
- Data + Location: PBWyxWrvztPjyDtn-LB0Sr05DnKGDwx4n → "Data\\nLocation"
- Footer p2: PB2MlGvVXNdZXJrv-LBLHQRf5hDdfSFGg → "Nome & Cognome Wedding"
- Footer p3: PBrk8D8hH58TKzVX-LBSZ4QJ8QCKMJWfx → "Nome & Cognome Wedding"
- Footer p4: PB3Py5lt3H1dkJjn-LBTpZrvncDtzLfDw → "Nome & Cognome Wedding"
- Aperitivo titolo momento: PB2MlGvVXNdZXJrv-LBp0xfHyJcmDMMCn
- Aperitivo formazione+copy: PB2MlGvVXNdZXJrv-LBfjX1Rdp8pq2xBP
- Dinner titolo momento: PB2MlGvVXNdZXJrv-LBgM1NhgvzxGHgfQ
- Dinner formazione+copy: PB2MlGvVXNdZXJrv-LB3fSS0Hq73tfyTZ
- After dinner titolo: PB2MlGvVXNdZXJrv-LBsHc9qWpFrdCm2X
- After dinner formazione+copy: PB2MlGvVXNdZXJrv-LBnbkKBzp2XTmJs4
- Taglio torta titolo: PB2MlGvVXNdZXJrv-LBGDNC6K4BjKZ6N6
- Taglio torta formazione+copy: PB2MlGvVXNdZXJrv-LBT26ZWlm8wwk99K
- Fee riga 1: PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-A1
- Fee riga 2: PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-A3
- Fee riga 3: PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-WBt--_gfGpm7Qxh3A:mj7900ec:0
- Totale importo: PB3Py5lt3H1dkJjn-LBCgrNSvWwRRSlsF-tdzihiU1N3bwUJEsA:mmaxlxx8:1

## Regole
- Se il preventivo è in italiano, traduci i copy ENG in italiano
- Se è in inglese, traduci i copy ITA in inglese
- La sezione Voices nella pagina 3 va inclusa solo se l'utente la specifica
- Rispondi sempre in italiano all'utente
- Dopo il commit, dai il link diretto: https://www.canva.com/design/[DESIGN_ID]/edit
"""

# ── Client Anthropic ──────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Stati ─────────────────────────────────────────────────────────────
RACCOLTA = 1

# ── Chiama Claude con MCP Canva ───────────────────────────────────────
async def chiama_claude(messages: list) -> str:
    """Chiama Claude API con il connettore Canva MCP."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            mcp_servers=[
                {
                    "type": "url",
                    "url": "https://mcp.canva.com/mcp",
                    "name": "canva"
                }
            ]
        )

        # Estrai tutto il testo dalla risposta
        testo = ""
        for block in response.content:
            if hasattr(block, "text"):
                testo += block.text

        return testo.strip() or "✅ Operazione completata."

    except Exception as e:
        logger.error(f"Errore Claude: {e}")
        return f"⚠️ Errore: {str(e)}"

# ── Handler Telegram ──────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text(
        "👋 Ciao! Sono il bot di *MB Luxury Events*.\n\n"
        "Mandami i dati del preventivo, ad esempio:\n\n"
        "_Marco & Sofia, 15 agosto 2026, Villa Rufolo Ravello (SA), "
        "aperitivo quartetto acustico, dinner cool vibes band, "
        "party velvet aura, taglio torta sax bar, totale 3.500€_\n\n"
        "Posso chiederti i dati mancanti se non li fornisci tutti.",
        parse_mode="Markdown"
    )
    return RACCOLTA

async def raccolta_dati(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = update.message.text

    if "history" not in context.user_data:
        context.user_data["history"] = []

    context.user_data["history"].append({"role": "user", "content": testo})

    await update.message.reply_text("⏳ Elaboro e modifico il template su Canva...")

    risposta = await chiama_claude(context.user_data["history"])

    context.user_data["history"].append({"role": "assistant", "content": risposta})

    await update.message.reply_text(risposta, parse_mode="Markdown")
    return RACCOLTA

async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("❌ Annullato. Mandami i dati quando vuoi!")
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
    logger.info("🎵 Bot MB Luxury Events avviato!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
