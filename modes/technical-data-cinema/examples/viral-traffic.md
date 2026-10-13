# Pilot: Why a viral moment can break a backend

Format: vertical 9:16 technical data cinema, approximately 45–55 seconds.

Core question: Why can a product that worked for thousands of users fail when a post suddenly goes viral?

Narrative beats:
1. A clip spreads quickly; show audience growth as a meaningful crowd/particle field, not decorative dots.
2. One tap fans out into multiple work requests (feed, media, recommendations); show the branching causal flow.
3. Requests converge on finite backend capacity; queue depth and latency rise as demand exceeds capacity.
4. A traffic-versus-capacity graph builds in time, showing the lag in reactive autoscaling. Label values illustrative unless sourced.
5. Demonstrate prescaling or caching as an intervention that changes the flow and reduces backend work.
6. Show retries spreading out with backoff/jitter instead of synchronizing into a second spike.
7. Pay off with the lesson: prepare for demand and reduce work per request instead of relying only on reacting after overload.

Visual requirements:
- Audience, requests, servers, queue and graph are visually distinct and consistently represented.
- Show each mechanism operating, not just labels.
- Let one continuous system view evolve across multiple beats; use close-ups/graphs only when they clarify a new idea.
- Do not assert that the numbers describe a real service.
- Narration is generated and refined separately through the existing Chatterbox workflow; keep caption cues easy to replace after audio alignment.
