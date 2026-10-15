# Free AI-text detectors (checked 2026-10-15)

Paid services are not used by these skills. What is left: local open-source models, which keep the
manuscript on the machine, and one hosted free tier. A detector's score is a hint for a reread, never
evidence of authorship and never a target (`detector-evidence.md`).

## The free options

| key | detector | where it runs | what it needs | evidence |
|---|---|---|---|---|
| `modernbert` | rasbt/ai-text-detector-modernbert (ModernBERT-base, 150M, up to 8,192 tokens, Apache-2.0) | local, CPU is fine | nothing (public model, ~0.6 GB) | trained on 2026 generators (Gemini 3.6 Flash, DeepSeek v4, Qwen 3.6, Kimi K3) with arXiv, PLOS and PMC human text; only in-distribution accuracy is published (99.71%) |
| `tropa` | tropa-mini, wasitaigeneratedcom/ai-text-detector-small (DeBERTa-v3-large, 434M, Apache-2.0) | local | nothing (public, ~1.7 GB) | four classes (human, ai, ai_edited, humanized); threshold 0.976 at a 0.5% false-positive rate on 6,930 human texts (vendor-run); flags 15.6% of non-native TOEFL essays |
| `editlens` | Pangram EditLens (pangram/editlens_roberta-large; CC-BY-NC-SA) | local | a Hugging Face token and manual access approval | estimates how much of a text was AI-edited (ICLR 2026, arXiv:2510.03154); not run by `detect.py` yet |
| `binoculars` | Binoculars (two Falcon-7B models, BSD-3 code) | local; ~28 GB of models, a 30 GB GPU or 64 GB RAM for CPU | install from https://github.com/ahans30/Binoculars | 0.1% false positives on 135,389 non-native academic texts in Park et al. 2026 (their normalisation); not run by `detect.py` |
| `aiornot` | AI or Not API, `POST https://api.aiornot.com/v2/text/sync` | hosted | `AIORNOT_API_KEY` (free: 1M words a month, 250 to 500,000 characters per call) | no independent evaluation found; docs say media "are processed and deleted immediately after inference", the privacy policy says nothing about training |

Not free, or not usable for unpublished text: GPTZero, Pangram's API, Originality.ai, Copyleaks (its sandbox
returns mock results), ZeroGPT, Hive, Grammarly, Turnitin (paid); Sapling, Winston AI and wasitaigenerated
(free trials that store or may use the text); Hugging Face Spaces demos (a third-party container with no
stated terms); old classifiers trained on 2019 to 2023 generators (the OpenAI RoBERTa detector,
Hello-SimpleAI, RADAR, MAGE), which Park et al. found to flag most human academic text.

## Accuracy, in short

- Park et al. 2026 (13 open detectors, human non-native academic text): false-positive rates from 0.1%
  (Binoculars) to 100% (log-rank); Fast-DetectGPT 25%, RADAR 76%, the OpenAI RoBERTa detector 94%.
  Professional editing moved scores in both directions.
- Epoch AI (July 2026): commercial detectors flagged none of 495 human passages, but missed about a quarter
  of scientific AI text written in an imitated style.
- The local classifiers above have little independent evaluation. Calibrate against the authors' own
  writing (`detect.py --sample`) rather than trusting a vendor threshold.

## How the skills use them

1. `detector_setup.py check`: which detectors are ready on this machine (token, GPU, memory, disk, cached
   models), a recommendation, and for anything missing the page to get it.
2. If a token or access is missing and the user wants that detector, provide the page. Open it when
   requested; no second confirmation is needed for the same request.
   `detector_setup.py open hf-token | editlens-access | aiornot-key` opens it where a browser is available,
   and prints the link otherwise.
3. `detect.py PAPER --detector modernbert --sample AUTHORS_EARLIER.md`: windows of 120 to 400 words,
   references and tables excluded, three states (flagged, not flagged, not assessed), the threshold set by
   the authors' own writing.
4. A hosted detector runs only with `--allow-remote`, and only after the authors agreed to send this text.
5. Flagged windows go to the critic in reflection mode as places to look. The fix is still a named smell or
   an unsupported claim; a window with neither stays as it is.
