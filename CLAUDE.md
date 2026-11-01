Read @AGENTS.md first and follow it. "The rules in short" and "Commands" bind every action.

From step S1.3 on, run `make check` before proposing a commit. Before S1.3 there is no Makefile: run the em dash check and the banned-word grep from AGENTS.md instead.

Never read `.env`, anything in `keys/` or `~/.config/gcloud/`, and never run `env`, `printenv` or plain `docker compose config`.
