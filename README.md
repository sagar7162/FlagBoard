# FlagBoard

## A multi-tenant feature-flag and configuration platform

Imagine that a company has built a new checkout page. Instead of releasing that page to every customer at once, the team can use FlagBoard to:

- keep the new page disabled while it is being developed;
- enable it only in development or staging;
- enable it for customers on a particular plan;
- release it to a percentage of users, such as 20%;
- switch it off immediately if something goes wrong;
- see changes appear in an open dashboard without refreshing;
- review who changed a flag and what the old and new values were.

This repository contains the backend service, a simple browser dashboard, database migrations, and automated tests for the core behavior.

---

## Table of contents

1. [The short version](#the-short-version)
2. [What problem does FlagBoard solve?](#what-problem-does-flagboard-solve)
3. [Important words](#important-words)
4. [A complete example](#a-complete-example)
5. [Features](#features)
6. [System overview](#system-overview)
7. [Architecture](#architecture)
8. [How a request travels through the application](#how-a-request-travels-through-the-application)
9. [Database design](#database-design)
10. [UML diagrams](#uml-diagrams)
11. [Feature-flag evaluation](#feature-flag-evaluation)
12. [Sticky percentage rollouts](#sticky-percentage-rollouts)
13. [Authentication and authorization](#authentication-and-authorization)
14. [Caching](#caching)
15. [Realtime updates](#realtime-updates)
16. [Audit logging](#audit-logging)
17. [API reference](#api-reference)
18. [Project structure](#project-structure)
19. [Frontend](#frontend)
20. [Local setup](#local-setup)
21. [Trying the system](#trying-the-system)
22. [Testing](#testing)
23. [Security model](#security-model)
24. [Design decisions and trade-offs](#design-decisions-and-trade-offs)
25. [Known limitations and future work](#known-limitations-and-future-work)

---

## The short version

FlagBoard has four main ideas:

1. A user belongs to one or more organizations.
2. An organization owns projects, and projects own feature flags.
3. Each flag has different settings for `development`, `staging`, and `production`.
4. A client application asks whether a flag is enabled for a particular user.

The answer is not merely `true` or `false`. FlagBoard also explains why it made that decision, for example:

```json
{
  "flag_key": "new_checkout_flow",
  "value": true,
  "reason": "rule_match"
}
```

The service is one FastAPI application, but its code is separated internally into routers, services, repositories, an evaluation engine, a cache, and realtime connection management.

---

## What problem does FlagBoard solve?

Without a feature-flag system, releasing a feature often looks like this:

```text
Developer writes code
        |
        v
Code is deployed
        |
        v
Everyone receives the feature immediately
```

That is risky. A bug in the new feature can affect every user, and switching it off may require another code change and deployment.

With FlagBoard, the release becomes a controlled decision:

```text
Code is deployed safely but hidden
        |
        v
FlagBoard decides who sees it
        |
        +--> nobody
        +--> internal testers
        +--> users with plan = pro
        +--> a stable percentage of users
        +--> everyone
```

The code and the release decision are separate. Developers can deploy code once and change exposure later.

### Why “multi-tenant”?

In this project, an organization is a tenant. “Acme Inc.” and “Beta Corp.” can both use the same FlagBoard server, but Acme must never see or change Beta’s projects, flags, API keys, or audit records.

```text
One FlagBoard server
├── Acme Inc. data
│   ├── projects
│   ├── flags
│   └── audit history
└── Beta Corp. data
    ├── projects
    ├── flags
    └── audit history

Acme users cannot cross the boundary into Beta data.
```

Tenant isolation is the most important security property in this project and is covered by tests.

---

## Important words

| Word | Meaning in plain language |
|---|---|
| User | A person with a FlagBoard account. |
| Organization | A company, team, or workspace. It is the tenant boundary. |
| Membership | The connection between a user and an organization, including their role. |
| Owner | An organization member allowed to perform owner-only actions, such as managing API keys. |
| Member | An organization user who can work with the organization’s flag data. |
| Project | A group of related flags, such as the checkout project. |
| Feature flag | A named on/off decision, such as `new_checkout_flow`. |
| Environment | A separate context: `development`, `staging`, or `production`. |
| Targeting rule | A condition such as `plan equals pro`. |
| Rollout | A percentage of users who should receive the enabled behavior. |
| Evaluation | Asking FlagBoard what value a flag has for one user. |
| API key | A secret used by a client application to evaluate flags. It is limited to one organization and environment. |
| Audit log | A history of changes: who changed what, when, and from which value to which value. |
| WebSocket | A long-lived browser/server connection used for live updates. |

---

## A complete example

Suppose Acme Inc. has a flag called `new_checkout_flow`.

```text
Organization: Acme Inc.
Project: Storefront
Flag: new_checkout_flow
```

Its environment settings might be:

| Environment | Enabled | Rule | Rollout |
|---|---:|---|---:|
| Development | Yes | none | 100% |
| Staging | Yes | `plan equals pro` | 20% for everyone else |
| Production | No | none | not applicable while off |

If the production setting is later changed to enabled and the client asks about user `user-123` with `plan = pro`, the evaluation flow is:

```text
Client sends API key + flag key + user information
                    |
                    v
API key identifies Acme Inc. + production
                    |
                    v
FlagBoard loads Acme's production config
                    |
                    v
Flag is enabled? yes
                    |
                    v
Does plan equal pro? yes
                    |
                    v
Return true, reason = rule_match
```

If the rule does not match, the service checks the percentage rollout. If neither a rule nor a rollout decides the result, an enabled flag is on for everyone.

---

## Features

### Included

- User signup and login.
- JWT bearer authentication for dashboard/API management requests.
- Organizations and organization memberships.
- `owner` and `member` roles.
- Projects within organizations.
- Boolean feature flags within projects.
- Separate settings for development, staging, and production.
- Enable/disable a flag.
- Percentage rollout from 0 to 100.
- One `equals` targeting rule per flag and environment.
- Environment-scoped evaluation API keys.
- Deterministic, sticky percentage rollouts.
- Safe evaluation responses for missing or malformed flag data.
- In-process TTL caching.
- Organization-scoped WebSocket updates.
- Audit history for flag changes.
- Plain HTML/CSS/JavaScript dashboard.
- Alembic database migrations.
- Unit and API/integration tests.




## System overview

```mermaid
flowchart LR
    User[Dashboard user] -->|HTTPS + JWT| Dashboard[Browser dashboard]
    Client[Product/client application] -->|HTTPS + API key| API[FlagBoard FastAPI application]
    Dashboard -->|REST requests| API
    Dashboard -.->|WebSocket| API
    API --> Routers[Routers]
    Routers --> Services[Services]
    Services --> Engine[Evaluation engine]
    Services --> Cache[In-memory TTL cache]
    Services --> Realtime[WebSocket connection manager]
    Services --> Repositories[Repositories]
    Repositories --> DB[(PostgreSQL)]
    Realtime -.-> Dashboard
```

### In simple terms

- The browser is the control panel.
- A product application uses the evaluation API.
- FastAPI receives requests.
- Routers identify the endpoint.
- Services apply business rules.
- Repositories read and write PostgreSQL.
- The pure evaluation engine decides the flag value.
- The cache avoids repeated database work.
- The connection manager tells open dashboards about changes.

---

## Architecture

FlagBoard is one deployable service with clear internal layers:

```mermaid
flowchart TB
    subgraph Clients[Clients]
        Browser[Browser dashboard]
        Product[Client product application]
    end

    subgraph App[One FastAPI application]
        Router[HTTP and WebSocket routers]
        Service[Application services]
        Repo[Database repositories]
        Eval[Pure evaluation engine]
        Cache[Simple TTL cache]
        WS[Connection manager]
    end

    Database[(PostgreSQL)]

    Browser --> Router
    Product --> Router
    Router --> Service
    Service --> Repo
    Repo --> Database
    Service --> Eval
    Service --> Cache
    Service --> WS
    WS --> Browser
```
---

## How a request travels through the application

### Example: toggling a flag

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Router as Flags router
    participant Service as Flag service
    participant DB as PostgreSQL
    participant Cache as TTL cache
    participant WS as WebSocket manager
    participant Other as Other open dashboards

    User->>Browser: Clicks the production toggle
    Browser->>Router: PATCH /flags/{id}/environments/production/toggle
    Router->>Router: Verify JWT and identify user
    Router->>Service: Request flag update
    Service->>DB: Check organization membership
    Service->>DB: Save new environment setting
    Service->>DB: Write audit entry
    Service->>Cache: Invalidate old cached configuration
    Service->>WS: Broadcast flag_updated event
    WS-->>Other: Send live event
    Service-->>Router: Return updated flag
    Router-->>Browser: HTTP 200 response
    Other->>Other: Re-fetch and redraw flag list
```

### Example: evaluating a flag

```mermaid
sequenceDiagram
    actor Client as Product application
    participant API as Evaluate router
    participant Auth as API-key dependency
    participant Cache as TTL cache
    participant DB as PostgreSQL
    participant Engine as Evaluation engine

    Client->>API: POST /evaluate/new_checkout_flow
    API->>Auth: Validate ApiKey header
    Auth-->>API: Organization + environment
    API->>Cache: Look up flag and environment config
    alt Cache miss
        Cache->>DB: Load organization-scoped flag/config
        DB-->>Cache: Return data
    end
    API->>Engine: Evaluate config for user
    Engine-->>API: value + reason
    API-->>Client: JSON evaluation response
```

---

## Database design

PostgreSQL stores eight tables:

```text
user
organization
membership
project
flag
flag_environment_config
api_key
audit_log_entry
```

### Relationships

```mermaid
erDiagram
    USER ||--o{ MEMBERSHIP : has
    ORGANIZATION ||--o{ MEMBERSHIP : contains
    ORGANIZATION ||--o{ PROJECT : owns
    PROJECT ||--o{ FLAG : contains
    FLAG ||--o{ FLAG_ENVIRONMENT_CONFIG : configures
    ORGANIZATION ||--o{ API_KEY : issues
    ORGANIZATION ||--o{ AUDIT_LOG_ENTRY : owns
    FLAG ||--o{ AUDIT_LOG_ENTRY : records
    USER ||--o{ AUDIT_LOG_ENTRY : performs

    USER {
        uuid id PK
        string email UK
        string password_hash
        datetime created_at
    }
    ORGANIZATION {
        uuid id PK
        string name
        string slug UK
        datetime created_at
    }
    MEMBERSHIP {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        string role
    }
    PROJECT {
        uuid id PK
        uuid organization_id FK
        string name
        string key
    }
    FLAG {
        uuid id PK
        uuid organization_id FK
        uuid project_id FK
        string key
        string name
        boolean on_value
        boolean off_value
        uuid created_by FK
        datetime created_at
    }
    FLAG_ENVIRONMENT_CONFIG {
        uuid id PK
        uuid flag_id FK
        string environment
        boolean enabled
        integer rollout_percentage
        string rule_attribute
        string rule_operator
        string rule_value
        datetime updated_at
    }
    API_KEY {
        uuid id PK
        uuid organization_id FK
        string environment
        string hashed_key UK
        string key_prefix
        datetime revoked_at
    }
    AUDIT_LOG_ENTRY {
        uuid id PK
        uuid organization_id FK
        uuid flag_id FK
        uuid actor_user_id FK
        string action
        json before
        json after
        datetime created_at
    }
```

### What each table means

#### `user`

Stores accounts. Passwords are never stored in plaintext; only a bcrypt hash is stored.

#### `organization`

Stores the tenant/workspace. The `slug` is a unique human-readable identifier.

#### `membership`

Connects users to organizations. The same user can belong to multiple organizations, and the same organization can have many users.

#### `project`

Groups related flags. Project keys are unique within an organization.

#### `flag`

Stores the flag identity and its boolean values. A flag belongs to both a project and an organization. The organization ID is stored directly so tenant-scoped queries can be explicit and safe.

#### `flag_environment_config`

Stores the setting for one flag in one environment. There can be only one row per flag/environment pair.

#### `api_key`

Stores only a hashed API key and a display prefix. The raw secret is returned only once when the key is created.

#### `audit_log_entry`

Stores the history of changes using JSON snapshots called `before` and `after`.

---

## UML diagrams

### UML class diagram

```mermaid
classDiagram
    class User {
        +UUID id
        +string email
        +string password_hash
        +datetime created_at
    }
    class Organization {
        +UUID id
        +string name
        +string slug
    }
    class Membership {
        +UUID user_id
        +UUID organization_id
        +string role
    }
    class Project {
        +UUID id
        +UUID organization_id
        +string name
        +string key
    }
    class Flag {
        +UUID id
        +UUID organization_id
        +UUID project_id
        +string key
        +string name
        +bool on_value
        +bool off_value
    }
    class FlagEnvironmentConfig {
        +string environment
        +bool enabled
        +int rollout_percentage
        +string rule_attribute
        +string rule_operator
        +string rule_value
    }
    class ApiKey {
        +UUID organization_id
        +string environment
        +string hashed_key
        +datetime revoked_at
    }
    class AuditLogEntry {
        +UUID flag_id
        +UUID actor_user_id
        +string action
        +JSON before
        +JSON after
    }

    User "1" --> "many" Membership
    Organization "1" --> "many" Membership
    Organization "1" --> "many" Project
    Project "1" --> "many" Flag
    Flag "1" --> "many" FlagEnvironmentConfig
    Organization "1" --> "many" ApiKey
    Flag "1" --> "many" AuditLogEntry
    User "1" --> "many" AuditLogEntry : actor
```

### Internal component diagram

```mermaid
classDiagram
    class Router {
        +parse request
        +call service
        +return response
    }
    class Service {
        +validate business rules
        +authorize user
        +coordinate work
    }
    class Repository {
        +read database
        +write database
    }
    class EvaluationEngine {
        +evaluate(config, user) EvaluationResult
    }
    class SimpleTTLCache {
        +get(key)
        +set(key, value)
        +invalidate(key)
    }
    class ConnectionManager {
        +connect(org, socket)
        +disconnect(org, socket)
        +broadcast(org, message)
    }

    Router --> Service
    Service --> Repository
    Service --> EvaluationEngine
    Service --> SimpleTTLCache
    Service --> ConnectionManager
```

---

## Feature-flag evaluation

The evaluation engine is pure business logic. It does not know about FastAPI, HTTP, SQLAlchemy, or PostgreSQL.

It receives:

```text
FlagConfig:
  flag_key
  enabled
  rollout_percentage
  optional targeting rule
  on_value
  off_value

EvalUser:
  key
  attributes
```

It returns:

```text
EvaluationResult:
  value: true or false
  reason: explanation string
```

### Decision flow

```mermaid
flowchart TD
    Start[Start evaluation] --> Enabled{Is flag enabled?}
    Enabled -->|No| Disabled[Return off_value\nflag_disabled]
    Enabled -->|Yes| Rule{Is there a targeting rule?}
    Rule -->|Yes| Match{Does user's attribute match?}
    Match -->|Yes| RuleOn[Return on_value\nrule_match]
    Match -->|No| Rollout{Is rollout percentage set?}
    Rule -->|No| Rollout
    Rollout -->|Yes| Bucket[Calculate stable user bucket 0-99]
    Bucket --> Included{Bucket < percentage?}
    Included -->|Yes| RolloutOn[Return on_value\nrollout]
    Included -->|No| RolloutOff[Return off_value\nrollout_excluded]
    Rollout -->|No| DefaultOn[Return on_value\ndefault_on]
```

The order matters:

1. A disabled flag always returns the off value.
2. A matching targeting rule takes priority over percentage rollout.
3. Percentage rollout is checked next.
4. An enabled flag with no rollout restriction is on for everyone.

Missing user attributes do not cause an error. The rule simply does not match.

### Safe failure behavior

If stored configuration is malformed, evaluation returns the safe off value with `reason: "evaluation_error"`. If the flag does not exist, evaluation returns HTTP 200 with a safe default and `reason: "not_found"`.

This is intentional: a client application should not crash merely because a configuration flag is missing or damaged.

---

## Sticky percentage rollouts

A naive rollout might use a random number on every request:

```text
Request 1: random result says ON
Request 2: random result says OFF
Request 3: random result says ON
```

That creates a confusing user experience.

FlagBoard instead hashes the flag key and user key together:

```python
bucket = md5(f"{flag_key}:{user_key}").hexdigest() converted to an integer % 100
```

The result is a stable bucket from 0 to 99.

```mermaid
flowchart LR
    Input[flag key + user key] --> Hash[Deterministic hash]
    Hash --> Bucket[Number from 0 to 99]
    Bucket --> Compare[Compare with rollout percentage]
    Compare --> Result[Stable ON or OFF decision]
```

For a 20% rollout:

```text
Buckets 0–19  -> ON
Buckets 20–99 -> OFF
```

The same user remains in the same group for that flag, while a different flag produces a different bucket. MD5 is used here for speed and distribution, not for security; the bucket is not a secret or authentication decision.

---

## Authentication and authorization

FlagBoard uses two kinds of credentials because there are two different audiences.

### Dashboard users: JWT bearer tokens

1. A user signs up or logs in.
2. The server verifies the password.
3. The server returns a signed JWT.
4. The browser sends it as `Authorization: Bearer <token>`.
5. Protected endpoints decode the token and load the user.

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Auth as Auth router
    participant DB as PostgreSQL

    User->>Browser: Enter email and password
    Browser->>Auth: POST /auth/login
    Auth->>DB: Find user by email
    Auth->>Auth: Verify bcrypt password hash
    Auth-->>Browser: Signed JWT
    Browser->>Auth: Request with Bearer JWT
    Auth->>Auth: Verify signature and expiry
    Auth-->>Browser: Protected response
```

### Product applications: environment-scoped API keys

The evaluation endpoint uses:

```text
Authorization: ApiKey <raw-key>
```

An API key belongs to one organization and one environment. A production key cannot evaluate staging data.

Raw API keys are not stored. The server stores a hash plus a short prefix for display. The raw key is shown only at creation time.

### Tenant isolation

Every organization-sensitive query must be scoped to the authenticated user’s membership or the API key’s organization. A user from Acme must not be able to access Beta data by guessing a UUID.

```mermaid
flowchart TD
    Request[Incoming request] --> Credential{Credential type}
    Credential -->|JWT| User[Identify user]
    Credential -->|ApiKey| Key[Identify organization + environment]
    User --> Membership{Membership exists?}
    Membership -->|No| Deny[Reject request]
    Membership -->|Yes| Scope[Scope query to that organization]
    Key --> Scope
    Scope --> Database[Read or change only permitted rows]
```

---

## Caching

Evaluation can happen frequently. The service uses `SimpleTTLCache`, a small in-memory dictionary with expiration times.

There are cached lookups for:

- organization + flag key → flag identity;
- flag ID + environment → environment configuration;
- API key authentication lookups.

```mermaid
flowchart TD
    Request[Evaluation request] --> CacheLookup{Cached?}
    CacheLookup -->|Yes| Engine[Evaluate in memory]
    CacheLookup -->|No| DB[Read PostgreSQL]
    DB --> Store[Store with TTL]
    Store --> Engine
    Write[Flag configuration changed] --> Invalidate[Explicitly invalidate affected cache key]
```

The cache uses two safeguards:

- invalidate immediately after a write;
- expire entries after the configured TTL, which is 30 seconds by default.

This cache is intentionally process-local. If the service ran on multiple server processes, each process could have a different cached value. A shared cache such as Redis would then be a natural future improvement.

---

## Realtime updates

The dashboard opens a WebSocket for the selected organization:

```text
WS /ws/orgs/{org_id}?token=<jwt>
```

The server checks that the JWT identifies an organization member before accepting the connection.

When a flag changes, the connection manager broadcasts an event such as:

```json
{
  "type": "flag_updated",
  "flag_id": "...",
  "environment": "production",
  "enabled": true,
  "rollout_percentage": 20
}
```

The dashboard receives the event, fetches the latest flag list, and redraws the page. The user who made the change receives the normal HTTP response; other open dashboard tabs receive the live notification.

### Why this is in memory

The project intentionally runs as one application process. A plain Python connection registry is therefore sufficient. With multiple instances, a change arriving at instance A would not automatically reach sockets connected to instance B. Redis pub/sub or a managed realtime service would solve that later.

---

## Audit logging

Every flag mutation records:

- the organization;
- the flag;
- the user who made the change;
- the action name;
- the state before the change;
- the state after the change;
- the timestamp.

Example:

```json
{
  "action": "flag_toggled",
  "before": {
    "environment": "production",
    "enabled": false
  },
  "after": {
    "environment": "production",
    "enabled": true
  }
}
```

Audit history makes operational changes explainable. If somebody asks “when did production turn on, and who did it?”, the answer is in the flag’s audit log.

---

## API reference

The FastAPI application also exposes interactive documentation at `/docs` when it is running.

### Health

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Returns `{ "status": "ok" }`. |

### Authentication

| Method | Path | Body | Authentication |
|---|---|---|---|
| `POST` | `/auth/signup` | `{ "email": "...", "password": "..." }` | None |
| `POST` | `/auth/login` | `{ "email": "...", "password": "..." }` | None |

Both successful endpoints return:

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer"
}
```

### Organizations, members, projects, and API keys

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/orgs` | List organizations where the current user is a member. |
| `POST` | `/orgs` | Create an organization; the creator becomes owner. |
| `POST` | `/orgs/{organization_id}/members` | Add an existing user to an organization. |
| `GET` | `/orgs/{organization_id}/projects` | List projects for an organization. |
| `POST` | `/orgs/{organization_id}/projects` | Create a project. |
| `POST` | `/orgs/{organization_id}/api-keys` | Create an environment-scoped evaluation key. |
| `GET` | `/orgs/{organization_id}/api-keys` | List key metadata without raw secrets. |
| `DELETE` | `/orgs/{organization_id}/api-keys/{api_key_id}` | Revoke an API key. |

Example project creation:

```json
{
  "name": "Storefront",
  "key": "storefront"
}
```

Example API key creation:

```json
{
  "environment": "production"
}
```

### Flags

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/projects/{project_id}/flags` | List project flags. |
| `POST` | `/projects/{project_id}/flags` | Create a boolean flag. |
| `GET` | `/flags/{flag_id}` | Get one flag. |
| `PATCH` | `/flags/{flag_id}/environments/{environment}/toggle` | Enable or disable a flag. |
| `PATCH` | `/flags/{flag_id}/environments/{environment}/rollout` | Set a 0–100 rollout percentage. |
| `PATCH` | `/flags/{flag_id}/environments/{environment}/rule` | Set a rule or send `null` to clear it. |
| `GET` | `/flags/{flag_id}/audit-log` | Get flag change history. |

Supported environments are:

```text
development
staging
production
```

Create a flag:

```json
{
  "key": "new_checkout_flow",
  "name": "New checkout flow"
}
```

Toggle a flag:

```json
{
  "enabled": true
}
```

Set a rollout:

```json
{
  "percentage": 20
}
```

Set a targeting rule:

```json
{
  "attribute": "plan",
  "operator": "equals",
  "value": "pro"
}
```

To clear the rule, send:

```json
null
```

### Evaluation

```text
POST /evaluate/{flag_key}
Authorization: ApiKey <environment-scoped-key>
```

Body:

```json
{
  "user": {
    "key": "user-123",
    "attributes": {
      "plan": "pro"
    }
  }
}
```

Response:

```json
{
  "flag_key": "new_checkout_flow",
  "value": true,
  "reason": "rule_match"
}
```

Possible reasons include:

| Reason | Meaning |
|---|---|
| `flag_disabled` | The environment setting is off. |
| `rule_match` | The user matched the targeting rule. |
| `rollout` | The user’s stable bucket was inside the rollout percentage. |
| `rollout_excluded` | The user’s stable bucket was outside the rollout percentage. |
| `default_on` | The flag is enabled with no rule or rollout restriction. |
| `not_found` | The flag or environment configuration was not found; safe off behavior was returned. |
| `evaluation_error` | Stored configuration was malformed; safe off behavior was returned. |

### WebSocket

```text
WS /ws/orgs/{org_id}?token=<jwt>
```

The JWT is passed as the `token` query parameter because browsers do not provide a straightforward way to add an `Authorization` header to the native WebSocket constructor.

---

## Project structure

```text
.
├── PROJECT_BLUEPRINT.md             # Source-of-truth design document
├── README.md                        # This guide
├── requirements.txt                 # Python dependencies
├── alembic.ini                      # Migration configuration
├── alembic/
│   ├── env.py
│   └── versions/                    # Database migration history
├── app/
│   ├── main.py                      # Creates FastAPI app and includes routers
│   ├── config.py                    # Environment-based settings
│   ├── database.py                  # SQLAlchemy engine/session setup
│   ├── models.py                    # SQLAlchemy database models
│   ├── schemas.py                   # Pydantic request/response schemas
│   ├── cache.py                     # In-process TTL cache
│   ├── realtime.py                  # WebSocket connection manager
│   ├── auth/
│   │   ├── security.py              # Password hashing and JWT helpers
│   │   └── dependencies.py          # Current-user and API-key dependencies
│   ├── engine/
│   │   ├── evaluator.py              # Pure flag evaluation logic
│   │   └── rollout.py                # Stable bucket calculation
│   ├── repositories/                # Database query code
│   ├── services/                    # Business workflows
│   └── routers/                     # HTTP and WebSocket endpoints
├── frontend/
│   ├── index.html                   # Dashboard markup
│   ├── app.js                       # Dashboard behavior and API calls
│   └── styles.css                   # Dashboard styling
└── tests/                           # Automated tests
```

### Layer responsibilities

| Layer | Responsibility | What it should not do |
|---|---|---|
| Routers | Parse requests, call services, format HTTP responses. | Contain complicated business logic. |
| Services | Apply business rules, authorization, validation, and coordinate work. | Become a second database abstraction. |
| Repositories | Perform database reads and writes. | Decide UI behavior or HTTP status codes. |
| Engine | Evaluate a flag from plain data. | Perform I/O or import FastAPI/SQLAlchemy. |
| Cache | Temporarily reuse commonly requested data. | Become the permanent source of truth. |
| Realtime manager | Track sockets and broadcast events. | Persist business data. |

---

## Frontend

The frontend is intentionally plain HTML, CSS, and JavaScript.

Current dashboard behavior includes:

- login;
- organization list;
- project selection;
- environment selection;
- flag list;
- flag status and toggle control;
- live connection indicator;
- audit log display;
- live refresh when a WebSocket event arrives;
- logout.

The dashboard calls the backend at:

```javascript
const API_BASE = window.FLAGBOARD_API_BASE || "http://localhost:8000";
```

For a production deployment, configure the API base URL for the deployed backend and serve the frontend from an allowed CORS origin.

The create-organization control is currently a visual placeholder, and creation of organizations, projects, flags, and API keys is available through the API or `/docs`. This keeps the current dashboard focused on the core “change a flag and see it update live” demonstration.

---

## Local setup

### Prerequisites

- Python 3.10 or newer.
- PostgreSQL.
- `pip`.
- A shell or terminal.

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a PostgreSQL database

Create a database named `flagboard`, or use another name and place it in `DATABASE_URL`.

Example connection string:

```text
postgresql://postgres:postgres@localhost:5432/flagboard
```

### 4. Create a `.env` file

The application loads settings through `pydantic-settings`.

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/flagboard
JWT_SECRET=replace-this-with-a-long-random-secret
JWT_EXPIRY_HOURS=24
API_KEY_PEPPER=replace-this-with-another-secret
CACHE_TTL_SECONDS=30
CORS_ALLOWED_ORIGINS=["http://localhost:5500","http://127.0.0.1:5500"]
```

Do not commit real secrets.

### 5. Apply database migrations

```bash
alembic upgrade head
```

### 6. Start the API

```bash
uvicorn app.main:app --reload
```

The backend is now available at:

- API: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 7. Serve the frontend

From the repository root, run a simple static server in a second terminal:

```bash
python -m http.server 5500 --directory frontend
```

Open:

```text
http://localhost:5500
```

---

## Trying the system

The simplest end-to-end demonstration is:

```mermaid
flowchart LR
    Signup[Sign up] --> Org[Create organization]
    Org --> Project[Create project]
    Project --> Flag[Create flag]
    Flag --> Key[Create production API key]
    Key --> Toggle[Toggle flag in dashboard]
    Toggle --> Live[See live update in another tab]
    Toggle --> Evaluate[Evaluate flag with API key]
    Evaluate --> Answer[Receive value + reason]
```

### Example with `curl`

Sign up:

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@example.com","password":"correct-horse-battery-staple"}'
```

Save the returned `access_token` as `JWT` and use it below:

```bash
export JWT='paste-token-here'
```

Create an organization:

```bash
curl -X POST http://localhost:8000/orgs \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Acme Inc."}'
```

Create a project:

```bash
curl -X POST http://localhost:8000/orgs/{ORG_ID}/projects \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Storefront","key":"storefront"}'
```

Create a flag:

```bash
curl -X POST http://localhost:8000/projects/{PROJECT_ID}/flags \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"key":"new_checkout_flow","name":"New checkout flow"}'
```

Create a production API key. Store the `raw_key` from the response; it is only returned at creation time:

```bash
curl -X POST http://localhost:8000/orgs/{ORG_ID}/api-keys \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{"environment":"production"}'
```

Evaluate the flag:

```bash
curl -X POST http://localhost:8000/evaluate/new_checkout_flow \
  -H 'Authorization: ApiKey paste-raw-api-key-here' \
  -H 'Content-Type: application/json' \
  -d '{"user":{"key":"user-123","attributes":{"plan":"pro"}}}'
```

Replace placeholders such as `{ORG_ID}` with actual UUIDs returned by previous responses. Curly-brace placeholders are documentation notation, not literal shell syntax.

---

## Testing

The test suite is organized around the most important behavior.

### Unit tests

- `tests/test_evaluator.py`: disabled flags, targeting rules, rollouts, and safe evaluation behavior.
- `tests/test_rollout.py`: deterministic buckets and distribution behavior.

These tests exercise pure logic without needing a browser.

### API/integration tests

- `tests/test_auth.py`: signup and login behavior.
- `tests/test_flags_api.py`: flag and organization workflows.
- `tests/test_evaluation_cache.py`: cached evaluation behavior.

Important scenarios include:

- signup → login → create organization → create project → create flag;
- enable, disable, and evaluate a flag;
- tenant isolation between two organizations;
- duplicate flag handling;
- revoked API key rejection;
- missing flag returns a safe response rather than breaking evaluation.

Run the suite with:

```bash
pytest -q
```

The tests require the project dependencies and a configured test database according to the repository’s test configuration.

---

## Security model

### Passwords

Passwords are normalized and hashed using bcrypt. The plaintext password is not stored.

### JWTs

Dashboard access tokens are signed with the configured server secret using HS256 and include an expiration time.

### API keys

API keys are generated as random secrets. Only a hash and display prefix are stored. The raw key should be treated like a password.

### Organization boundaries

Authorization checks verify membership before organization-owned data is returned or changed. Evaluation keys are also scoped to one organization and environment.

### Safe logging

Passwords, JWTs, and raw API keys must never be logged.

---

## Design decisions and trade-offs

### Synchronous FastAPI and SQLAlchemy

The project uses synchronous route handlers and synchronous SQLAlchemy with `psycopg2`. FastAPI can run synchronous handlers concurrently in a thread pool. This keeps the code easier to learn and reason about while the project has modest traffic.

An asynchronous database stack could be appropriate at higher I/O concurrency, but it would introduce another set of concepts without helping the single-server demonstration much.

### One service with internal layers

Microservices would add deployment, networking, and operational complexity. The current scale needs separation of responsibilities, not separate servers.

### One targeting rule

Each environment supports at most one `attribute equals value` rule. This is enough to demonstrate targeted releases without creating a full rules language.

### WebSockets for the dashboard

Polling would repeatedly ask the server “did anything change?” WebSockets keep a connection open so the server can push a change immediately. The project uses an in-memory connection manager because it runs as one process.

### Database migrations

Alembic records schema changes over time. Instead of manually recreating the database, developers can apply the migration history to reach the current schema.

---

## Known limitations and future work

1. Add a complete dashboard UI for creating organizations, projects, flags, and API keys.
2. Add multiple ordered targeting rules with AND/OR behavior.
3. Add user segments and individual overrides.
4. Move cache and WebSocket fan-out to Redis for multiple server instances.
5. Add refresh-token rotation and stronger session management.
6. Add rate limiting and security monitoring.
7. Add analytics for evaluation counts and rollout outcomes.
8. Add multi-value flags, such as strings or JSON configuration.
9. Add a client SDK that locally evaluates a periodically synchronized ruleset.
10. Add load testing before handling real production traffic.

### What scaling would change

```mermaid
flowchart LR
    Current[One process\nlocal cache + local sockets] -->|Need horizontal scaling| Shared[Shared infrastructure]
    Shared --> Redis[Redis cache + pub/sub]
    Shared --> Pool[Database connection pooling]
    Shared --> Replicas[Multiple FastAPI instances]
```

The important point is not that the current design solves every production problem. It is that the design makes the current boundary explicit and makes the next engineering step understandable.

---

