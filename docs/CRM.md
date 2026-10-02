# CRM and leads

The CRM turns buyer interest into tracked work for agents, agency owners and
independent owners. It lives in `backend/app/crm/` (models, policies,
service, router) and `frontend/src/app/dashboard/crm`, `/messages`.

## Model

| Table | Purpose |
| --- | --- |
| `inquiries` | Raw messages from signed-in, email-verified visitors about a public listing (name, phone/email, message, preferred contact). |
| `crm_customers` | A contact in someone's book. Scoped to an **agency** or, for independent listers, to an **owner user**. Linked to a platform user when the inquiry came from one (one customer per user per book). |
| `crm_leads` | The opportunity: customer, optional property, agency, accountable owner, assignee, stage, source, priority, budget (with currency, never converted), follow-up date, closed/lost data. |
| `lead_statuses` | Configurable pipeline: core stages NEW, CONTACTED, QUALIFIED, VIEWING, NEGOTIATION, WON, LOST (seeded, `is_system`), plus custom stages created by admins. |
| `crm_lead_activities` | Append-only timeline / contact history: notes, calls, WhatsApp, email, SMS, meetings, inquiries, stage changes, assignments, tasks, appointments, messages. |
| `crm_tasks` | To-dos with due dates (follow-up reminders), optionally tied to a lead. |
| `crm_appointments` | Viewings/meetings with status (scheduled, completed, cancelled, no-show). |
| `conversations`, `messages` | One thread per customer per listing between the customer and the listing side; read receipts. |

## Flow

1. A verified user sends an inquiry on a public listing
   (`POST /properties/{id}/inquiries`; rate limited per IP and per user;
   own listings rejected).
2. The customer is found or created in the right book, and the customer's
   **open** lead on that listing is reused — or a new `NEW` lead is created,
   assigned to the listing's agent (or the independent owner).
3. The inquiry is logged on the timeline, a conversation is opened with the
   message, an audit record is written and domain events
   `inquiry.created` / `lead.created` are emitted (notifications subscribe to
   these — see Phase 9).
4. The agent logs calls/notes (first real contact moves NEW → CONTACTED),
   schedules viewings (moves early stages → VIEWING), sets follow-ups and
   tasks, and closes the lead as WON or LOST (a reason is required for LOST;
   re-opening clears `closed_at`).

## Authorization

| Who | Sees | Changes |
| --- | --- | --- |
| Agent / independent owner (`leads.read_own`) | leads they own or are assigned to | those leads (`leads.manage`) |
| Agency owner (`leads.read_agency`) | every lead of their agency | all of them; **only they** (and admins) can reassign, within the agency |
| Admin (`leads.read_any`) | all leads | all leads; configure stages (`leads.configure`) |
| Customer | their own inquiries (`/me/inquiries`) and conversations — never lead internals | messages in their own threads |

Rules are enforced server-side in `app/crm/policies.py`; anything outside a
caller's scope returns **404** (not 403) so IDs cannot be probed. Lists are
filtered in SQL by the same scope, and related rows are batch-loaded (a test
asserts the query count does not grow with page size).

## API

| Endpoint | Notes |
| --- | --- |
| `POST /properties/{id}/inquiries`, `GET /me/inquiries` | Visitor side |
| `GET /crm/statuses`, `PUT /admin/crm/statuses/{code}` | Pipeline; core NEW/WON/LOST cannot be deactivated; a stage used by open leads cannot be deactivated |
| `GET/POST /crm/leads`, `GET/PATCH /crm/leads/{id}` | Filters: `status`, `assigned_to_id`, `property_id`, `q` (name/phone/email), `overdue`, `open_only` |
| `GET/POST /crm/leads/{id}/activities` | Only manual kinds can be posted; no future timestamps |
| `POST /crm/leads/{id}/appointments`, `GET /crm/appointments`, `PATCH /crm/appointments/{id}` | |
| `GET/POST /crm/tasks`, `PATCH /crm/tasks/{id}` | `status=open|today|overdue|done|all`, `lead_id` |
| `GET /crm/customers`, `GET/PATCH /crm/customers/{id}` | |
| `GET /crm/dashboard` | Open leads, new this week, overdue follow-ups, tasks due/overdue, upcoming appointments, won/lost, win rate — all scoped |
| `GET /me/conversations`, `GET/POST /conversations/{id}/messages` | Reading marks the other side's messages read; replies from the listing side are logged on the lead |

## Web UI

- Property page: inquiry form (prefilled from the account).
- `/dashboard/crm`: KPIs, kanban-style pipeline by stage with quick stage
  changes, new-lead form, upcoming appointments.
- `/dashboard/crm/leads/{id}`: stage/priority/follow-up/budget/assignee
  editor, activity logger and timeline, tasks, appointments, customer
  contact (tel/WhatsApp/email links).
- `/dashboard/crm/tasks`: task list with filters.
- `/messages`, `/messages/{id}`: conversations for customers and listers.

## Reminders

Follow-up dates and task due dates are stored and surfaced (overdue
counters, filters). Delivery of reminders (in-app/email/push) is handled by
the notification workers in Phase 9 via the domain events and a scheduled
scan — the CRM has no dependency on n8n.
