# CrewLoop Product Spec

## 1. Product Summary

**Product name:** CrewLoop  
**One-line pitch:** CrewLoop is an AI dispatcher for contractor-heavy small businesses. It reads work from the web tools businesses already use, finds the right contractor, texts or calls them based on urgency, schedules the job, verifies they showed up, and releases payment only when the work is completed.

## 2. Exact Problem

Small businesses often rely on informal contractor lists. When a worker cancels or a last-minute job appears, the owner manually checks who is qualified, texts multiple people, calls urgent candidates, tracks replies, updates the schedule, verifies attendance, and pays after completion.

This is especially painful for businesses that use contract labor:

- event staffing companies
- catering companies
- cleaning companies
- moving companies
- home-service companies
- photographers and production crews
- hospitality teams
- security staffing teams
- field service operators

The core problem is:

> Small businesses need a fast, reliable way to fill urgent contractor jobs, verify proof of work, and pay only when the job is actually completed.

## 3. Exact Idea

CrewLoop turns a messy staffing emergency into a fully automated dispatch workflow. It can start from an owner text, or it can read an event page, schedule portal, spreadsheet, calendar, or staffing board through Browser Use and convert that web context into a dispatchable job.

Example owner text:

> Need a bartender tonight from 6-10 PM in SoMa. Must have event experience. Pay $120. Urgent.

CrewLoop then:

1. Parses the job request or imports it from a web source.
2. Captures source evidence from the original page.
3. Searches the contractor roster.
4. Matches by skill, availability, location, reliability, and rate.
5. Texts the best contractor.
6. Calls if the request is urgent or no one replies.
7. Confirms the contractor.
8. Creates the schedule.
9. Emails the owner a summary.
10. Collects proof that the contractor showed up.
11. Holds payment until work is complete.
12. Releases payment after proof and approval.

## 4. Hackathon Demo Scenario

### Demo business

**Bay Events Co.** needs a replacement contractor.

### Demo request

> Our bartender canceled. Need a replacement tonight from 6-10 PM in SoMa. Must have event experience. Pay $120. This is urgent.

### Demo outcome

CrewLoop finds Maya, a qualified bartender nearby, texts her, calls her when urgent, confirms the shift, sends the owner an email, verifies Maya checked in, and releases payment after proof of work.

## 5. Sponsor Usage

| Sponsor | Exact Use in CrewLoop |
|---|---|
| **AgentPhone** | Handles SMS and phone calls. Owner texts the job request. CrewLoop texts contractors. If urgent or no response, CrewLoop calls the contractor. Contractors can check in by SMS or phone. |
| **AgentMail** | Sends owner summaries, contractor confirmations, final job reports, timesheets, and receipts. Can also receive proof documents or job details by email. |
| **Browser Use** | Native web workspace layer. CrewLoop uses Browser Use to read event pages, staffing portals, calendars, web forms, and spreadsheets; extract job details; update external schedule tools; verify venue/event details; and capture browser screenshots as audit evidence. |
| **Stripe / MPP** | Creates the payment flow for contractor pay. Used for payment authorization, payment links, payout simulation, receipt generation, and payment status. |
| **Sponge** | Provides the agent wallet and payment rules: pay cap, proof required, approval required, contractor identity match, and release conditions. This is the core sponsor for conditional payment. |
| **Moss** | Stores and retrieves contractor memory: skills, reliability, preferred jobs, response speed, past work, rates, locations, certifications, and no-show history. |

### 5.1 Integration Configuration

Keep real credentials in local environment files only. The repo should document variable names, not secret values.

| Sponsor | Docs | Environment variables |
|---|---|---|
| **AgentPhone** | https://docs.agentphone.ai/welcome | `AGENTPHONE_API_KEY`, `AGENTPHONE_BASE_URL` |
| **AgentMail** | https://docs.agentmail.to/llms.txt | `AGENTMAIL_API_KEY`, `AGENTMAIL_BASE_URL`, `AGENTMAIL_INBOX_NAME` |
| **Browser Use** | https://docs.browser-use.com/cloud/quickstart | `BROWSER_USE_API_KEY` |
| **Moss** | https://docs.moss.dev/docs/start/what-is-moss | `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY` |
| **Sponge** | https://docs.paysponge.com/ | `SPONGE_API_KEY`, `SPONGE_MCP_API_KEY`, `SPONGE_MCP_URL` |
| **Stripe / MPP** | https://docs.stripe.com/ | `STRIPE_API_KEY` |

## 6. Core Agents

### 6.1 Intake Agent

**Purpose:** Understands the job request from the owner.

**Inputs:**

- SMS from owner
- phone call transcript
- email request
- browser-imported job description

**Outputs:**

- structured job object
- urgency score
- missing information questions

**Features:**

- Extract role, time, location, pay, urgency, required skills.
- Ask one clarifying question only if needed.
- Detect urgency from phrases like "tonight," "ASAP," "canceled," or "in 1 hour."

---

### 6.2 Contractor Matching Agent

**Purpose:** Finds the best contractor for the job.

**Inputs:**

- structured job object
- contractor roster
- Moss memory

**Outputs:**

- ranked contractor list
- matching explanation

**Features:**

- Match by required skill.
- Filter by availability.
- Consider distance/location.
- Consider reliability score.
- Consider response speed.
- Consider preferred rate.
- Identify backup contractors.

**Example ranking:**

```text
Maya - bartender - 98% reliability - 2 miles away - recommended
Chris - bartender - 61% reliability - backup
Luis - server - skill mismatch
```

---

### 6.3 Outreach Agent

**Purpose:** Contacts contractors through the right channel.

**Inputs:**

- ranked contractor list
- urgency score
- job details

**Outputs:**

- sent SMS messages
- phone calls
- contractor responses

**Features:**

- Texts top contractor first.
- If urgent, calls immediately.
- If no reply after a configured timeout, escalates to next contractor.
- Handles contractor replies like "yes," "can't," "what's the pay," or "where?"
- Logs every interaction to the dispatch timeline.

---

### 6.4 Scheduling Agent

**Purpose:** Converts contractor acceptance into a confirmed shift.

**Inputs:**

- contractor acceptance
- job object
- owner preferences

**Outputs:**

- confirmed schedule entry
- contractor confirmation message
- owner email summary

**Features:**

- Locks the job once a contractor accepts.
- Sends job details to contractor.
- Sends owner summary email.
- Adds backup contractor if needed.
- Creates a check-in reminder.

---

### 6.5 Proof-of-Work Agent

**Purpose:** Verifies that the contractor showed up and completed the job.

**Inputs:**

- SMS check-in
- photo proof
- QR code scan
- manager approval
- phone confirmation
- uploaded timesheet

**Outputs:**

- proof status
- verification event
- payment release recommendation

**Features:**

- Requests check-in before job starts.
- Accepts proof by SMS/photo/email.
- Compares proof to job requirements.
- Flags missing or suspicious proof.
- Asks owner for final approval before release.

---

### 6.6 Payment Agent

**Purpose:** Holds and releases contractor pay based on rules.

**Inputs:**

- job pay amount
- contractor identity
- proof status
- owner approval
- Sponge/Stripe payment state

**Outputs:**

- payment hold
- payment release
- receipt

**Features:**

- Creates a payment hold when contractor accepts.
- Enforces maximum pay cap.
- Requires proof before release.
- Requires owner approval before release.
- Sends receipt after payment.
- Blocks payment if proof is missing.

**Release rule example:**

```text
Release $120 only if:
- contractor accepted the shift
- contractor checked in
- proof was submitted
- owner approved completion
```

---

### 6.7 Reporting Agent

**Purpose:** Keeps the owner updated.

**Inputs:**

- timeline events
- schedule status
- contractor status
- payment status

**Outputs:**

- email summary
- SMS updates
- dashboard summary

**Features:**

- Sends "contractor found" summary.
- Sends check-in confirmation.
- Sends final job report.
- Includes proof, payment receipt, and timeline.

---

### 6.8 Escalation Agent

**Purpose:** Handles failures and backup plans.

**Inputs:**

- no response
- contractor rejection
- late check-in
- failed proof
- owner override

**Outputs:**

- backup outreach
- owner alert
- new contractor recommendation

**Features:**

- If top contractor does not reply, moves to backup.
- If accepted contractor does not check in, calls them.
- If contractor misses check-in, alerts owner and starts replacement search.
- If payment proof fails, blocks release.

---

### 6.9 Memory Agent

**Purpose:** Learns from contractor history.

**Inputs:**

- prior jobs
- response times
- ratings
- no-shows
- skill tags
- owner notes

**Outputs:**

- contractor reliability score
- personalized ranking
- warnings

**Features:**

- Stores skill profiles.
- Tracks reliability.
- Remembers who accepts urgent jobs.
- Remembers who no-showed.
- Improves ranking over time.

---

### 6.10 Browser Integration Agent

**Purpose:** Makes web tools feel native inside CrewLoop.

**Inputs:**

- event website
- schedule tool
- calendar
- staffing portal
- spreadsheet
- form

**Outputs:**

- imported job details
- updated schedule
- proof screenshots
- source evidence
- browser action log

**Features:**

- Reads job details from a web page.
- Pulls staffing needs from a spreadsheet or portal.
- Updates external schedule.
- Captures screenshots for proof.
- Shows the original web source inside the Dispatch Room.
- Links every imported field to the source page or screenshot.
- Lets the owner approve imported job details before dispatch.
- Re-checks the source after scheduling to confirm external state changed.

**Native browser workflow:**

```text
Open source page -> extract shift details -> show source evidence -> owner confirms -> create Job -> dispatch contractor -> update source page -> save screenshot to audit trail
```

## 7. MVP Features

### Must-have for hackathon demo

1. Owner can text a staffing request or import a shift from a web page.
2. Browser Use captures the source page, extracts job details, and adds source evidence.
3. System creates a Dispatch Room.
4. Contractor list is ranked.
5. Agent texts the top contractor.
6. Agent calls contractor if urgent.
7. Contractor accepts by SMS or call.
8. Schedule is created.
9. External source can be updated or marked as filled.
10. Owner receives email summary.
11. Payment hold is created.
12. Contractor checks in with proof.
13. Owner approves payment release.
14. Receipt/final report is emailed.

### Nice-to-have

1. Backup contractor escalation.
2. QR check-in.
3. Photo proof.
4. Reliability score updates after demo.
5. Multiple contractors for one job.
6. Contractor-facing mini page.
7. Saved templates for common web portals.

## 8. Dispatch Room UI

### Page: `/dispatch/:job_id`

Sections:

1. **Job Request Card**
   - Role
   - Time
   - Location
   - Pay
   - Urgency
   - Required skills

2. **Contractor Match List**
   - Name
   - Skills
   - Distance
   - Reliability
   - Availability
   - Status

3. **Live Timeline**
   - Request parsed
   - Contractor matched
   - Text sent
   - Call placed
   - Contractor accepted
   - Schedule created
   - Payment held
   - Proof received
   - Payment released

4. **Payment Panel**
   - Amount
   - Status: pending / held / blocked / released
   - Release conditions
   - Approval button

5. **Proof Panel**
   - SMS check-in
   - photo proof
   - manager confirmation
   - timesheet

6. **Owner Summary**
   - confirmed contractor
   - ETA
   - pay
   - proof
   - payment status

7. **Web Source Panel**
   - source URL
   - imported fields
   - browser screenshot
   - extraction confidence
   - update status
   - audit evidence

## 9. Data Models

```text
Job
- id
- owner_id
- business_name
- role
- description
- location
- start_time
- end_time
- pay_amount
- urgency
- required_skills
- status

Contractor
- id
- name
- phone
- email
- skills
- location
- hourly_rate
- reliability_score
- response_speed
- availability
- notes

Outreach
- id
- job_id
- contractor_id
- channel: sms | call | email
- message
- status
- response
- timestamp

Schedule
- id
- job_id
- contractor_id
- start_time
- end_time
- status

Proof
- id
- job_id
- contractor_id
- type: sms | photo | qr | manager_approval | call
- content_url
- status
- timestamp

Payment
- id
- job_id
- contractor_id
- amount
- status: pending | held | blocked | released
- release_conditions
- receipt_url

BrowserSource
- id
- job_id
- source_url
- source_type: event_page | staffing_portal | calendar | spreadsheet | form
- imported_fields
- screenshot_url
- extraction_confidence
- update_status: not_needed | pending | updated | failed
- browser_action_log
- timestamp

Event
- id
- job_id
- type
- content
- timestamp
```

## 10. API Endpoints

```text
POST /jobs
GET /jobs/{job_id}
POST /jobs/{job_id}/rank-contractors
POST /jobs/{job_id}/outreach
POST /jobs/{job_id}/accept
POST /jobs/{job_id}/check-in
POST /jobs/{job_id}/approve-release
POST /jobs/{job_id}/events
GET /jobs/{job_id}/stream
POST /browser/import
POST /jobs/{job_id}/browser-sources
POST /jobs/{job_id}/browser-sync
POST /webhooks/agentphone
POST /webhooks/agentmail
POST /webhooks/stripe
POST /webhooks/sponge
```

## 11. Demo Script

Opening:

> Small businesses run on contractor lists, but when someone cancels last minute, the owner still has to manually text, call, schedule, verify, and pay. CrewLoop automates that entire dispatch loop.

Live demo:

1. CrewLoop opens a Bay Events Co. staffing page showing a canceled bartender shift.
2. Browser Use extracts: bartender, tonight, 6-10 PM, SoMa, $120, event experience, urgent.
3. Dispatch Room appears with source evidence from the page.
4. CrewLoop ranks contractors.
5. CrewLoop texts Maya.
6. Because the job is urgent, CrewLoop calls Maya.
7. Maya accepts.
8. CrewLoop schedules Maya, marks the web source as filled, and emails the owner.
9. CrewLoop creates a $120 payment hold.
10. Maya checks in with proof.
11. Owner approves release.
12. Payment is released and receipt is emailed.

Closing:

> CrewLoop is not just an assistant. It is an AI dispatcher that fills urgent jobs, verifies work, and pays contractors only when the job is done.

## 12. Build Plan

### Hour 0-1: Lock demo and data

- Create Bay Events Co. fake business.
- Create contractor roster: Maya, Chris, Luis, Priya.
- Create one urgent bartender job.
- Write contractor call/SMS scripts.

### Hour 1-3: Frontend

- Build Dispatch Room.
- Add fake timeline events.
- Add contractor ranking UI.
- Add payment/proof panels.
- Add Web Source Panel with imported fields and screenshot evidence.

### Hour 3-5: Integrations

- Browser Use import from fake Bay Events Co. staffing page.
- AgentPhone inbound owner SMS.
- AgentPhone outbound contractor SMS/call.
- AgentMail owner summary email.
- Stripe/Sponge payment hold/release simulation.

### Hour 5-6: Orchestration

- Connect job request to matching.
- Connect outreach events to timeline.
- Connect contractor response to schedule.
- Connect proof to payment release.

### Hour 6-7: Proof and payment polish

- Add check-in proof flow.
- Add release approval button.
- Add final report email.

### Hour 7-8: Rehearsal

- Run golden path repeatedly.
- Prepare backup screenshots/video.
- Polish pitch.

## 13. Future Features

1. Contractor reliability learning.
2. Multi-worker staffing jobs.
3. Contractor availability calendar.
4. Automatic backup dispatch.
5. Payroll/payout integrations.
6. Timesheets and invoices.
7. Certifications and document verification.
8. Job templates by industry.
9. Owner policy controls.
10. Contractor mobile portal.
11. Multi-location business support.
12. Integration with scheduling tools.
13. Dispute resolution workflow.
14. Recurring jobs.
15. Marketplace for trusted contractors.

## 14. Success Criteria for Hackathon

The demo should prove:

1. The agent can understand a real staffing request.
2. The agent can choose the right contractor.
3. The agent can communicate through SMS/call/email.
4. The agent can create a schedule.
5. The agent can verify proof of work.
6. The agent can safely release payment after approval.
7. The owner gets a complete audit trail.

## 15. Final Product Framing

CrewLoop is the AI dispatcher and payment-control layer for contractor-heavy small businesses.

Final pitch:

> When a contractor cancels, CrewLoop finds the right replacement, contacts them, schedules the job, verifies they showed up, and releases payment only when the work is done.
