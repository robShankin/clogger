# Claude Code Skills – Lean Implementation Guide

## 1. What a Skill Is

A Claude Code skill is a directory with a `SKILL.md` entrypoint.

It provides:

* a reusable workflow
* a named command (`/skill-name`)
* optional automatic invocation when relevant

Skills can include supporting files, scripts, and structured metadata.

---

## 2. Installation Models

### Project-local (recommended default)

```text
.claude/skills/<skill-name>/SKILL.md
```

* scoped to a repo
* commit and share with team

### Personal/global

```text
~/.claude/skills/<skill-name>/SKILL.md
```

* available across your projects

### Plugin-packaged

```text
<plugin>/skills/<skill-name>/SKILL.md
```

* use for team-wide distribution across repos

---

## 3. When to Use a Skill

Use a skill when the workflow is:

* repeatable
* stable
* file-aware
* worth naming and standardizing

Do NOT use a skill when:

* it’s a one-off prompt
* logic belongs in code/service
* it depends on hidden or persistent state

---

## 4. Minimum Viable Skill

```text
.claude/skills/review-api/
└── SKILL.md
```

```md
---
name: review-api
description: Review an API implementation for contract correctness, error handling, auth, and test coverage. Use when reviewing backend endpoint changes.
disable-model-invocation: false
user-invocable: true
allowed-tools: Read, Grep, Glob
---

Review the API implementation.

Objectives:
1. Verify route shape, request/response contract, and status codes.
2. Check authn/authz behavior.
3. Check validation and error handling.
4. Check test coverage and missing edge cases.
5. Return:
   - Findings
   - Severity
   - Exact file references
   - Recommended fixes

Be concrete. Do not speculate without evidence.
```

---

## 5. Frontmatter (What Actually Matters)

### Required thinking fields

**name**

* lowercase, hyphenated

**description (CRITICAL)**

* drives auto-selection
* write as a **conditional trigger**, not documentation
* must clearly state:

  * what changed
  * what context applies
  * when to activate

Bad:

```yaml
description: Helps with code
```

Good:

```yaml
description: Review Express API handlers for contract correctness, validation, auth, and test coverage when endpoint files are modified.
```

---

### ⚠️ Reality check

Only `name` and `description` are guaranteed to drive skill selection.

All other frontmatter fields should be treated as **advisory controls** and may vary by runtime or version.

---

### Control fields (advisory)

**disable-model-invocation: true**

* use for side-effectful workflows (deploy, commit, publish)

**user-invocable: false**

* hidden skill used only automatically

**allowed-tools**

* constrain behavior (use for read-only review skills)

---

### Control fields

**disable-model-invocation: true**

* required for side-effectful workflows (deploy, commit, publish)

**user-invocable: false**

* hidden skill used only automatically

**allowed-tools**

* constrain behavior (use for read-only review skills)

---

### Advanced (use intentionally)

**context: fork + agent**

* run in isolated subagent for heavy analysis

**paths**

* limit where skill applies

**argument-hint**

* improves slash command UX

---

## 6. Skill Design Principles

### 6.1 Write the description as a trigger

It must answer:

* what this does
* when it should be used
* what files/changes it applies to

---

### 6.2 Keep SKILL.md tactical

Do NOT:

* dump documentation
* write essays

DO:

* define execution steps
* define output

---

### 6.3 Use a playbook structure

* Purpose
* When to use
* Inputs
* Procedure
* Output contract
* Guardrails

---

### 6.4 Separate supporting content

```text
.claude/skills/<skill>/
├── SKILL.md
├── reference.md
├── examples.md
└── scripts/
```

SKILL.md = orchestration
Everything else = supporting material

---

### 6.5 Constrain outputs

Always define output shape.

Example:

* findings
* severity
* evidence
* recommended fix
* missing tests

---

## 7. Arguments

Use `$ARGUMENTS` for slash invocation.

```md
---
name: triage-bug
description: Triage a bug by identifying reproduction steps and root cause.
argument-hint: [ticket-id]
disable-model-invocation: true
---

Triage bug $ARGUMENTS.

Return:
- reproduction status
- root cause hypothesis
- confidence
- fix recommendation
- tests to add
```

---

## 8. When to Use `context: fork`

Use for:

* repo-wide exploration
* architecture tracing
* multi-step reasoning

Example:

```md
---
name: deep-research-api
description: Analyze API architecture and trace request flow.
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob
---
```

Rule:

* skill = reusable workflow
* fork/subagent = heavy exploration

---

## 9. Execution (Critical)

A high-quality skill should execute, not just reason.

When applicable:

* run tests
* run linters
* run validators
* inspect outputs

Example:

* Run `npm test`
* Parse failures
* Map failures to source files
* Identify root cause patterns

Avoid skills that only analyze without interacting with the system.

---

name: deep-research-api
description: Analyze API architecture and trace request flow.
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob
-------------------------------

````

Rule:
- skill = reusable workflow
- fork/subagent = heavy exploration

---

## 9. Packaging Patterns

### Repo-shipped (default)

```text
repo/.claude/skills/<skill>/
````

### Personal utility

```text
~/.claude/skills/<skill>/
```

### Plugin distribution

```text
plugin/skills/<skill>/
```

Only use plugins when you actually need distribution.

---

## 10. Common Pitfalls (Critical)

### 10.1 Vague descriptions

* breaks auto-selection

### 10.2 Over-triggering

* caused by aggressive language like “ALWAYS USE”

### 10.3 Overloaded skills

* trying to do everything in one skill

### 10.4 Side-effectful auto-invocation

* dangerous
* use manual-only for deploy/commit/etc

### 10.5 No output contract

* leads to inconsistent results

### 10.6 Stuffing everything into SKILL.md

* hurts performance and clarity

### 10.7 Missing tool constraints

* review skills start modifying code

### 10.8 Wrong abstraction

* using skills instead of subagents for deep research

### 10.9 No path scoping

* triggers in irrelevant contexts

### 10.10 Not testing properly

* must test:

  * `/skill-name`
  * natural-language triggering

---

## 11. Testing Checklist

1. Run `/skill-name`
2. Test natural-language trigger
3. Adjust description if under-triggering
4. Narrow scope if over-triggering
5. Move bulk content out of SKILL.md

---

## 12. Production Template

```md
---
name: <skill-name>
description: <precise triggerable description>
argument-hint: [optional]
disable-model-invocation: <true|false>
user-invocable: <true|false>
allowed-tools: Read, Grep, Glob
---

# Purpose
<short>

# When to use
- condition

# Inputs
- $ARGUMENTS

# Procedure
1. step
2. step

# Output contract
Return:
- item
- item

# Guardrails
- no guessing
- cite files

# Resources
- reference.md
```

---

## 13. Blunt Best Practices

Good skill:

* narrow
* explicit
* constrained
* safe

Bad skill:

* vague
* broad
* side-effectful + auto-invoked
* no output structure

---

## 14. Hard Rule

If a skill cannot be trusted to run automatically, it must not be auto-invocable.

---

## 15. Bottom Line

Start here:

* project-local skill
* one clear responsibility
* manual-only for side effects
* read-only for analysis
* strong description
* strict output contract

This yields skills that actually work instead of prompt clutter.
