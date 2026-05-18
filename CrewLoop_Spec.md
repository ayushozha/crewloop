# CrewLoop Product Spec

## 1. Product Summary

**Product name:** CrewLoop
**One-line pitch:** CrewLoop turns a messy event request into a staffed, stocked, invoiced, and payment-ready job.

**Short pitch:** Tell CrewLoop about an event, and it finds the right crew, confirms availability, buys required supplies, invoices the client, and holds worker pay until the job is completed.

**Product framing:** CrewLoop is an AI ops dispatcher for event businesses. The demo should feel like one unified workflow: **fulfill this event**. Staffing, supplies, invoicing, and worker pay are not separate products; they are steps in the same event fulfillment loop.

## 2. Exact Problem

Event businesses run on messy operational threads: client texts, contractor rosters, vendor websites, supply runs, invoices, and conditional worker pay. When a client requests an event, the owner has to turn that request into a real operation.

Today the owner manually:

- asks follow-up questions about the event
- infers how many workers and roles are needed
- checks contractor availability and reliability
- texts or calls workers
- fills gaps with backups
- creates a schedule
- buys supplies
- prepares and sends an invoice
- holds or tracks worker pay
- collects proof of work
- releases payment after completion

This is especially painful for businesses that run events or field work:

- catering companies
- event staffing companies
- venue operators
- cleaning companies
- moving companies
- home-service companies
- photographers and production crews
- hospitality teams
- security staffing teams
- field service operators

The core problem is:

> Event businesses need a fast, reliable way to turn a client request into a fully staffed, stocked, invoiced, and payment-ready job with proof and an audit trail.

## 3. Exact Idea

CrewLoop turns a messy event request into a guided fulfillment workflow. It starts in chat, asks only the minimum clarifying questions, uses Browser Use when source evidence is needed, and then coordinates the operational steps.

Example owner text:

> Hey, we got an event this Saturday that needs 10 people. Can you help me staff it, get supplies, and prepare the invoice?

CrewLoop then:

1. Asks 3 structured questions: event type, timing, and whether to infer roles.
2. Infers the staffing plan and responsibilities.
3. Creates a recommended crew plan.
4. Shortlists contractors from the roster using Moss memory.
5. Asks owner approval before contacting workers.
6. Texts most contractors and calls only urgent or key roles.
7. Fills open roles with backups.
8. Creates the event schedule and sends contractor confirmations.
9. Infers a short supply list and asks owner approval before purchase.
10. Uses Browser Use to check or simulate vendor checkout.
11. Prepares and sends the client invoice.
12. Creates conditional worker pay holds.
13. Collects proof of check-in and completion.
14. Releases worker pay after proof and owner approval.

## 4. Hackathon Demo Scenario

### Demo business

**Bay Events Co.** needs to fulfill a corporate dinner.

### Demo request

> We have a corporate dinner this Saturday for 80 guests in SoMa from 6-11 PM. Can you staff it, get supplies, and prepare the invoice?

### Demo outcome

CrewLoop infers a 10-person crew, ranks candidates, asks the owner to approve the shortlist, texts the crew, calls one urgent/key role live, fills gaps with backups, creates the schedule, recommends a small supply purchase, prepares the client invoice, creates conditional worker pay holds, and shows proof-based release.

### Demo constraint

The live demo should not try to show every operational detail. It should focus on three big moments:

1. Smart crew matching.
2. Real contractor outreach: SMS plus one live phone call.
3. Conditional worker payment: held until proof of work.

Inventory and invoice should appear as quick, natural steps in the same timeline, not as separate product demos.

### Demo realism split

**Must be real in the demo:**

- Chat flow.
- Candidate shortlisting.
- SMS to contractors.
- One outbound phone call.
- Schedule creation.
- Invoice preview/email.
- Payment hold/release UI.

**Can be demo-controlled:**

- Contractor roster.
- Contractor replies.
- Inventory store.
- Client invoice recipient.
- Payment sandbox.
- Check-in proof.

## 5. Sponsor Usage

| Sponsor | Exact Use in CrewLoop |
|---|---|
| **AgentPhone** | Text and call contractors, receive accept/decline/question/check-in messages, and call urgent or key roles live during the demo. |
| **AgentMail** | Email client invoice, owner summary, contractor confirmations, final job report, receipt, and vendor/invoice messages when needed. |
| **Browser Use** | Read event or staffing pages, check vendor availability, simulate or perform supply checkout, capture screenshots/source evidence, and update external source status. |
| **Stripe / MPP** | Create client invoice/payment link and represent worker payment/payment status in sandbox. |
| **Sponge** | Hold worker pay with release rules: accepted assignment, check-in, shift complete, proof submitted, and owner approval. |
| **Moss** | Remember contractor skills, reliability, rates, past event history, client preferences, response speed, and no-show risk. |

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

**Purpose:** Understands the event request from the owner.

**Inputs:**

- SMS from owner
- phone call transcript
- email request
- browser-imported event or job description
- client event details

**Outputs:**

- structured event/job object
- urgency score
- missing information questions
- fulfillment intent: staff, stock, invoice, payment setup

**Features:**

- Extract event type, guest count, time, location, budget, urgency, and requested outcomes.
- Ask one clarifying question only if needed.
- Use structured buttons for demo-speed clarification:
  - event type
  - timing
  - infer roles vs owner-specified roles
  - approval before outreach
- Detect urgency from phrases like "tonight," "ASAP," "canceled," "this weekend," or "in 1 hour."

---

### 6.2 Event Planning Agent

**Purpose:** Converts an event request into an operational plan.

**Inputs:**

- structured event object
- event type
- guest count
- time window
- owner preferences
- known venue/client history

**Outputs:**

- recommended crew plan
- inferred responsibilities
- estimated labor cost
- urgency rating
- approval prompt

**Features:**

- Infer crew needs from event type and guest count.
- Keep demo roles simple and explainable.
- Ask owner approval before contractor outreach.
- Produce a clear plan:

```text
Event: Corporate dinner
Guests: 80
Time: 6 PM-11 PM
Location: SoMa

Recommended crew:
- 2 bartenders
- 4 servers
- 2 setup crew
- 1 event lead
- 1 cleanup lead

Total: 10 people
Estimated labor cost: $1,450
Urgency: medium
```

---

### 6.3 Contractor Matching Agent

**Purpose:** Finds the best crew for the event.

**Inputs:**

- structured event/job object
- required role plan
- contractor roster
- Moss memory

**Outputs:**

- ranked contractor list by role
- matching explanation
- backup list

**Features:**

- Match by required skill.
- Filter by availability.
- Consider distance/location.
- Consider reliability score.
- Consider response speed.
- Consider preferred rate.
- Consider similar event history.
- Consider client preference.
- Consider no-show risk.
- Identify backup contractors.

**Example ranking:**

```text
Bartenders:
1. Emma - bartender - 98% reliability - 2 miles away - recommended
2. Madison - bartender - 84% reliability - backup

Servers:
1. Luis - server - 95% reliability - $25/hr
2. Ashley - server - 91% reliability - $26/hr
```

---

### 6.4 Outreach Agent

**Purpose:** Contacts contractors through the right channel.

**Inputs:**

- approved crew shortlist
- urgency score
- event/job details

**Outputs:**

- sent SMS messages
- phone calls
- contractor responses

**Features:**

- Texts approved contractors.
- Calls only urgent or key roles live during the demo.
- If no reply after a configured timeout, escalates to next contractor.
- Handles contractor replies like "yes," "can't," "what's the pay," or "where?"
- Logs every interaction to the dispatch timeline.
- Demo pattern:

```text
Texted 10 contractors
7 accepted by SMS
1 declined
1 no response
Calling backup bartender now
Backup accepted
Crew complete: 10/10
```

---

### 6.5 Scheduling Agent

**Purpose:** Converts accepted workers into a confirmed event schedule.

**Inputs:**

- contractor acceptances
- event/job object
- owner preferences

**Outputs:**

- confirmed schedule entries
- role-specific contractor confirmation messages
- owner email summary

**Features:**

- Locks each role once a contractor accepts.
- Sends assignment details to each contractor.
- Sends owner summary email.
- Adds backup contractor if needed.
- Creates a check-in reminder.
- Creates an event schedule:

```text
5:00 PM - Setup crew arrives
5:30 PM - Event lead arrives
6:00 PM - Servers arrive
6:30 PM - Bartenders arrive
10:30 PM - Cleanup starts
11:30 PM - Shift complete
```

---

### 6.6 Procurement and Invoice Agent

**Purpose:** Handles the small non-staffing operations required to fulfill the event.

**Inputs:**

- event type
- guest count
- inferred supply needs
- current inventory or vendor source
- client billing details
- owner approval

**Outputs:**

- small supply list
- browser/vendor evidence
- purchase approval request
- invoice preview
- sent invoice email

**Features:**

- Keep supply inference short for demo:

```text
- 100 compostable cups
- 100 napkins
- 4 bags of ice
- 2 tablecloths
- bartender tool kit rental
```

- Ask owner approval before purchase.
- Use Browser Use to check vendor availability or simulate checkout.
- Prepare client invoice:

```text
Labor: $1,450
Supplies: $86
Service fee: $220
Total invoice: $1,756
Deposit requested: $500
Balance due after event: $1,256
```

- Send invoice through AgentMail after approval.

---

### 6.7 Proof-of-Work Agent

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

### 6.8 Payment Agent

**Purpose:** Holds and releases worker pay based on rules.

**Inputs:**

- event/job pay amounts
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
Maya - $175 - held
Release only if:
- contractor accepted assignment
- contractor checked in
- shift completed
- proof was submitted
- manager/owner approved completion
```

---

### 6.9 Reporting Agent

**Purpose:** Keeps the owner updated.

**Inputs:**

- timeline events
- schedule status
- crew fill status
- invoice status
- supply purchase status
- payment status

**Outputs:**

- email summary
- SMS updates
- dashboard summary

**Features:**

- Sends "crew confirmed" summary.
- Sends invoice and supply summary.
- Sends check-in confirmation.
- Sends final event report.
- Includes proof, payment receipt, and timeline.

---

### 6.10 Escalation Agent

**Purpose:** Handles failures and backup plans.

**Inputs:**

- no response
- contractor rejection
- late check-in
- failed proof
- vendor unavailable
- invoice edit needed
- owner override

**Outputs:**

- backup outreach
- owner alert
- new contractor recommendation

**Features:**

- If top contractor does not reply, moves to backup.
- If accepted contractor does not check in, calls them.
- If contractor misses check-in, alerts owner and starts replacement search.
- If vendor stock is unavailable, suggests a simpler substitute.
- If payment proof fails, blocks release.

---

### 6.11 Memory Agent

**Purpose:** Learns from contractor, vendor, and client history.

**Inputs:**

- prior jobs
- response times
- ratings
- no-shows
- skill tags
- owner notes
- vendor outcomes
- client preferences

**Outputs:**

- contractor reliability score
- personalized ranking
- warnings

**Features:**

- Stores skill profiles.
- Tracks reliability.
- Remembers who accepts urgent jobs.
- Remembers who no-showed.
- Remembers preferred vendors and client-specific staffing patterns.
- Improves ranking over time.

---

### 6.12 Browser Integration Agent

**Purpose:** Makes web tools feel native inside CrewLoop.

**Inputs:**

- event website
- vendor website
- schedule tool
- calendar
- staffing portal
- spreadsheet
- form

**Outputs:**

- imported job details
- supply availability
- checkout or vendor evidence
- updated schedule
- proof screenshots
- source evidence
- browser action log

**Features:**

- Reads job details from a web page.
- Pulls staffing needs from a spreadsheet or portal.
- Checks inventory/vendor availability.
- Simulates or performs approved supply checkout.
- Updates external schedule.
- Captures screenshots for proof.
- Shows the original web source inside the Dispatch Room.
- Links every imported field to the source page or screenshot.
- Lets the owner approve imported job details before dispatch.
- Re-checks the source after scheduling to confirm external state changed.

**Native browser workflow:**

```text
Open source page -> extract event details -> show source evidence -> owner approves -> create plan -> dispatch crew -> check supplies -> send invoice -> save screenshots to audit trail
```

## 7. MVP Features

### Must-have for hackathon demo

1. Owner can start from chat with an event request.
2. Agent asks 3 structured questions with buttons.
3. Agent infers a 10-person staffing plan.
4. System creates a Dispatch/Event Fulfillment Room.
5. Browser Use captures event/source evidence.
6. Contractor shortlist is ranked by role.
7. Owner approves shortlist before outreach.
8. Agent texts contractors.
9. Agent calls one urgent/key role live.
10. Demo-controlled contractor replies fill the crew.
11. Schedule is created.
12. Agent recommends 3-5 supply items and asks approval.
13. Browser Use checks or simulates supply checkout.
14. Client invoice preview is generated and emailed.
15. Worker payment holds are created.
16. Contractor checks in with proof.
17. Owner approves payment release.
18. Receipt/final report is emailed.

### Nice-to-have

1. Backup contractor escalation for each role.
2. QR check-in.
3. Photo proof.
4. Reliability score updates after demo.
5. Contractor-facing mini page.
6. Saved templates for common web portals.
7. Real vendor checkout after explicit owner approval.
8. Invoice markup editing.
9. Client deposit payment link.

## 8. Dispatch Room UI

### Page: `/dispatch/:job_id`

For demo, this can still be called Dispatch Room, but the story should be **Event Fulfillment Room**: one place where staffing, supplies, invoice, payment holds, proof, and source evidence are visible.

Sections:

1. **Event Request Card**
   - Event type
   - Guest count
   - Time
   - Location
   - Budget / labor estimate
   - Urgency
   - Required outcomes: staff, supplies, invoice, pay

2. **Crew Plan + Contractor Match List**
   - Role groups
   - Name
   - Skills
   - Distance
   - Reliability
   - Availability
   - Rate
   - Capabilities
   - Status

3. **Live Timeline**
   - Event request parsed
   - Source evidence captured
   - Crew plan inferred
   - Shortlist approved
   - Texts sent
   - Call placed for key role
   - Crew accepted
   - Schedule created
   - Supplies approved
   - Invoice prepared/sent
   - Worker pay held
   - Proof received
   - Worker pay released

4. **Supply Panel**
   - Recommended items
   - Estimated cost
   - Vendor/source
   - Browser evidence
   - Approval status

5. **Invoice Panel**
   - Labor line item
   - Supplies line item
   - Service fee
   - Total invoice
   - Deposit request
   - Email status

6. **Worker Payment Panel**
   - Amount
   - Status: pending / held / blocked / released
   - Release conditions
   - Approval button

7. **Proof Panel**
   - SMS check-in
   - photo proof
   - manager confirmation
   - timesheet

8. **Owner Summary**
   - crew filled count
   - schedule status
   - supply status
   - invoice status
   - proof
   - payment status

9. **Web Source Panel**
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
- event_type
- description
- guest_count
- location
- start_time
- end_time
- estimated_labor_cost
- estimated_supply_cost
- urgency
- required_outcomes
- status

EventPlan
- id
- job_id
- roles: bartender/server/setup/event_lead/cleanup
- required_count_by_role
- responsibilities
- estimated_labor_cost
- approval_status

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
- role
- start_time
- end_time
- status

SupplyOrder
- id
- job_id
- items
- vendor
- estimated_cost
- approval_status
- browser_source_id
- checkout_status

ClientInvoice
- id
- job_id
- client_email
- labor_amount
- supplies_amount
- service_fee
- deposit_amount
- total_amount
- status: draft | sent | paid | void
- provider_state

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
- schedule_id
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
POST /jobs/{job_id}/infer-event-plan
POST /jobs/{job_id}/rank-contractors
POST /jobs/{job_id}/outreach
POST /jobs/{job_id}/accept
POST /jobs/{job_id}/schedule
POST /jobs/{job_id}/recommend-supplies
POST /jobs/{job_id}/approve-supplies
POST /jobs/{job_id}/invoice
POST /jobs/{job_id}/send-invoice
POST /jobs/{job_id}/payment-holds
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

> Event businesses run through texts, tabs, vendor sites, invoices, calls, and payment approvals. CrewLoop turns one messy event request into a fulfilled event: staffed, stocked, invoiced, and payment-ready.

Live demo:

1. Owner starts in chat: "We have a corporate dinner this Saturday for 80 guests. Can you staff it, get supplies, and prepare the invoice?"
2. CrewLoop asks 3 structured questions: event type, timing, and whether to infer roles.
3. CrewLoop infers the crew plan: 2 bartenders, 4 servers, 2 setup crew, 1 event lead, 1 cleanup lead.
4. CrewLoop shows estimated labor cost and asks for shortlist approval.
5. CrewLoop ranks contractors by role using reliability, skill, availability, distance, rate, and Moss memory.
6. Owner clicks "Approve and contact."
7. CrewLoop texts the crew and calls one key role live.
8. Dashboard shows demo-controlled replies: 7 accepted, 1 declined, 1 no response, backup accepted, crew complete 10/10.
9. CrewLoop creates the event schedule and sends contractor confirmations.
10. CrewLoop recommends 3-5 supply items and asks approval for an $86 purchase.
11. Browser Use checks vendor availability or simulates checkout and saves screenshot evidence.
12. CrewLoop prepares the client invoice: labor, supplies, service fee, deposit, balance.
13. CrewLoop sends the invoice through AgentMail.
14. CrewLoop creates conditional worker pay holds.
15. Contractor check-in/proof arrives.
16. Owner approves release.
17. Worker pay is released and final report/receipt is emailed.

Closing:

> CrewLoop is not a staffing app, an inventory app, or an invoice app. It is the ops dispatcher that fulfills the event and keeps every action accountable.

## 12. Build Plan

### Hour 0-1: Lock demo and data

- Create Bay Events Co. fake business.
- Create contractor roster: Emma, Madison, Luis, Ashley.
- Create one corporate dinner event request.
- Create demo crew plan for 10 workers.
- Create demo supply list and invoice values.
- Write contractor call/SMS scripts.

### Hour 1-3: Frontend

- Build chat-first event intake.
- Build Dispatch/Event Fulfillment Room.
- Add fake timeline events.
- Add crew plan and contractor ranking UI.
- Add supply and invoice preview panels.
- Add payment/proof panels.
- Add Web Source Panel with imported fields and screenshot evidence.

### Hour 3-5: Integrations

- Browser Use import from fake Bay Events Co. event/source page.
- Browser Use supply availability / checkout simulation.
- AgentPhone inbound owner SMS.
- AgentPhone outbound contractor SMS plus one live call.
- AgentMail client invoice, owner summary, and contractor confirmations.
- Stripe/Sponge client invoice/payment state and worker pay hold/release simulation.

### Hour 5-6: Orchestration

- Connect event request to crew plan.
- Connect crew plan to matching.
- Connect outreach events to timeline.
- Connect contractor responses to schedule.
- Connect supply approval to Browser Use evidence.
- Connect invoice preview to AgentMail.
- Connect proof to payment release.

### Hour 6-7: Proof and payment polish

- Add check-in proof flow.
- Add release approval button.
- Add worker payment holds per role.
- Add final report email.

### Hour 7-8: Rehearsal

- Run golden path repeatedly.
- Prepare backup screenshots/video.
- Polish pitch.

## 13. Future Features

1. Contractor reliability learning.
2. Contractor availability calendar.
3. Automatic backup dispatch.
4. Real vendor checkout after explicit owner approval.
5. Inventory memory and reorder thresholds.
6. Client invoice payment links and deposit tracking.
7. Payroll/payout integrations.
8. Timesheets and certifications.
9. Job templates by event type.
10. Owner policy controls.
11. Contractor mobile portal.
12. Multi-location business support.
13. Integration with scheduling tools.
14. Dispute resolution workflow.
15. Recurring events.
16. Marketplace for trusted contractors and vendors.

## 14. Success Criteria for Hackathon

The demo should prove:

1. The agent can understand a real event request.
2. The agent can infer a staffing and supply plan.
3. The agent can choose the right crew from memory.
4. The owner approves before high-impact actions.
5. The agent can communicate through SMS/call/email.
6. The agent can create a schedule.
7. The agent can prepare invoice and supply steps without branching into separate products.
8. The agent can verify proof of work.
9. The agent can safely release worker pay after approval.
10. The owner gets a complete audit trail.

## 15. Final Product Framing

CrewLoop is the AI ops dispatcher for event businesses.

Final pitch:

> CrewLoop turns a messy event request into a fully staffed, stocked, invoiced, and payment-ready job.

Demo thesis:

> Fulfill this event.
