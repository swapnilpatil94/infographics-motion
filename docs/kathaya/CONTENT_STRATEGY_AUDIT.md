# Content strategy audit: money psychology / scam-awareness channel

Written after the narration-pacing and prop-geometry fixes in this session. It maps the renderer's actual vocabulary (`kathaya/renderer/manifest.py`, generated from the code, not aspirational) against the kinds of scam / money-psychology stories a channel in this niche typically wants to cover, so the answer is "what can this system uniquely do today" rather than "what could a video generator in general do."

## What actually makes this different from a typical AI-shorts scam channel

Most channels in this niche are either a talking head, stock B-roll over a voice-over, or a generic AI-avatar reading a script. This system is neither:

1. **A drawn, consistent visual style** (Ink-line 2.5D characters + a hand-drawn "notebook page" look for data cards) that is nobody else's default AI-video look, and stays the same video to video - a real brand asset if kept consistent.
2. **Animated data visualisation as a first-class shot type**, not an afterthought: `VISUALIZE_FLOW` (money moving between accounts, now colour-coded and synced to the exact rupee figure the narrator says) and the amount callouts added this session. Very few scam-story channels actually *animate where the money goes* - most just show a chat screenshot. This is the single most differentiated capability the system has right now.
3. **Deterministic, capability-checked rendering.** A story that asks for something the system cannot do fails loudly (`capability_error` / `MISSING` asset) instead of quietly drawing the wrong thing. For a channel whose whole premise is "get the facts right so people don't get scammed," a system that cannot silently put a bank scene at night when the bank data only exists by day, or invent a landmark it doesn't have, is a real trust asset, not just an engineering nicety.
4. **No real logos, brands or faces are generated** - already true of the system (fictional sender ids, generic props) - which matters for a channel that will inevitably depict real institutions (banks, UPI, government departments) without defaming or impersonating them.

## Category-by-category fit (against the actual manifest: 12 environments, 15 archetypes, 36 actions, 12 props, 8 effects)

| scam category | fit today | why |
|---|---|---|
| Fake lottery / prize-fee scam | **Strong** | proven this session: bedroom -> phone alert -> insert screen -> money-flow -> resolve. Nothing missing. |
| Fake bank / OTP / KYC-update call | **Strong** | proven this session across 4 environments (bedroom, ATM, bank, cyber cell). `PHONE_CALL`, `INSERT_SCREEN`, `VISUALIZE_FLOW`, `bank`/`atm`/`police` environments and `bank employee` archetype all exist. |
| Fake delivery / customs-fee scam | **Strong, untested** | `delivery_worker` archetype and `door` prop exist specifically for this; `living_room`/`street` environments fit. Worth being the next acceptance story - it is very likely to work first try. |
| Fake job / work-from-home advance-fee scam | **Strong, untested** | `call_center`/`office` environments, `student`/`office worker`/`customer` archetypes, `INSERT_SCREEN` for the WhatsApp "task" messages, `VISUALIZE_FLOW` for the "registration fee" all already fit. |
| Government-scheme impersonation (fake tax refund, fake EPFO/Aadhaar message) | **Strong, untested** | same shape as the lottery story - only the fictional sender name changes. |
| Loan / EMI mis-selling, insurance mis-selling | **Moderate** | `bank`/`office`, `READ_DOCUMENT`, `document`/`pen` props, `bank employee` archetype all fit the "signing something you didn't understand" beat. What's missing is a way to show *numbers on a document* (interest rate, hidden charges) as clearly as `VISUALIZE_FLOW` shows money moving - currently that would just be a static `document` prop, which is weaker than the system's own money-flow visualisation. |
| Ponzi / MLM social-pressure schemes | **Moderate** | `CONVERSE`, `GIVE_OBJECT`/`RECEIVE_OBJECT`, `cafe`/`office` fit a two-person pitch. The cast cap (1 protagonist + 1 partner + 2 extras) and the fact `CROWD_WATCH` is only a background reaction, not a real crowd, means the "whole room believes it" feeling of an MLM meeting cannot really be shown - it will read as two people talking, which undersells the social-proof mechanism that makes this scam work. |
| UPI / QR-code "collect request" scam | **Moderate** | `INSERT_SCREEN` can carry a payment-request message, but there is no purpose-built UPI/QR visual - it will look like a generic phone message, not a recognisable payment app screen. Buildable as a second `INSERT_SCREEN` variant (see Recommendations). |
| Fake tech-support / remote-access scam | **Weak-moderate** | `TYPE_LAPTOP` and `laptop` exist, but `INSERT_SCREEN` is a phone-shaped card (see code note below) - a laptop pop-up / remote-cursor takeover has no visual vocabulary yet. |
| Fake trading-app / crypto "profit screenshot" scam | **Weak** | this is one of the most common current scam formats and the system has no fit for it: no candlestick chart, no fake portfolio dashboard. `VISUALIZE_FLOW` is a network diagram, not a line chart. A real gap - and a natural *second* procedural visual type, since `VISUALIZE_FLOW`/`INSERT_SCREEN` already prove that "an animated data card as a shot" works and passes QC. |
| "Digital arrest" (fake police video call) | **Weak** | this is one of the fastest-growing scam formats in India right now and currently has no fit: no video-call framing (picture-in-picture, ringing state), and the `police` environment can only be the victim's own later, real visit to a real station - it cannot play the scammer's side. High topical value, currently unbuildable without a new capability. |
| Romance / matrimonial scam | **Weak, but maybe deliberately** | no dating-profile or video-call visual exists. This may be fine as-is: showing a fabricated "attractive stranger's photo" raises its own problems for a system that generates people procedurally, and the emotional arc (weeks of messages) does not compress into a 30-60 s Short well regardless of rendering capability. If covered, it should stay in `INSERT_SCREEN` (a chat log), never a face. |
| Deepfake voice-clone ("it's your son, I'm in trouble, send money") | **Weak** | topically very current and genuinely a good fit for the story shape (phone alert -> urgency -> money flow -> resolve, exactly the lottery/bank template), but there is no way to signal "this voice/video is fake" visually - no glitch or distortion effect in the 8-effect list. The *narrative* is buildable today; the "how do you tell it's fake" visual beat is not. |
| Cognitive-bias / money-psychology explainers (loss aversion, sunk cost, anchoring, FOMO) - not a scam story at all, just "why does this trick your brain" | **Strong, and under-used** | this is not a character drama, it is exactly what `VISUALIZE_FLOW`-style animated cards are for. `EXPLAIN_PROCESS` is already a defined visual intent in the schema but the director rarely reaches for it. A format built around 2-3 data-card shots and minimal character animation would be cheap to render, fast to produce, and lean on the system's actual strength instead of its weakest area (character variety). |

## What's fixable this week vs what needs new capability

**Cheap, high-value, same shape as `VISUALIZE_FLOW`:**
- A second procedural card type for a simple line/percentage chart (fake profit graph) - the render, caption and QC machinery for a data card already exists; only the drawing code is new.
- A UPI/QR-style variant of `INSERT_SCREEN` (payment app chrome instead of a generic SMS card).
- A laptop/desktop framing for `INSERT_SCREEN` (a browser/pop-up look instead of a phone card) - closes the tech-support-scam gap.

**Needs a genuinely new capability:**
- A video-call shot (ringing state, picture-in-picture) - unlocks both digital-arrest and deepfake-relative scams, two of the highest-search-volume current topics.
- A crowd/group shot beyond 4 cast members - unlocks MLM/Ponzi meetings.
- A glitch/distortion effect - lets a story visually say "this is synthetic" without narrating it.

**Not worth building:** photoreal fake profile photos, real brand/app UI reproductions (both raise their own legal/ethical problems for a system that generates people and interfaces procedurally; the fictional-sender-id convention this system already uses is the right call to keep).

## The other uniqueness risk: repetition across your own catalogue, not against competitors

Even inside the categories rated "strong" above, every story currently draws from the same 15 archetypes, 12 environments and 36 actions. The lottery story and the OTP story already share a visual grammar (phone alert -> insert screen -> money flow -> resolve) because that is the honest shape of most of these scams - but a viewer who watches five of these videos in a row will start to recognise the shots, not just the topic. That is a real risk to "we want to be unique" that has nothing to do with what a competitor is doing.

Two cheap mitigations available today, no new capability needed:
- Vary camera and pacing choices per story on purpose (already improved this session: the director is told to vary shot size/movement, and the finishing look now varies pause length by punctuation instead of one fixed rhythm).
- Rotate which of the 12 environments and 15 archetypes a story uses instead of defaulting to bedroom + young man every time - the catalogue supports far more variety than the two acceptance stories have shown so far.

## Bottom line

The system is a strong, ready fit today for the classic "phone scam" shape - lottery, fake bank/OTP, delivery, job offers, government-scheme impersonation - and that shape covers a large share of real-world scams in India. Its most genuinely unique asset is the animated money-flow visualisation, which almost nobody else in this content niche does. Its weakest fit is exactly the newest, fastest-growing scam formats - digital arrest and deepfake/voice-clone fraud - because those need a video-call visual the renderer does not have yet. If the channel wants to lead on *currency* (the scams people are searching for right now) rather than just *volume*, a video-call capability is the single highest-leverage thing to build next.
