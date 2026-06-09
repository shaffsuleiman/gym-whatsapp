# Gym Trainer — FastAPI

A code-based port of the n8n Gym Trainer. One inbound webhook drives onboarding, meal logging,
food-photo analysis, macro/calorie + weight tracking, and on-demand progress charts. A separate
job sends daily "calories left" dinner reminders. Same MongoDB schema as the n8n build, so it can
share the same database.

## Architecture

```
POST /webhook/gym-trainer
  └─ normalize payload (phoneNumber, agentId, contactNumber, processedContent, image_url)
     └─ save contact (e164)  ── load profile + chat history
        └─ [if image] OpenAI vision → food analysis appended to the message
           └─ run_agent (gpt-5-mini, strict JSON structured output)
              ├─ persist: profile / meal / weight (per the agent's flags)
              └─ respond { "text", "image"? }   ← image = base64 PNG when wants_progress_chart
```

- `app/main.py` — FastAPI app, the webhook pipeline, reminder endpoint, optional scheduler.
- `app/agent.py` — system prompt, vision analysis, structured-output call.
- `app/schemas.py` — agent output models + the OpenAI JSON Schema (strict).
- `app/db.py` — MongoDB (`users`, `meals`, `weights`, `chat_histories`).
- `app/chart.py` — matplotlib weight chart with linear-trend prediction → base64 PNG.
- `app/platform.py` — outbound client for the WhatsApp `/api/send-message` API.
- `app/reminders.py` — daily dinner / calories-left job.

## Setup

```bash
cd gym-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in MONGODB_URI, OPENAI_API_KEY, PLATFORM_* 
uvicorn app.main:app --reload --port 8000
```

## Response format (matches your platform)

```json
{ "text": "Here is your weight progress 📈", "image": "<base64-png>" }
```
`image` is only included when the user asks to see progress and weight data exists.
`voice` / `pdf` are easy to add the same way.

## Test

```bash
# Onboarding / coaching
curl -s -X POST localhost:8000/webhook/gym-trainer -H 'Content-Type: application/json' \
  -d '{"phoneNumber":"193342281375976@lid","agentId":"agent008","contactNumber":"923091440655","contactName":"Shaff","processedContent":"hi"}'

# Progress chart
curl -s -X POST localhost:8000/webhook/gym-trainer -H 'Content-Type: application/json' \
  -d '{"phoneNumber":"193342281375976@lid","agentId":"agent008","contactNumber":"923091440655","processedContent":"show my progress"}'

# Trigger reminders manually
curl -s -X POST localhost:8000/tasks/dinner-reminders
```

## Reminders

- `ENABLE_SCHEDULER=true` runs an in-process APScheduler cron at `DINNER_REMINDER_HOUR:MINUTE` (`TIMEZONE`).
- Or keep it `false` and hit `POST /tasks/dinner-reminders` from your own cron / a platform scheduler.

## Notes

- `user_id = "{phoneNumber}:{agentId}"` — the same composite key as the n8n build.
- gpt-5 models reject a custom `temperature`, so none is set (parity with the n8n fix).
- To swap to Claude: replace the OpenAI calls in `app/agent.py` with the Anthropic SDK
  (use tool-use / a JSON schema for the structured output).
