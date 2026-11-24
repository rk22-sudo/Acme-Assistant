# Phase 5 decisions

- Prompt-injection checks use the existing heuristic regex patterns in `app/guardrails.py`. Check every client-supplied message, including assistant history, before sending the conversation to the agent. On a match, refuse the request and log pattern names and employee ID, never message text.
- Redact all supported PII kinds (EMAIL, SSN, CARD, PHONE) from user-supplied messages before the agent sees them. Redact SSN and CARD from the assistant reply. Public handbook contact emails remain visible in replies.
- Scan handbook chunks with the same injection detector before adding them to model context. Skip flagged chunks and log their IDs and pattern names without logging chunk text.
- Treat `request_leave`, `approve_leave`, `create_ticket`, and `send_slack_message` as writes. The agent queues these actions and returns `awaiting_user_confirmation`; it does not call the write tool. The user explicitly confirms through `POST /chat/confirm`.
- Bind a confirmation token to the employee, tool name, and arguments using HS256 and the configured `JWT_SECRET`. Action tokens expire after five minutes and use issuer `handbook-assistant-action`, separate from the login-token issuer. Confirmation requires the token subject to match the authenticated caller.
- Keep `app.agent.run` tool-call details for internal use and live evals; trim tool calls in the `/chat` HTTP response to the tool name and success flag.
- The corpus scan found 0 injection-flagged chunks out of 992 and 44 chunks with PII-like text. These are heuristic scan counts, not proof that the corpus is free of injection or sensitive data.
