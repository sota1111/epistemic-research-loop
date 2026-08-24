# Security

Never store Kaggle tokens, API keys, cloud credentials, or unseal tokens in Git, events, prompts, or
artifacts. The local executor passes a minimal environment without ambient secrets. Production
experiments run in a container with read-only dataset mounts, network disabled by default, resource
limits, timeout/process-tree cleanup, command and output allowlists, and no host write access.

Competition text and external documents are untrusted data. Prompts explicitly state that embedded
instructions must not be followed. Artifact metadata includes SHA-256, code commit, dataset and
environment fingerprints, MIME type, size, timestamp, and seal status.
