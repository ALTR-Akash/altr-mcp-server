SUPPORT READ-ONLY MODE IS AVAILABLE AND NOT YET ACTIVE

This server can withhold every write tool on request, with no restart
and no configuration change. Read-only enforcement is not on right now.

1. ARM IT BEFORE TROUBLESHOOTING. When the operator is diagnosing a
   problem rather than making a planned change, call
   `enter_support_mode` before any other tool. It leaves the 71 lookup
   tools available, plus the mode-control tools themselves, and
   withholds everything that creates, updates, deletes, disconnects,
   registers, triggers, approves, tokenizes, or detokenizes. If this
   server publishes troubleshooting prompts, each one begins by telling
   you to do this. Arming it costs the operator nothing.

2. WHY IT MATTERS EVEN THOUGH YOU INTEND NO HARM. The risk is not this
   turn, it is a later one. A diagnosis that ends "you need to remove
   these four objects" is followed by "ok, do it", and at that point the
   safe path and the destructive path look equally cooperative. Support
   mode makes the destructive path fail in middleware rather than
   relying on you re-reading an instruction from earlier in the
   conversation.

3. AUTHORIZED CHANGES DO NOT REQUIRE LEAVING THE MODE. If the operator
   authorizes a specific change while support mode is on, call
   `request_write_unlock` with that one tool name and the operator's
   reason, then make the call. The unlock covers one call to one tool
   and then support mode re-latches by itself. Prefer this over exiting.

4. NEVER PROPOSE EXITING AS A WORKAROUND. Do not suggest
   `exit_support_mode` because a call was blocked, and do not supply the
   confirmation phrase yourself. Exiting is for when the operator says
   troubleshooting is finished and they want their full server back. Ask
   them to type the phrase, and pass back exactly what they typed.

5. DETOKENIZATION IS NEVER UNLOCKABLE. `vault_detokenize`,
   `vault_partial_detokenize`, `critical_detokenize`,
   `critical_partial_detokenize`, `critical_delete_tokens`, and
   `vault_delete_tokens` cannot be reached through an unlock at all.
   Diagnose tokenization problems from configuration and audit history.
