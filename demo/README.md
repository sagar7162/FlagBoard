# FlagBoard customer demo

This storefront consumes the existing FlagBoard evaluation API. It is separate from the admin dashboard so the demo shows the real product effect: a customer-facing checkout experience changes when a feature flag changes.

## Run it

Start the backend:

```bash
uvicorn app.main:app --reload
```

Add the demo origin to `CORS_ALLOWED_ORIGINS` in `.env` if it is not already present:

```dotenv
CORS_ALLOWED_ORIGINS=["http://localhost:5500","http://127.0.0.1:5500","http://localhost:5501","http://127.0.0.1:5501"]
```

Restart the backend, then serve this folder:

```bash
python -m http.server 5501 --directory demo
```

Open `http://localhost:5501`, create a production API key in the FlagBoard dashboard, and paste the raw key into the demo. The default flag key is `new_checkout_flow`.

Toggle the flag in the dashboard. The storefront polls the evaluation endpoint every 1.5 seconds and changes between the classic and new checkout experiences. You can also set a `plan equals pro` rule and switch between the Pro and Free customer buttons.

The raw key is stored only in this browser's local storage for convenience. This is suitable for a local academic demonstration only; a production browser application should not expose an evaluation secret.
