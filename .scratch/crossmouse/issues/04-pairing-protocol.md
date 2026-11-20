Type: grilling
Status: resolved

## Answer

Human opted out of ticket grilling; calls made by the executor and recorded in the map's Notes and `README.md`: config-fixed connector/listener; fixed configurable port; PBKDF2-HMAC-SHA256 + salted AES-GCM handshake probe; explicit pairing mode with no extra identity pinning.

## Question

What is the pairing/handshake protocol for two symmetric peers given only the other peer's IP address and a shared secret?

How do they mutually authenticate from the pre-shared secret, establish a session, handle both sides attempting to pair at once, reject a wrong secret, and re-pair later? The link is TCP with authenticated encryption keyed from the secret.
