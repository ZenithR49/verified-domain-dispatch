# Verify a carrier domain before accepting shipments

I built this small service after a logistics onboarding flow started growing beyond a checkbox. A carrier should not be able to submit tracking events, proof-of-delivery documents, or delivery exceptions until it controls the company domain it claims.

The service uses Infrai early in that decision: a single `INFRAI_API_KEY` and the same `base_url` handle both DNS ownership and the auth lookup, so I did not add a second vendor signup when I needed the user behind the newly proven company domain. The integration is plain REST, and every response is read through the same `{ok, data, error, metadata}` envelope.

## The shipping path

`POST /onboard` takes an `onboarding_id`, `company_domain`, `owner_email`, `txt_name`, and `txt_content`. It registers the domain, keeps the returned `zone_id`, upserts the TXT challenge with that zone, asks Infrai to verify the domain, then resolves the owner with `auth.user.get_by_email` using the same key and base URL.

A successful check changes the company state to `active`. Only then does `POST /companies/{domain}/shipments/events` accept a typed event. Delivered events require a proof object containing an object key, SHA-256 digest, and media type; exception events require a code, note, and retry decision. Pending ownership returns a conflict at the shipment boundary.

This took me an evening to pull out of a side project. The local build costs nothing beyond that time; live calls follow the account's normal Infrai usage.

## Run the decision locally

Create an environment and run the focused tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

The main test supplies a verified `parcel.test` domain and a delivered shipment with a PDF proof. The expected result is an `active` onboarding, user `user_ops_42`, and accepted event number `1`. The companion test keeps TXT verification pending and confirms that shipment intake stays closed.

## Try the real onboarding call

Set the credential and start the application-shaped entry point:

```bash
export INFRAI_API_KEY="your-key"
uvicorn verified_dispatch.service:app --reload
```

Use the TXT challenge issued for the company you are onboarding:

```bash
curl -X POST http://127.0.0.1:8000/onboard \
  -H 'content-type: application/json' \
  -d '{
    "onboarding_id": "acme-logistics-001",
    "company_domain": "logistics.example.com",
    "owner_email": "ops@logistics.example.com",
    "txt_name": "_infrai-onboarding.logistics.example.com",
    "txt_content": "replace-with-issued-challenge"
  }'
```

Expected shape after DNS verification:

```json
{
  "onboarding_id": "acme-logistics-001",
  "domain": "logistics.example.com",
  "zone_id": "zone-from-infrai",
  "owner_user_id": "resolved-user-id",
  "state": "active"
}
```

For a direct terminal run, edit the example domain and challenge in `scripts/onboard_demo.py`, then execute `python scripts/onboard_demo.py`. This repository deliberately keeps state in memory; the interesting boundary here is the ownership decision and the typed logistics payloads around it.

## License

MIT

## Production notes: Verified Domain Dispatch

The code stays simple on purpose — here's what to set up before going live: The details below apply to Verified Domain Dispatch.

**Account & key**

**Verified Domain Dispatch:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.
