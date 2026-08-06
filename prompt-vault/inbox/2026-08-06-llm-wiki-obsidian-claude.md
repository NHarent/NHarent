# LLM Wiki build guide — Obsidian + Claude (artikel)

- **Type**: workflow
- **Bron**: onbekend (nieuwsbrief/blogpost, geplakt)
- **Datum**: 2026-08-06
- **Tags**: #claude #agent #productivity #untested
- **Triage**: pending
- **Score**: -

## Notitie

Volledige build-guide voor het Karpathy LLM-Wiki-patroon. Overlapt ~80% met
de bestaande drie-vault-setup. Waarde zit in 3 deltas, niet in de basis.

## Inhoud (samengevat — geen integrale kopie i.v.m. bron)

### Basis (al aanwezig in eigen setup)

- Obsidian = opslag (plain text, lokaal), Claude = brein erbovenop
- Koppeling via community plugin "Local REST API" + MCP:

  ```bash
  claude mcp add-json obsidian-vault '{
    "type": "stdio",
    "command": "uvx",
    "args": ["mcp-obsidian"],
    "env": {
      "OBSIDIAN_API_KEY": "KEY",
      "OBSIDIAN_HOST": "127.0.0.1",
      "OBSIDIAN_PORT": "27124"
    }
  }'
  ```

  → key zonder het woord "Bearer"; Obsidian moet draaien
- CLAUDE.md in vault-root via interview-prompt (1 vraag per keer)
- Projectmap-pipeline: Inputs / Process / Outputs / Feedback + eigen CLAUDE.md
- Project apart openen als vault i.p.v. de hele kennisbank
- Skills per herhaalde taak; Swipe-map (Favorite / Validated / Personal)
- Scheduled task (Claude Desktop, dagelijks 07:00): inbox fileren, stale
  notes flaggen, 3-regel changelog

### Delta 1 — rulings.md (WEL nieuw)

Per project een rulings.md. Elke correctie = één regel. Agents lezen dit
vóór elke actie. Bewust gescheiden van CLAUDE.md: identiteit is stabiel,
correcties zijn churn. Mengen = één slechte correctie herschrijft de rol.

### Delta 2 — Obsidian CLI-optie aanzetten

Instelling "Command Line Interface" in Obsidian: Claude navigeert via
native commands i.p.v. markdown file-by-file lezen. Sneller + geeft
structureel vaultbegrip.

### Delta 3 — Permissies boven prompts

"Niet verwijderen" in een prompt is een suggestie, geen beveiliging.
Afdwingen via read-only / scoped keys. Relevant voor knowledge-work vault.

### Repo-pointers

- AgriciDaniel/claude-obsidian — ~10.3k ★, 15 skills, PARA/Zettelkasten/LYT
  modes. LET OP: artikel noemt `bash bin/setup-vault.sh`; repo staat inmiddels
  op v2.0.0 met marketplace-install:

  ```bash
  claude plugin marketplace add AgriciDaniel/claude-obsidian
  claude plugin install claude-obsidian@claude-obsidian-marketplace
  ```

- eugeniughelbur/obsidian-second-brain — 45 commands, vault zonder Obsidian
  te openen, multi-agent. NIET geverifieerd.
- coleam00/second-brain-starter — genereert bouwplan i.p.v. kant-en-klaar
  systeem. NIET geverifieerd.
