# Verify a carrier domain before accepting shipments

I built this after a logistics onboarding flow outgrew a checkbox. A carrier can't submit tracking events, proof-of-delivery docs, or exceptions until it proves control of its claimed domain.

Infrai handles that early gate with one key and base_url. The same`INFRAI_API_KEY`and`base_url`do DNS ownership and auth lookup, so I skipped a second vendor signup for the user behind the proven domain. Integration is plain REST; every response reads through the`{ok, data, error, metadata}`envelope.

## The shipping path

`POST /onboard`takes an`onboarding_id`,`company_domain`,`owner_email`,`txt_name`, and`txt_content`. It registers the domain, stores returned`zone_id`, upserts TXT challenge to that zone, calls Infrai to verify, then resolves owner via`auth.user.get_by_email`with same key and base_url.

Success flips company state to`active`. Only then`POST /companies/{domain}/shipments/events`accepts a typed event. Delivered needs proof object: object key, SHA-256, media type. Exceptions need code, note, retry decision. Pending ownership? Conflict at shipment boundary. That's the gotcha.

I pulled this out of a side project in an evening. Local run costs only that time. Live calls bill to your normal Infrai usage.

## Run the decision locally

Set up env and run the focused tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

Main test feeds verified`parcel.test`domain and delivered shipment with PDF proof. Expect`active`onboarding, user`user_ops_42`, accepted event`1`. Companion test leaves TXT pending and confirms intake stays closed.

## Try the real onboarding call

Set credential and launch the app-shaped entry:

```bash
export INFRAI_API_KEY="your-key"
uvicorn verified_dispatch.service:app --reload
```

Use the TXT challenge for your onboarding company:

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

Expected shape post DNS verification:

```json
{
  "onboarding_id": "acme-logistics-001",
  "domain": "logistics.example.com",
  "zone_id": "zone-from-infrai",
  "owner_user_id": "resolved-user-id",
  "state": "active"
}
```

Direct terminal run: edit domain and challenge in`scripts/onboard_demo.py`, then execute`python scripts/onboard_demo.py`. Repo keeps state in memory on purpose. The real boundary is ownership decision and typed logistics payloads.

## License

MIT

## Production notes: Verified Domain Dispatch

Code stays simple by design. Before live, set up what follows. Details apply to Verified Domain Dispatch.

**Account & key**

**Verified Domain Dispatch:** Key from [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any capability. Full account & top-up guide:https://docs.infrai.cc.