Test Plan for MyAdvisor

1. Purpose

This test plan validates that the core MyAdvisor workflows work correctly for students and advisors, with emphasis on:

- appointment booking
- approval/denial decisions
- history filtering and sorting
- soft-delete and recycle-bin behavior
- role-based access and profile matching
- validation and error handling

2. Scope

In scope:
- Student booking flow
- Advisor request management
- Student history and pending request views
- Recycle-bin restore/delete flow
- Signed-in email to Student/Advisor profile resolution
- Required business rules

Out of scope:
- unrelated UI polish
- non-assignment features not tied to advising workflow

3. Test objectives

The plan verifies that:
- a student can submit a valid advising request
- an advisor can approve or deny only pending requests assigned to them
- a student sees the correct appointment statuses and history
- deleted appointments are hidden from active views and recoverable in recycle bin
- invalid requests are rejected with clear feedback
- the app correctly enforces profile matching by email

4. Test approach

Use a layered test strategy:

- Unit tests
  - business rules in `app/services/appointment_service.py`
- Integration tests
  - HTTP routes in `app/routers/appointments.py`
- Workflow tests
  - end-to-end interaction through the app UI and session flow

5. Test environments

- Local development environment
- SQLite test database or isolated temp DB
- TestClient for FastAPI requests
- Seeded demo accounts:
  - bob / bobpass
  - admin / adminpass
  - advisor / advisorpass

6. Test cases

Workflow 1: Book an Advising Session (Student)

- TC-01: valid booking creates pending appointment
  - Preconditions: logged in as Bob with a matching Student profile
  - Steps:
    - open booking page
    - select valid advisor
    - choose valid date/time
    - enter reason
    - submit
  - Expected:
    - appointment created
    - status = pending
    - redirect to pending requests page
    - success message displayed

- TC-02: booking with invalid advisor fails
  - Preconditions: signed-in student exists
  - Steps: submit advisor_id that does not exist
  - Expected: error message; no appointment created

- TC-03: student without matching profile cannot book
  - Preconditions: account exists without corresponding Student record
  - Expected: BookingProfileNotFoundError or equivalent reject flow

- TC-04: blank/missing reason is rejected
  - Preconditions: valid student and advisor
  - Expected: form validation/error handling with no record created

- TC-05: date/time in the past is rejected or handled as invalid
  - Expected: no appointment created, user sees feedback

Workflow 2: Manage Appointment Requests (Advisor)

- TC-06: advisor sees only their pending requests
  - Preconditions: advisor profile exists
  - Expected: only appointments assigned to that advisor appear

- TC-07: advisor approves request
  - Steps: select approve on pending appointment
  - Expected: status changes to approved

- TC-08: advisor denies request
  - Steps: select deny and provide a denial note
  - Expected: status changes to denied and note is stored

- TC-09: deny without explanation is rejected
  - Expected: service raises AppointmentNotDecidableError and request is not updated

- TC-10: advisor cannot act on another advisor’s request
  - Expected: request is not updated and error is displayed

- TC-11: already resolved request cannot be changed again
  - Expected: decision is rejected

Workflow 3: View Advising History (Student)

- TC-12: history shows only resolved appointments
  - Expected: pending items excluded
  - resolved items sorted newest first

- TC-13: pending appointments are displayed separately from history
  - Expected: pending requests on pending page
  - history shows only approved/denied appointments

- TC-14: each appointment shows advisor/student details correctly
  - Expected: linked student/advisor records display as expected

- TC-15: deleted/trashed appointments are hidden from active history
  - Expected: not shown in normal views

Workflow 4: Recycle Bin / Restore

- TC-16: student can delete own appointment
  - Expected: soft-delete flag set, item removed from active list

- TC-17: student cannot delete another student’s appointment
  - Expected: error and no update

- TC-18: recycle bin shows deleted appointments
  - Expected: only the student’s deleted records are visible

- TC-19: restore works for valid deleted appointment
  - Expected: record restored to active view

- TC-20: expired items are purged automatically
  - Preconditions: appointment older than retention threshold
  - Expected: item is removed permanently when bin is opened or restore is attempted

7. Negative and edge cases

- signed-in user has no matching Student or Advisor profile
- invalid appointment_id
- multiple rows with same email
- deleted appointment not belonging to signed-in student
- request is denied without note
- invalid decision value passed directly to service
- app created with no seeded data

8. Priority levels

High priority:
- valid booking
- advisor approval/denial
- permission validation
- delete/restore
- profile-matching logic

Medium priority:
- sorting, filtering, display formatting
- alert message correctness
- navigation after action

Low priority:
- cosmetic details and layout consistency

9. Acceptance criteria

The test plan is complete when:
- all core workflows pass
- all critical validation failures are covered
- role-based restrictions are tested
- recycle-bin and retention logic are tested
- the app does not allow unauthorized record access

10. Example test summary table

| ID | Priority | Workflow | Scenario | Expected result |
|---|---|---|---|---|
| TC-01 | High | Booking | Valid booking | Appointment created as pending |
| TC-02 | High | Booking | Invalid advisor | Error, no record |
| TC-06 | High | Advisor | View pending requests | Only own requests shown |
| TC-07 | High | Advisor | Approve | Status becomes approved |
| TC-09 | High | Advisor | Deny without note | Rejected |
| TC-12 | Medium | History | Resolved appointments only | Only approved/denied appear |
| TC-16 | High | Delete | Student deletes own appointment | Soft-deleted in bin |
| TC-19 | High | Restore | Restore from trash | Record visible again |

11. Recommended implementation order

Start with these tests first:
1. appointment_service tests
2. router tests
3. workflow tests

That order matches the architecture and keeps debugging easier.

If you want, I can take the next step and turn this into:
- a full pytest test file structure
- actual test code for the service layer
- a complete test case matrix in a document format you can paste into your assignment
