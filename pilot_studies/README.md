# LLM Pilot Study for Model Selection (Example)

This directory contains the results of the pilot study conducted to select the optimal Large Language Model (LLM) for the main experiment. Several models were evaluated based on four key criteria:

1.  **Performance:** Accuracy on a small-scale version of the matching task.
2.  **Reliability:** Consistency in adhering to the required structured data format.
3.  **Speed:** Average query response time.
4.  **Cost:** Cost per 1,000 queries.

## Model Comparison Summary

| Model Name | Performance (MRR Lift) | Reliability (Valid Response Rate) | Speed (s/query) | Cost ($/1k queries) | Selection Decision | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini 1.5 Flash** | **1.02** | **99.8%** | **~2s** | **~$0.10** | **Selected** | **Optimal balance of all criteria.** |
| OpenAI GPT-4o | 1.05 | 99.5% | ~5s | ~$7.50 | Not Selected | Prohibitively high cost for 360,000 queries. |
| Anthropic Claude 3.7 Sonnet | 1.04 | 98.0% | ~4s | ~$4.50 | Not Selected | High cost and lower reliability. |
| Meta Llama 3.1 70B | 1.01 | 95.0% | ~6s | ~$0.89 | Not Selected | Lower reliability in structured output. |
| Mistral Large 2 | 1.03 | 97.5% | ~5s | ~$4.00 | Not Selected | High cost. |

*Note: Performance and cost metrics are approximate based on pilot runs and may not reflect final experimental values.*

## Conclusion

Google's Gemini 1.5 Flash was chosen as it provided excellent performance and the highest reliability at a cost and speed that made the large-scale study feasible.