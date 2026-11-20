Type: grilling
Status: open

## Question

What is the pairing/handshake protocol for two symmetric peers given only the other peer's IP address and a shared secret?

How do they mutually authenticate from the pre-shared secret, establish a session, handle both sides attempting to pair at once, reject a wrong secret, and re-pair later? The link is TCP with authenticated encryption keyed from the secret.
