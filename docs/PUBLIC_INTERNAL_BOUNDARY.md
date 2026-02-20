# Public/Internal Boundary

`bio-sim` is a public OSS repository.

## Allowed (public)
- Runtime/library source code
- Technical design docs and API contracts
- Testing strategy and quality docs
- Example models/templates intended for public use

## Not allowed (internal only)
- Business cases, pricing, GTM, investor/fundraising content
- Competitive strategy and commercial forecasts
- Internal operating procedures and non-public incident reports
- Secrets, service-account keys, credentials, tokens

## Enforcement
- CI blocks commits containing common business-sensitive terms in docs.
- CI blocks commits containing detected secrets.
- Internal planning docs are stored in `biosim-platform`.
