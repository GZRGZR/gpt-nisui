# Gemini Live phone bridge

This project is a self-hosted SIP phone bridge between Yemot HaMashiach and Gemini Live.

Call flow:

Phone -> Yemot SIP -> Asterisk -> AudioSocket -> Gemini Live -> Asterisk -> Phone

## Required accounts and equipment

- A Yemot system with a SIP account enabled.
- An Oracle Cloud account to create an Always Free VM (or another Linux VPS).
- A Gemini API key from Google AI Studio.
- Docker and Docker Compose on the cloud VM.

## Privacy and billing — read before deploying

- The bridge does not print user or Gemini transcripts to the application logs by default.
- The Gemini API key and SIP password must be stored only in the server's `.env` file. Never commit `.env` to GitHub.
- This bridge sends the call audio and conversation context to Google's Gemini API. On unpaid Gemini API quota, Google may use prompts and responses to improve products and may send content to human reviewers. Do not discuss sensitive or confidential matters on the free tier.
- Google Search is enabled by default for current-news questions. Search grounding availability and quotas depend on the Gemini project/tier. If you want to avoid web searches, set `ENABLE_GOOGLE_SEARCH=false` in `.env`.
- Use Oracle resources explicitly labeled Always Free. Oracle says idle Always Free compute instances may be reclaimed. It also may require a card for account verification. Do not upgrade to a paid plan if you cannot accept any possible charges.
- No hosting provider can guarantee both zero cost and uninterrupted 24/7 SIP service on a free tier.

## Deploy

1. Copy `.env.example` to `.env`.
2. Enter the SIP credentials supplied by Yemot and the Gemini API key.
3. Set `ASTERISK_EXTERNAL_IP` to the VM's public IPv4 address.
4. Start:

   ```bash
   docker compose up -d --build
   ```

5. Inspect logs without exposing secrets:

   ```bash
   docker compose logs --tail=100
   ```

The Compose file uses host networking so SIP/RTP ports can be handled directly by Asterisk. The app's AudioSocket listener binds to loopback only; the Asterisk dialplan connects to `127.0.0.1:9019`.

## Firewall

Asterisk needs UDP 5060 and the RTP range in `asterisk/rtp.conf` (currently 10000–10100). Do not open the AudioSocket port 9019 to the internet.

Before opening UDP 5060 globally, ask Yemot support for their current complete SIP/RTP source IP ranges and restrict the ingress rules to those ranges where possible. Community posts report that the list can change and may contain many addresses; do not rely on a short list copied from a forum.

Also:
- Keep SSH restricted to your own current IP or use a cloud console.
- Do not add any dialplan routes that let unauthenticated callers place outbound calls.
- Use the SIP credentials from Yemot's official account screen and keep the API key out of logs.

## Live news

The Gemini Live session can be configured with the built-in Google Search tool. `ENABLE_GOOGLE_SEARCH=true` enables that option. Search quota and billing rules are controlled by Google and should be checked for the API project before making it available to callers.

## Status

The code and deployment templates have been updated, but the actual phone call has not been tested against the user's Yemot account or cloud VM. Treat first deployment as a test and verify SIP registration, inbound call routing, two-way audio, and current-news searches before relying on it.
