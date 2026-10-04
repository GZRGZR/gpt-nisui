# Gemini Live phone bridge

This repository now contains a SIP phone bridge between Yemot HaMashiach and Gemini Live.

Flow:

Phone -> Yemot SIP -> Asterisk -> AudioSocket -> Gemini Live -> Asterisk -> Phone

## Requirements

- A Yemot account/line with SIP access.
- A Linux VPS with a public IP.
- Docker and Docker Compose.
- A Gemini API key.

## Setup

1. Copy .env.example to .env.
2. Fill in the Yemot SIP credentials, public IP, and Gemini API key.
3. Start the stack:

   docker compose up -d --build

4. Check logs:

   docker compose logs -f

The Asterisk container uses the current community Asterisk image from andrius/asterisk and its built-in envsubst support for rendering the SIP templates.

## Network

The Compose file uses host networking because SIP/RTP is sensitive to NAT and port mapping. Protect the server with a firewall. SIP uses UDP 5060 and Asterisk uses the RTP range configured in asterisk/rtp.conf.

The AudioSocket bridge binds to localhost by default.

## Gemini Live

The bridge sends raw PCM audio to Gemini Live and receives 24 kHz PCM audio back. The phone side is 8 kHz PCM, so the bridge performs the sample-rate conversion.

The default model is gemini-3.8-live and the default voice is Kore.

## Secrets

Never commit .env. The Gemini key stays on the server and is not sent to callers.

## Yemot

Configure the Yemot system so incoming calls are routed to the SIP account registered by Asterisk. Use the exact SIP credentials shown in your Yemot account.
