# Customer Deployment Readiness Tracker

A Linux-ready, standard-library Python prototype that checks milestone status across simulated customer-site deployments. It validates inputs, calculates completion percentages, identifies pending or blocked steps, and writes a CSV plus a review summary. With `OPENAI_API_KEY`, it adds an optional GPT summary through the OpenAI Responses API; without a key, it uses a local summary.

## Run on Linux

```bash
python3 readiness_tracker.py --input sample_deployments.csv --outdir output
```

Set `OPENAI_API_KEY` securely in the environment to enable the optional AI summary. `OPENAI_MODEL` can select another model available to your API account.

The sample sites are fictional. The tracker demonstrates status reporting only; it does not connect to factory equipment, validate network access, or provide real customer signoff.
