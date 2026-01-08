# 🧠 Claude Model Selection Strategy

IncidentFox uses **Claude 4.5** models from Anthropic for failure analysis.

## Default: Claude Sonnet 4.5

**Model ID:** `claude-sonnet-4-5-20250929`

**Why Sonnet 4.5 by default?**

✅ **Excellent for our use case:**
- Strong coding and technical analysis capabilities
- Fast response times (critical for incident response)
- Cost-effective at $3/MTok input, $15/MTok output
- 200K token context window (sufficient for deployment logs)
- Exceptional at pattern recognition and structured output

✅ **Deployment failure analysis doesn't need maximum intelligence:**
- Most failures are deterministic (missing env vars, port mismatches, etc.)
- We use regex patterns first, LLM for explanation
- Sonnet 4.5 excels at this type of technical troubleshooting

✅ **Speed matters:**
- Developers want immediate feedback when deployments fail
- Sonnet is ~2x faster than Opus
- Faster analysis = faster MTTR (mean time to resolution)

## Optional: Claude Opus 4.5 Fallback

**Model ID:** `claude-opus-4-5-20251101`

**When to use Opus:**

🎯 **For complex, low-confidence failures:**
- Pattern matching has low confidence (<60% by default)
- Multiple conflicting failure signals
- Novel failure modes not in our patterns
- Requires deeper reasoning about system interactions

⚙️ **Configuration:**

In `.env`:
```bash
# Enable Opus for low-confidence cases
USE_OPUS_FOR_COMPLEX=true

# Confidence threshold (0-100)
# Below this, use Opus instead of Sonnet
OPUS_CONFIDENCE_THRESHOLD=60
```

⚠️ **Trade-offs:**
- **More intelligent:** Better at complex reasoning, edge cases
- **Slower:** ~2x latency compared to Sonnet
- **More expensive:** $5/MTok input, $25/MTok output (vs $3/$15 for Sonnet)

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Fails                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            Pattern Detection (Regex)                         │
│  - Check for known failure patterns                          │
│  - Calculate confidence score (0-100)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ Confidence?   │
              └───────┬───────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
  High (≥60%)                  Low (<60%)
        │                           │
        ▼                           ▼
┌───────────────┐          ┌────────────────┐
│  Sonnet 4.5   │          │  Opus 4.5?     │
│  (Default)    │          │  (If enabled)  │
│               │          │                │
│  Fast         │          │  More careful  │
│  Cost-eff     │          │  Deeper        │
└───────────────┘          └────────────────┘
        │                           │
        └──────────┬────────────────┘
                   ▼
         ┌──────────────────┐
         │  Analysis Result │
         │  - Summary       │
         │  - Root cause    │
         │  - Fix steps     │
         └──────────────────┘
```

## Pricing Comparison

### Typical deployment failure analysis:

**Input:** ~2,000 tokens (logs + evidence)
**Output:** ~500 tokens (analysis)

| Model | Input Cost | Output Cost | Total | Latency |
|-------|-----------|-------------|-------|---------|
| **Sonnet 4.5** | $0.006 | $0.0075 | **$0.0135** | ~2s |
| **Opus 4.5** | $0.010 | $0.0125 | **$0.0225** | ~4s |

**Cost difference:** ~$0.01 per analysis (~67% more expensive)

For 1,000 analyses/month:
- Sonnet only: $13.50/month
- Opus only: $22.50/month
- Mixed (80% Sonnet, 20% Opus): $15.30/month

## Recommendation

**For this demo/MVP:**
- ✅ Keep `USE_OPUS_FOR_COMPLEX=false` (Sonnet only)
- ✅ Our failure patterns are well-defined
- ✅ Speed and cost matter more than marginal intelligence gains

**For production at scale:**
- Enable Opus fallback if you see complex edge cases
- Monitor confidence scores in logs
- Adjust `OPUS_CONFIDENCE_THRESHOLD` based on your needs
- Consider using Opus only for critical production deployments

## Model Performance

Based on Anthropic's benchmarks:

| Task | Sonnet 4.5 | Opus 4.5 | Improvement |
|------|-----------|----------|-------------|
| **Coding (SWE-bench)** | 49.8% | 61.4% | +23% |
| **Graduate-level reasoning (GPQA)** | 65.0% | 72.8% | +12% |
| **Code generation (HumanEval)** | 93.7% | 93.2% | -0.5% |
| **Instruction following** | 84.5% | 96.4% | +14% |

**For our use case (code/log analysis):**
- Sonnet is already excellent (93.7% on code tasks)
- Opus marginal gain doesn't justify 2x cost/latency for most cases
- Pattern-based detection handles most common failures

## Monitoring

Watch these metrics to decide if you need Opus:

```bash
# Check confidence distribution
grep "confidence" app.log | jq '.confidence' | sort -n | uniq -c

# See how many would use Opus
grep "confidence" app.log | jq 'select(.confidence < 60)' | wc -l

# Check current model usage
grep "anthropic_analysis_complete" app.log | jq '.model' | sort | uniq -c
```

If you see:
- **Many low-confidence (<60%) analyses:** Enable Opus fallback
- **Users reporting incorrect diagnoses:** Lower threshold to 70-80%
- **Most analyses >80% confidence:** You're fine with Sonnet only

## Customization

Want to tune for your needs?

```bash
# More aggressive Opus usage (use for anything <80% confidence)
OPUS_CONFIDENCE_THRESHOLD=80

# Only use Opus for very uncertain cases (<40%)
OPUS_CONFIDENCE_THRESHOLD=40

# Always use Sonnet (fast & cheap)
USE_OPUS_FOR_COMPLEX=false

# Always use Opus (maximum intelligence, cost be damned)
CLAUDE_MODEL=claude-opus-4-5-20251101
```

## Summary

**TL;DR:**
- 🏆 **Sonnet 4.5 is the right choice** for 95% of deployment failures
- 🎯 **Opus 4.5 is available** for the rare complex case
- 💰 **Cost-effective:** $0.01/analysis with Sonnet vs $0.02 with Opus
- ⚡ **Fast:** 2s response time with Sonnet vs 4s with Opus
- 📊 **Monitor confidence** and adjust threshold as needed

**Current configuration:** Sonnet only (no Opus fallback)
- Perfect for this demo
- Can enable later if needed
