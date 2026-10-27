# Seed data (private)

The real `customer_records.json` is **not committed** to this repository because
it contains customer names, plate numbers, and addresses. Keep it local or mount
it as a secret at deploy time.

## File format

A JSON array of rows. Each row has seven strings:

```json
["visit_date", "record_no", "plate", "model", "customer_name", "address", "technician"]
```

`visit_date` must be `YYYY-MM-DD` and `record_no` must be numeric; other rows are
ignored. The importer deduplicates on the complete row, so re-running it is safe.

`customer_records.example.json` is a small synthetic sample you can copy while
developing:

```powershell
Copy-Item f2m\data\customer_records.example.json f2m\data\customer_records.json
python run.py
```

## Using a file from another location

Set `SEED_DATA_FILE` to an absolute or relative path:

```powershell
$env:SEED_DATA_FILE = "C:\secure\customer_records.json"
python run.py
```

On Render, upload the JSON as a **Secret File** (Dashboard → your service →
Environment → Secret Files) and set:

```text
SEED_DATA_FILE=/etc/secrets/customer_records.json
```

If the app started before the file was available, import it without wiping the
database:

```powershell
flask --app wsgi seed-db --force
```

`flask --app wsgi reset-data` also re-imports, but it deletes all existing data.
