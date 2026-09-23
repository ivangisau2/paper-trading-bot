# Bot de Paper Trading con IA en la nube

Réplica del bot del vídeo de Adrián Sáenz, corriendo en **OpenCode sin suscripción a Claude**,
alojado en **Hugging Face Spaces** (gratis, 24/7 sin encender tu PC).

> ⚠️ **Modo paper trading**: todo el dinero es simulado ($1,000 iniciales). No hay conexión
> a ningún exchange real. Esto es un experimento, no una fuente de ingresos garantizada.

## Proveedor de IA (variable `AI_PROVIDER`)

| Valor | Servicio | Requisito |
|---|---|---|
| `groq` | Groq API (Llama 3.3 70B), gratis | `GROQ_API_KEY` |
| `gemini` | Google Gemini Flash, gratis | `GEMINI_API_KEY` |
| `ollama` | Ollama local (futuro Raspberry Pi) | `OLLAMA_URL` opcional |
| `none` | Sin IA: solo estrategia técnica | — |

**Si la IA se queda sin tokens o falla, el bot sigue operando con la estrategia sola.**
Sin `AI_PROVIDER` definido, se deduce de las claves presentes.

## Arquitectura (mismo pipeline que el vídeo)

```
Datos (Kraken API pública — el bot; el dashboard usa Binance en el navegador)
  → Motor de datos (ordena OHLCV)
    → Indicadores (RSI, MACD, EMA, Bollinger, ATR, volumen)
      → Filtro y controles (volumen, volatilidad, extremos)
        → Analista IA (Groq Llama 3.3 70B / Ollama local) — puede vetar o confirmar
          → Motor de riesgo (tamaño por ATR × agresividad)
            → Ejecución simulada (compra/venta paper)
              → Posición (vigila SL/TP, long y short)
```

## Despliegue en la nube: GitHub Actions + Pages (gratis, sin PC encendida)

Los ciclos los ejecuta **GitHub Actions cada 15 min** y el estado se guarda como
commits en el repo. El dashboard vive en **GitHub Pages** y lee el estado vía
`raw.githubusercontent` + precios en vivo de Binance (CORS abierto).

```bash
# 1. Requisitos: gh (CLI de GitHub) autenticado
gh auth login --hostname github.com --git-protocol https --web

# 2. Crear repo, subir código y activar Pages (lo hace el agente o tú a mano)
gh repo create paper-trading-bot --public --source=. --push
gh api -X POST repos/{owner}/paper-trading-bot/pages -f "source[branch]=main" -f "source[path]=/"

# 3. Secreto de la IA (gratis en console.groq.com/keys)
gh secret set GROQ_API_KEY
```

- **Repo público recomendado**: Actions es ilimitado en públicos (en privados
  solo hay 2.000 min/mes, justo el límite). El estado es dinero simulado.
- **Fuente de datos del bot: Kraken** (`EXCHANGE=kraken`, por defecto). Binance
  bloquea las IPs de EE.UU. con HTTP 451 y los runners de GitHub Actions están
  en EE.UU. Kraken es legal allí, API pública sin key y con los mismos OHLCV.
  (BNB no existe en Kraken → se opera UNI en su lugar.)
- El dashboard en GitHub Pages sigue usando Binance en el navegador (IP del
  usuario, sin bloqueo) y el HTML se llama `index.html` (lo que Pages sirve).
- **Sin GROQ_API_KEY** el bot funciona igual, solo que decide con la estrategia
  técnica sin el veto de la IA (nunca se para por falta de IA).
- ⚠️ GitHub retrasa a veces el cron unos minutos: el contador del dashboard lo
  muestra como "esperando cron..." (hasta 5 min) y luego "retrasado".
- `storage.py` (respaldo HF) queda inactivo: el estado ya vive en commits.

## Uso

```bash
python3 bot.py cycle        # un ciclo de análisis
python3 bot.py loop 15      # bucle automático cada 15 min
python3 bot.py report       # estado, equity, win rate
python3 bot.py closeall     # modo "solo cierre"
python3 bot.py reflect      # IA revisa trades y escribe APRENDIDO.md
```

## Fases (como el vídeo)

1. **Fase 1 — Investigación** ✅ (resumida de fuentes públicas)
2. **Fase 2 — Construcción** ✅ (este código)
3. **Fase 3 — Paper trading** ⏳ dejar correr días y documentar resultados
4. **Fase 4 — Reflexión** `bot.py reflect` periódicamente
5. *(Dinero real: solo si los resultados son buenos — y con los riesgos asumidos)*

## Aprendizaje

`trades.jsonl` registra cada operación. `bot.py reflect` hace que la IA analice los
trades recientes y escriba lecciones en `APRENDIDO.md` (la zona "va aprendiendo" del vídeo).

## Configuración

Todo en `config.py`: 16 criptos, agresividad (1-10), riesgo por operación,
número máximo de posiciones, umbrales de filtros, modelo de IA.
