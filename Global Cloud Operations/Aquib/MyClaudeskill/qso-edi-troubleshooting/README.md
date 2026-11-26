# EDI Troubleshooting Skill — Installation Package

This folder contains the `qso-edi-troubleshooting` Cowork skill for investigating
Quorum Software EDI outages.

## What This Skill Does

When you describe an EDI problem in Cowork, this skill guides Claude to:

1. **Ask for the right logs** — specifically the QPEC segregated qtrace logs (not just
   the master log), which contain the GPG command details needed for diagnosis
2. **Review ADO comments and screenshots** for context and clues
3. **Identify the correct QPEC server** for the affected application instance
4. **Recognize the two GPG error types** (QPTM config mismatch vs. missing public key)
5. **Compare UAT vs PRD keyrings** when a DB refresh is suspected
6. **Check ADO setup tickets** to confirm correct UAT key IDs for each trading partner
7. **Walk through key imports** including UTF-16 BOM encoding fix and trust setup
8. **Produce a QPTM change list** for the app admin
9. **Generate an RCA document** with verbatim log evidence

## Files in This Package

```
edi-troubleshooting-skill/
├── SKILL.md                          ← Main skill (install this)
├── references/
│   ├── gpg-diagnostics.md            ← All GPG error patterns and fixes
│   ├── db-refresh-patterns.md        ← DB refresh impact and comparison guide
│   ├── log-analysis.md               ← Log locations and search commands
│   └── rca-template.md               ← RCA document template
└── evals/
    └── evals.json                    ← Test cases for skill validation
```

## Installation

To install this as a Cowork skill, ask your Cowork admin to add the `edi-troubleshooting-skill`
folder as a skill in the `.claude/skills/` directory of your Cowork workspace.

## Trigger Phrases

Claude will use this skill automatically when you say things like:
- "EDI is down for [partner]"
- "Let's investigate this incident: [ticket number]"
- "QPEC is failing with a GPG error"
- "DB refresh broke EDI"
- "Key not found in keyring"
- "Secret key not available"
- "Can you help me write an RCA for this EDI outage?"
