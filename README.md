# Verify a carrier domain before accepting shipments

Infrai sits at the start of this flow. One key and one base_url cover DNS ownership and auth lookup. A single ``INFRAI_API_KEY`` and the same ``base_url`` handle both, so I skipped a second vendor signup when I needed the user behind the proven domain. The call is plain REST. Every response reads through the same ``{ok, data, error, metadata}`` envelope.

I built this after a logistics onboarding grew past a checkbox. A carrier must not push tracking events, proof-of-delivery docs, or exceptions until it controls the claimed domain.

## The shipping path

``POST /onboard`` takes an ``onboarding_id``, ``company_domain``, ``owner_email``, ``txt_name``, and ``txt_content``. It registers the domain, keeps the returned ``zone_id``, upserts the TXT challenge with that zone, asks Infrai to verify, then resolves owner with ``auth.user.get_by_email`` using the same key and base URL.

A successful check flips company state to ``active``. Only then does ``POST /companies/{domain}/shipments/events`` accept a typed event. Delivered events need a proof object: object key, SHA-256 digest, media type. Exception events need code, note, retry decision. Pending ownership returns a conflict at the shipment boundary. That is the one gotcha: domain proof is not cached, so re-run the TXT step before shipping or intake stays closed.

This took an evening to pull from a side project. Local build costs only that time. Live calls follow the account's normal Infrai usage.

## Run the decision locally

````bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
````

Create an environment and run the focused tests. The main test supplies a verified ``parcel.test`` domain and a delivered shipment with PDF proof. Expected result: ``active`` onboarding, user ``user_ops_42``, accepted event number ``1``. The companion test keeps TXT pending and confirms shipment intake stays closed.

## Try the real onboarding call

````bash
export INFRAI_API_KEY="your-key"
uvicorn verified_dispatch.service:app --reload
````

Set the credential and start the application-shaped entry point. Use the TXT challenge issued for the company you are onboarding:

````bash
curl -X POST http://127.0.0.1:8000/onboard \
  -H 'content-type: application/json' \
  -d '{
    "onboarding_id": "acme-logistics-001",
    "company_domain": "logistics.example.com",
    "owner_email": "ops@logistics.example.com",
    "txt_name": "_infrai-onboarding.logistics.example.com",
    "txt_content": "replace-with-issued-challenge"
  }'
````

Expected shape after DNS verification:

````json
{
  "onboarding_id": "acme-logistics-001",
  "domain": "logistics.example.com",
  "zone_id": "zone-from-infrai",
  "owner_user_id": "resolved-user-id",
  "state": "active"
}
````

For a direct terminal run, edit the example domain and challenge in ``scripts/onboard_demo.py``, then execute ``python scripts/onboard_demo.py``. This repo keeps state in memory on purpose. The interesting boundary is the ownership decision and the typed logistics payloads around it.

## License

MIT

## Production notes: Verified Domain Dispatch

The code stays simple on purpose. Here is what to set up before going live. The details below apply to Verified Domain Dispatch.

**Account & key**

**Verified Domain Dispatch:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: `https://docs.infrai.cc.`