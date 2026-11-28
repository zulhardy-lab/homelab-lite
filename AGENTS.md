CLAUDE.md

# Azure DevOps Lab Agent Instructions

Source: Adapted from zulhardy/infrastructure-agents-guide

- Chapter 5: Credential Management
- Chapter 7: Change Control
- Chapter 8: Policy & Guardrails
- Chapter 13: Risk Framework

These instructions define the operational boundaries for this repository. Prompt-level instructions are considered the weakest control layer, therefore all controls should be reinforced through technical enforcement where possible.

## Autonomy Level

Level 1: PROPOSE

The agent may:

- Write code
- Create branches
- Open Pull Requests

The agent may not:

- Merge Pull Requests
- Apply infrastructure changes
- Destroy infrastructure
- Modify repository security controls

A human must approve and execute all production-affecting operations.

## Hard Rules

### Git Workflow

- NEVER push directly to main
- ALWAYS create a feature branch for every change

Branch naming:

- feat/<short-name>
- fix/<short-name>
- chore/<short-name>

#### Enforcement

- Branch protection enabled on main
- Pull Request required
- Human approval required
- All checks must pass before merge

### Terraform Restrictions

The agent MUST NEVER execute:

- terraform apply
- terraform destroy
- terraform import
- terraform state rm
- terraform state mv

The agent MAY execute:

- terraform fmt
- terraform validate
- terraform plan
- terraform show

### Azure Restrictions

The agent MUST NEVER execute write operations such as:

- az ... create
- az ... update
- az ... delete
- az ... set

The agent MAY execute:

- az ...

read-only discovery and query operations only.

#### Enforcement

- No Azure write identity assigned to the agent
- OIDC Federation only
- Infrastructure changes execute through GitHub Actions after merge
- GitHub Environment approval required

### Pull Request Restrictions

The agent MUST NEVER:

- Merge Pull Requests
- Approve Pull Requests
- Modify branch protection policies
- Change repository settings

### Credential Management

The agent MUST NEVER:

- Request secrets
- Store secrets
- Print secrets
- Commit secrets
- Commit .tfvars containing secrets
- Commit terraform.tfstate

Forbidden credential types include:

- Client secrets
- API keys
- Access tokens
- Certificates
- Terraform state files

#### Authentication Standard

Use:

- OIDC Workload Identity Federation

Never use:

- Static credentials
- Long-lived secrets

#### Enforcement

- No secrets stored in repository
- .gitignore excludes state files and tfvars
- Secret scanning enabled

### Repository Scope

The agent may modify only:

- infra/
- docs/

Workflow changes:

- .github/workflows/

require explicit human approval.

All other repository paths are considered out of scope.

### Validation Requirements

Before opening a Ready-for-Review Pull Request, the following must pass:

- terraform fmt
- terraform validate
- tflint
- checkov
- terraform plan

### Plan Convergence

If a Terraform plan does not converge after 10 attempts:

1. Stop further modifications.
2. Open a Draft Pull Request.
3. Prefix title with:
   [not converged]
4. Include remaining diff.
5. Do not describe the issue as resolved.

### Destructive Operations

The agent must never perform irreversible actions.

Examples:

- Database deletion
- Storage deletion
- Identity deletion
- Role assignment removal
- Key Vault secret deletion
- Terraform state manipulation

These actions require human execution.

### Ambiguity Policy

When requirements are unclear:

1. Stop.
2. State assumptions.
3. Explain uncertainty.
4. Request clarification.

Principle:

Fail safe. Never fail open.

## Pull Request Requirements

Every Pull Request must include the following sections.

### Summary

Describe:

- What changed
- Why it changed

### Changes

List:

- Modified files
- Impacted resources

### Validation

Provide results for:

- terraform fmt
- terraform validate
- tflint
- checkov

### Plan Output

Include:

- Add: X
- Change: Y
- Destroy: Z

along with the complete Terraform plan output.

### Cost Impact

Document:

- New resources introduced
- Expected Azure pricing tier
- Estimated monthly operating cost

### Destruction Notice

If any resource is planned for destruction:

- Place a destruction summary at the top of the PR
- Explicitly list affected resources
- Explain the reason for destruction

## Lab Standards

### Region

Default deployment region:

southeastasia

### Required Resource Tags

Every resource must contain:

- project
- owner
- expires-on

Date format:

YYYY-MM-DD

### Cost Controls

Prefer the lowest-cost SKU that satisfies requirements.

Requirements:

- Avoid premium tiers unless justified
- Nothing runs indefinitely
- Temporary resources must have an expiration strategy

### Version Pinning

Always pin:

- Terraform versions
- Provider versions
- Tool versions

Never use:

- latest

## Skills, MCP Servers, and Third-Party Code

Only use:

- Vendor-official sources
- Versioned releases
- Commit-pinned dependencies

Requirements:

- Review code before installation
- Pin versions or commit hashes

Never use:

- Runtime downloaders
- Tools fetching arbitrary remote URLs during execution
- Systems requiring static API keys
- Systems requiring long-lived credentials

## Emergency Stop Procedure

A human operator can immediately disable automation by:

- Disabling GitHub Actions workflows
- Removing OIDC federated credentials from Microsoft Entra ID

This procedure should be tested before the first production project.

## Engineering Principles

### 1. Think Before Coding

#### Core Principle

Do not assume. Do not hide uncertainty. Surface tradeoffs.

Before implementing:

- State assumptions explicitly
- Ask when requirements are unclear
- Present alternative interpretations
- Avoid silently choosing between ambiguous options
- Recommend simpler approaches when appropriate
- Push back on unnecessary complexity

If anything is unclear:

- Stop
- Explain the issue
- Ask for clarification

### 2. Simplicity First

#### Core Principle

Write the minimum code necessary to solve the problem.

Rules:

- No speculative features
- No unnecessary abstractions
- No future-proofing unless requested
- No configurability that was not requested
- No handling of impossible scenarios

Ask:

Would a senior engineer consider this overengineered?

If yes, simplify.

### 3. Surgical Changes

#### Core Principle

Change only what is required.

When modifying existing code:

- Do not refactor unrelated code
- Do not "clean up" adjacent files
- Do not reformat unrelated sections
- Match existing project conventions
- Mention unrelated issues separately

When your changes create unused code:

- Remove unused imports
- Remove unused variables
- Remove unused functions

Only remove items made obsolete by your own changes.

Do not remove pre-existing dead code unless explicitly instructed.

Validation test:

Every changed line should be traceable to the user's request.

### 4. Goal-Driven Execution

#### Core Principle

Define success before implementation.

Examples:

| Request | Success Criteria |
|---|---|
| Add validation | Write failing validation tests, then make them pass |
| Fix bug | Reproduce with a test, then make it pass |
| Refactor code | Verify behavior remains unchanged before and after |

For multi-step work:

1. Step → verification
2. Step → verification
3. Step → verification

Prefer measurable outcomes over subjective objectives.

## Success Metrics

These instructions are working when:

- Pull Requests contain only necessary changes
- Diffs remain focused and reviewable
- Solutions are simple and maintainable
- Clarifying questions come before implementation
- Rework decreases
- Infrastructure changes remain auditable and safe
- Destructive actions always require human involvement
