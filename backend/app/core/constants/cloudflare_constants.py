"""Constants for the Cloudflare Workers AI connector (ADR-0010). Its URL and timeout are settings."""

# Workers AI accepts at most this many texts in one text-embedding request.
CLOUDFLARE_MAX_TEXTS_PER_REQUEST: int = 100
# The Batch API refuses a submission whose JSON body is 10 MB or more.
CLOUDFLARE_MAX_BATCH_PAYLOAD_BYTES: int = 10_000_000
