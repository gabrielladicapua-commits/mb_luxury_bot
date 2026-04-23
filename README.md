# MB Luxury Events — Bot Telegram

Bot per generare preventivi su Canva direttamente da Telegram.

## Configurazione su Railway

### Variabili d'ambiente richieste

Vai su Railway → il tuo progetto → Variables e aggiungi:

| Variabile | Valore |
|-----------|--------|
| `TELEGRAM_TOKEN` | Il token del tuo bot (da @BotFather) |
| `ANTHROPIC_API_KEY` | La tua API key di Anthropic |
| `CANVA_TOKEN` | Il token API di Canva |
| `CANVA_DESIGN_ITA` | `DAHHaCBY8Ks` (template italiano) |
| `CANVA_DESIGN_ENG` | `DAHGeHDN8_U` (template inglese) |

## Come usare il bot

Scrivi su Telegram i dati del preventivo in linguaggio naturale:

```
Marco & Sofia, 15 agosto 2026, Villa Rufolo Ravello (SA),
aperitivo quartetto acustico, dinner cool vibes band,
party velvet aura, totale 3.500€
```

Il bot:
1. Estrae i dati automaticamente
2. Modifica il template Canva
3. Ti manda il link diretto al design
4. Tu aggiungi la foto location e scarichi il PDF

## Comandi

- `/start` — Avvia il bot
- `/annulla` — Annulla l'operazione corrente

## Aggiungere nuove formazioni

Modifica il file `formazioni.json` aggiungendo una nuova voce nella lista.
